import os
import json
import base64
from queue import Queue
from flask import Flask, request, Response, jsonify
from flask_socketio import SocketIO
from twilio.twiml.voice_response import VoiceResponse, Gather
from twilio.rest import Client
from google.cloud import speech
from google.cloud import texttospeech
import google.generativeai as genai
from dotenv import load_dotenv
from services.call_orchestrator import CallOrchestrator


from gevent import pywsgi
from geventwebsocket.handler import WebSocketHandler


ngrok_url = os.getenv('NGROK_URL', 'https://3e54-2405-201-c01e-40d3-bc8f-6e8c-9cee-acfb.ngrok-free.app')

# Load environment variables
load_dotenv()

# Initialize Twilio client
twilio_client = Client(
    os.getenv('TWILIO_ACCOUNT_SID'),
    os.getenv('TWILIO_AUTH_TOKEN')
)

# Initialize Google Cloud clients
speech_client = speech.SpeechClient()
tts_client = texttospeech.TextToSpeechClient()

# Configure Gemini API
genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
model = genai.GenerativeModel('models/gemini-1.5-pro-latest')

# Global variables
call_queue = Queue()  # Queue for managing outbound calls
call_states = {}      # Store call state information
active_connections = {}  # WebSocket connections

# Initialize global state and orchestrator
call_orchestrator = CallOrchestrator(call_queue, call_states, active_connections)


# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default-secret-key')
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent')

# ===== Flask Routes =====

@socketio.on('connect')
def handle_connect():
    print("Client connected to SocketIO")

@socketio.on('disconnect')
def handle_disconnect():
    print("Client disconnected from SocketIO")

@app.route('/')
def index():
    return "Reacho Outbound Voice AI System is running!"

@app.route('/upload_csv', methods=['POST'])
def upload_csv():
    """Endpoint to upload CSV file with lead information"""
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "No file part"}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({"status": "error", "message": "No selected file"}), 400
        
    if not file.filename.endswith('.csv'):
        return jsonify({"status": "error", "message": "File must be a CSV"}), 400
    
    # Save the file temporarily
    temp_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'temp_csv')
    os.makedirs(temp_path, exist_ok=True)
    file_path = os.path.join(temp_path, file.filename)
    file.save(file_path)
    
    # Process the CSV file
    result = call_orchestrator.process_csv(file_path)
    
    # Start call processing if not already running
    call_orchestrator.start_call_processing()
    
    return jsonify(result)

@app.route('/outbound_call', methods=['POST'])
def outbound_call():
    """Handle outbound call connection"""
    response = VoiceResponse()
    call_sid = request.values.get('CallSid')
    print("in out bound allacall sid", call_sid)
    
    if call_sid in call_states:
        # Get lead information
        lead_info = call_states[call_sid]['lead_info']
        name = lead_info.get('name', '')
        
        # Initial greeting
        greeting = f"Hello{', ' + name if name else ''}! This is Reacho AI calling. How are you today?"
        response.say(greeting)
        
        # Start streaming
        response.append(start_streaming(call_sid))
    else:
        # Fallback if call state not found
        response.say("Hello! This is Reacho AI calling. How are you today?")
        response.append(start_streaming(call_sid))
    
    return Response(str(response), mimetype='text/xml')

def start_streaming(call_sid):
    """Configure Twilio to stream audio to our WebSocket"""
    url = f"wss://{ngrok_url.replace('https://', '').replace('http://', '')}/stream/{call_sid}"
    print("starting streaming on websocket ", url)
    response = VoiceResponse()
    connect = response.connect()
    connect.stream(
    url=url,
        status_callback=f"{ngrok_url}/stream_status",
        status_callback_method="POST",
        track="inbound_track"
    )

    
    # Add gather to keep the call open and listen
    gather = Gather(input='speech', action='/process_speech', method='POST', speechTimeout='auto')
    response.append(gather)
    
    return response

@app.route('/process_speech', methods=['POST'])
def process_speech():
    """Process speech after Gather completes"""
    call_sid = request.values.get('CallSid')
    response = VoiceResponse()
    
    if call_sid in call_states and call_states[call_sid]['responses']:
        # Get the latest AI response
        ai_response = call_states[call_sid]['responses'][-1]
        response.say(ai_response)
    else:
        response.say("I'm sorry, I didn't catch that. Could you please repeat?")
    
    # Continue streaming
    response.append(start_streaming(call_sid))
    
    return Response(str(response), mimetype='text/xml')

@app.route('/stream_status', methods=['POST'])
def stream_status():
    print(">>> Stream status update:", dict(request.values))
    return Response("", status=200)

@app.route('/call_status', methods=['POST'])
def call_status():
    """Handle call status updates from Twilio"""
    call_sid = request.values.get('CallSid')
    call_status = request.values.get('CallStatus')
    
    # Update call status
    result = call_orchestrator.handle_call_status_update(call_sid, call_status)
    
    return jsonify(result)

@app.before_request
def log_every_request():
    print(f"[Flask] Incoming: {request.method} {request.path}")

