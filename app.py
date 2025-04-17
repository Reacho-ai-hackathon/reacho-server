import os
import json
import base64
import asyncio
import threading
from flask import Flask, request, Response
from flask_socketio import SocketIO
from twilio.twiml.voice_response import VoiceResponse, Gather
from google.cloud import speech
from google.cloud import texttospeech
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default-secret-key')
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent')

# Initialize Google Cloud clients
speech_client = speech.SpeechClient()
tts_client = texttospeech.TextToSpeechClient()

# Configure Gemini API
genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
model = genai.GenerativeModel('gemini-pro')

# Global variables to store call state
call_states = {}

# WebSocket connections
active_connections = {}

@app.route('/')
def index():
    return "Reacho Voice AI System is running!"

@app.route('/call', methods=['POST'])
def incoming_call():
    """Handle incoming Twilio calls"""
    response = VoiceResponse()
    caller_id = request.values.get('From', 'unknown')
    call_sid = request.values.get('CallSid')
    
    # Initialize call state
    call_states[call_sid] = {
        'caller_id': caller_id,
        'transcript': '',
        'responses': []
    }
    
    # Initial greeting
    response.say("Welcome to Reacho AI. How can I help you today?")
    
    # Start streaming
    response.append(start_streaming(call_sid))
    
    return Response(str(response), mimetype='text/xml')

def start_streaming(call_sid):
    """Configure Twilio to stream audio to our WebSocket"""
    response = VoiceResponse()
    connect = response.connect()
    connect.stream(url=f'wss://{request.host}/stream/{call_sid}')
    
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

@app.route('/end_call', methods=['POST'])
def end_call():
    """Handle call ending"""
    call_sid = request.values.get('CallSid')
    
    # Clean up resources
    if call_sid in call_states:
        del call_states[call_sid]
    
    if call_sid in active_connections:
        del active_connections[call_sid]
    
    return "", 204

@socketio.on('connect')
def handle_connect():
    print("Client connected to SocketIO")

@socketio.on('disconnect')
def handle_disconnect():
    print("Client disconnected from SocketIO")

@app.route('/stream/<call_sid>')
def stream(call_sid):
    """WebSocket endpoint for audio streaming"""
    if request.environ.get('wsgi.websocket'):
        ws = request.environ['wsgi.websocket']
        active_connections[call_sid] = ws
        
        # Start a thread for handling the WebSocket connection
        threading.Thread(target=handle_websocket, args=(ws, call_sid)).start()
        
        return ""
    return "WebSocket connection failed", 400

def handle_websocket(ws, call_sid):
    """Handle WebSocket connection for audio streaming"""
    try:
        # Configure speech recognition
        streaming_config = speech.StreamingRecognitionConfig(
            config=speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.MULAW,
                sample_rate_hertz=8000,
                language_code="en-US",
                enable_automatic_punctuation=True,
            ),
            interim_results=True,
        )
        
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
        responses = speech_client.streaming_recognize(streaming_config, audio_stream())
        
        for response in responses:
            if not response.results:
                continue
                
            result = response.results[0]
            if not result.alternatives:
                continue
                
            transcript = result.alternatives[0].transcript
            
            # Update the transcript in call state
            if call_sid in call_states:
                call_states[call_sid]['transcript'] = transcript
                
                # If this is a final result, generate AI response
                if result.is_final:
                    generate_ai_response(call_sid, transcript)
    
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        if call_sid in active_connections:
            del active_connections[call_sid]

def generate_ai_response(call_sid, transcript):
    """Generate AI response using Gemini"""
    try:
        # Generate response with Gemini
        prompt = f"You are a helpful AI assistant on a phone call. The caller said: '{transcript}'. Provide a natural, conversational response."
        response = model.generate_content(prompt)
        ai_text = response.text
        
        # Store the response
        if call_sid in call_states:
            call_states[call_sid]['responses'].append(ai_text)
        
        # Convert to speech
        synthesize_speech(call_sid, ai_text)
        
        # Emit the response via SocketIO for any web clients
        socketio.emit('ai_response', {
            'call_sid': call_sid,
            'transcript': transcript,
            'response': ai_text
        })
        
    except Exception as e:
        print(f"Error generating AI response: {e}")

def synthesize_speech(call_sid, text):
    """Convert text to speech using Google TTS"""
    try:
        # Configure TTS request
        synthesis_input = texttospeech.SynthesisInput(text=text)
        
        # Build the voice request
        voice = texttospeech.VoiceSelectionParams(
            language_code="en-US",
            ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL
        )
        
        # Select the type of audio file
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3
        )
        
        # Perform the text-to-speech request
        response = tts_client.synthesize_speech(
            input=synthesis_input, voice=voice, audio_config=audio_config
        )
        
        # The response's audio_content is binary
        audio_content = response.audio_content
        
        # Store the audio for playback (in a real system, you'd save this to a file or stream it)
        if call_sid in call_states:
            call_states[call_sid]['audio_response'] = audio_content
        
    except Exception as e:
        print(f"Error synthesizing speech: {e}")

if __name__ == '__main__':
    # Run the Flask app with SocketIO
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)