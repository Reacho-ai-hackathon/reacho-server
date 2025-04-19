import os
import json
import base64
import shutil  # Import shutil for file operations
from datetime import datetime
from queue import Queue
from werkzeug.utils import secure_filename
from fastapi import FastAPI, WebSocket, Request, Response, UploadFile, File # Import UploadFile and File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from twilio.twiml.voice_response import VoiceResponse, Gather
from twilio.rest import Client
from dotenv import load_dotenv
from services.call_orchestrator import CallOrchestrator
import aiofiles # Import aiofiles for async file operations

# Load environment variables
load_dotenv()

app = FastAPI(title="Reacho Voice AI System")

# Initialize Twilio client
twilio_client = Client(
    os.getenv('TWILIO_ACCOUNT_SID'),
    os.getenv('TWILIO_AUTH_TOKEN')
)

# Initialize core components
call_queue = Queue()
call_states = {}
active_connections = {}
call_orchestrator = CallOrchestrator(
    call_queue,
    call_states,
    active_connections
)

@app.get('/')
async def index():
    return "Reacho Outbound Voice AI System (FastAPI)"

@app.post('/upload_csv')
async def upload_csv(file: UploadFile = File(...)): # Use FastAPI's File parameter
    if not file:
        return JSONResponse({"status": "error", "message": "No file uploaded"}, status_code=400)

    if not file.filename:
        return JSONResponse({"status": "error", "message": "No selected file"}, status_code=400)

    if not file.filename.endswith('.csv'):
        return JSONResponse({"status": "error", "message": "File must be a CSV"}, status_code=400)

    temp_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'temp_csv')
    os.makedirs(temp_path, exist_ok=True)
    # Use secure_filename to prevent directory traversal issues
    safe_filename = secure_filename(file.filename)
    file_path = os.path.join(temp_path, safe_filename)

    try:
        # Asynchronously read the file content and write it to the destination
        async with aiofiles.open(file_path, 'wb') as out_file:
            while content := await file.read(1024 * 1024):  # Read file in chunks (e.g., 1MB)
                await out_file.write(content)
        print(f"File saved successfully to: {file_path}")
    except Exception as e:
        print(f"Error saving file: {e}")
        return JSONResponse({"status": "error", "message": f"Could not save file: {e}"}, status_code=500)
    finally:
        # Ensure the UploadFile is closed
        await file.close()

    # Process the CSV file
    result = call_orchestrator.process_csv(file_path)

    # Start call processing if not already running
    call_orchestrator.start_call_processing()

    return JSONResponse(result)

@app.post('/outbound_call')
async def outbound_call(request: Request):
    form_data = await request.form()
    call_sid = form_data.get('CallSid')
    
    response = VoiceResponse()
    if call_sid in call_states:
        # Get lead information
        lead_info = call_states[call_sid]['lead_info']
        name = lead_info.get('name', '')
        
        # Initial greeting
        greeting = f"Hello{', ' + name if name else ''}! This is Reacho AI calling. How are you today?"
        response.say(greeting)
        
        # Start streaming
        response.append(await start_streaming(call_sid))
    else:
        # Fallback if call state not found
        response.say("Hello! This is Reacho AI calling. How are you today?")
        response.append(await start_streaming(call_sid))
    
    return Response(content=str(response), media_type='text/xml')

async def start_streaming(call_sid: str):
    """Configure Twilio to stream audio to our WebSocket"""
    ngrok_url = os.getenv('NGROK_URL', '')
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

@app.post('/process_speech')
async def process_speech(request: Request):
    """Process speech after Gather completes"""
    form_data = await request.form()
    call_sid = form_data.get('CallSid')
    response = VoiceResponse()
    
    if call_sid in call_states and call_states[call_sid].get('responses', []):
        # Get the latest AI response
        ai_response = call_states[call_sid]['responses'][-1]
        response.say(ai_response)
    else:
        response.say("I'm sorry, I didn't catch that. Could you please repeat?")
    
    # Continue streaming
    response.append(await start_streaming(call_sid))
    
    return Response(content=str(response), media_type='text/xml')

@app.post('/stream_status')
async def stream_status(request: Request):
    """Handle stream status updates from Twilio"""
    form_data = await request.form()
    print(">>> Stream status update:", dict(form_data))
    return Response(content="", media_type='text/plain')

@app.post('/call_status')
async def call_status(request: Request):
    """Handle call status updates from Twilio"""
    form_data = await request.form()
    call_sid = form_data.get('CallSid')
    call_status = form_data.get('CallStatus')
    
    # Update call status
    result = await call_orchestrator.handle_call_status_update(call_sid, call_status)
    
    return JSONResponse(result)

@app.websocket('/stream/{call_sid}')
async def websocket_stream(websocket: WebSocket, call_sid: str):
    print(f"WebSocket connected for call_sid: {call_sid}")
    await websocket.accept()
    active_connections[call_sid] = websocket
    
    # Initialize call state if it doesn't exist
    if call_sid not in call_states:
        call_states[call_sid] = {
            'status': 'connected',
            'start_time': datetime.now().isoformat(),
            'transcript': '',
            'responses': [],
            'lead_info': {}
        }
    
    try:
        while True:
            message = await websocket.receive_text()
            data = json.loads(message)
            
            if data.get('event') == 'media':
                payload = data.get('media', {}).get('payload')
                if payload:
                    audio_chunk = base64.b64decode(payload)
                    
                    # Process audio stream through speech recognition
                    transcript = await call_orchestrator.speech_service.process_audio_stream(audio_chunk)
                    
                    if transcript:
                        # Update transcript in call state
                        call_states[call_sid]['transcript'] = transcript
                        
                        # Get lead information
                        lead_info = call_states[call_sid].get('lead_info', {})
                        
                        # Generate AI response
                        ai_response = await call_orchestrator.ai_handler.generate_response(transcript, lead_info)
                        
                        # Store the response
                        if 'responses' not in call_states[call_sid]:
                            call_states[call_sid]['responses'] = []
                        call_states[call_sid]['responses'].append(ai_response)
                        
                        # Convert to speech and send back
                        audio_data = await call_orchestrator.tts_service.text_to_speech(ai_response)
                        if audio_data:
                            await websocket.send_bytes(audio_data)
    except Exception as e:
        print(f"WebSocket error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print(f"WebSocket closing for call_sid: {call_sid}")
        if call_sid in active_connections:
            del active_connections[call_sid]

# Preserve other existing route handlers with FastAPI syntax

@app.get('/api/calls')
async def get_active_calls():
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
    
    return JSONResponse(active_calls)

@app.post('/api/end_call/{call_sid}')
async def end_call(call_sid: str):
    if call_sid in call_states:
        result = call_orchestrator.voice_service.end_call(call_sid)
        return result
    return JSONResponse({"status": "error", "message": "Call not found"}, status_code=404)

@app.get('/api/health')
async def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    os.makedirs('logs', exist_ok=True)
    os.makedirs('temp_csv', exist_ok=True)
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv('PORT', 8000)))