@app.route('/stream/<call_sid>')
def stream(call_sid):
    print(f"[Flask] WebSocket stream endpoint hit for: {call_sid}")
    
    ws = request.environ.get('wsgi.websocket')
    if not ws:
        print("[Flask] ❌ No WebSocket found in request.environ")
        return "WebSocket connection failed", 400

    print(f"WebSocket connected for call_sid: {call_sid}")
    active_connections[call_sid] = ws

    try:
        handle_websocket(ws, call_sid)
    except Exception as e:
        print(f"WebSocket handler error: {e}")
    finally:
        print(f"WebSocket closing for call_sid: {call_sid}")
        if call_sid in active_connections:
            del active_connections[call_sid]

    return ""  # Not actually used, socket stays open

def handle_websocket(ws, call_sid):
    """Handle WebSocket connection for audio streaming"""
    print("handling websocket connection", call_sid)
    try:
        # Get services
        speech_recognition = call_orchestrator.speech_recognition
        ai_handler = call_orchestrator.ai_handler
        tts_service = call_orchestrator.tts_service
        data_logger = call_orchestrator.data_logger
        
        # Configure speech recognition
        streaming_config = speech_recognition.get_streaming_config()
        
        # Create a generator for the audio stream
        def audio_stream():
            while True:
                try:
                    message = ws.receive()
                    if message:
                        data = json.loads(message)
                        if data.get('event') == 'media':
                            payload = data.get('media', {}).get('payload')
                            if payload:
                                chunk = base64.b64decode(payload)
                                yield speech.StreamingRecognizeRequest(audio_content=chunk)
                except Exception as e:
                    print(f"Error receiving WebSocket message: {e}")
                    break
        
        # Process the audio stream with Google Speech-to-Text
        for transcript, is_final in speech_recognition.process_audio_stream(audio_stream()):
            if not transcript:
                continue
                
            # Update the transcript in call state
            if call_sid in call_states:
                call_states[call_sid]['transcript'] = transcript
                
                # Log the transcript
                data_logger.log_transcript(call_sid, transcript, is_final)
                
                # If this is a final result, generate AI response
                if is_final:
                    # Get lead information
                    lead_info = call_states[call_sid]['lead_info'] if call_sid in call_states else {}
                    
                    # Generate AI response
                    ai_text = ai_handler.generate_response(call_sid, transcript, lead_info)
                    
                    # Log the AI response
                    data_logger.log_ai_response(call_sid, ai_text)
                    
                    # Convert to speech
                    audio_content = tts_service.synthesize(ai_text)
                    
                    # Store the audio for playback
                    if call_sid in call_states and audio_content:
                        call_states[call_sid]['audio_response'] = audio_content
                    
                    # Emit the response via SocketIO for any web clients
                    socketio.emit('ai_response', {
                        'call_sid': call_sid,
                        'transcript': transcript,
                        'response': ai_text
                    })
    
    except Exception as e:
        print(f"WebSocket error: {e}")
        # Log the error
        if call_sid in call_states:
            call_orchestrator.data_logger.log_error('websocket', str(e), {'call_sid': call_sid})
    finally:
        if call_sid in active_connections:
            del active_connections[call_sid]

@app.route('/api/calls', methods=['GET'])
def get_calls():
    """API endpoint to get all active calls"""
    active_calls = []
    for call_sid, state in call_states.items():
        active_calls.append({
            'call_sid': call_sid,
            'status': state.get('status', 'unknown'),
            'lead_info': state.get('lead_info', {}),
            'start_time': state.get('start_time'),
            'transcript': state.get('transcript', '')
        })
    
    return jsonify(active_calls)

@app.route('/api/call/<call_sid>', methods=['GET'])
def get_call(call_sid):
    """API endpoint to get details for a specific call"""
    if call_sid in call_states:
        return jsonify(call_states[call_sid])
    else:
        return jsonify({"status": "error", "message": "Call not found"}), 404

@app.route('/api/end_call/<call_sid>', methods=['POST'])
def api_end_call(call_sid):
    """API endpoint to end a specific call"""
    if call_sid in call_states:
        result = call_orchestrator.voice_service.end_call(call_sid)
        return jsonify(result)
    else:
        return jsonify({"status": "error", "message": "Call not found"}), 404

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "ok"})

# if __name__ == '__main__':
#     # Create necessary directories
#     os.makedirs('logs', exist_ok=True)
#     os.makedirs('temp_csv', exist_ok=True)
    
#     # Run the Flask app with SocketIO
#     socketio.run(app, host=os.getenv('HOST', '0.0.0.0'), port=int(os.getenv('PORT', 5000)), debug=True, allow_unsafe_werkzeug=True)


if __name__ == '__main__':
    os.makedirs('logs', exist_ok=True)
    os.makedirs('temp_csv', exist_ok=True)

    server = pywsgi.WSGIServer(
        (os.getenv('HOST', '0.0.0.0'), int(os.getenv('PORT', 5000))),
        app,
        handler_class=WebSocketHandler
    )
    server.serve_forever()
