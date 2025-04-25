import os
import json
import uuid
import base64
import logging
from datetime import datetime
from queue import Queue
from fastapi import FastAPI, WebSocket, Request, UploadFile, File, BackgroundTasks
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
import aiofiles
import asyncio
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Connect, Stream, Gather
from services.call_orchestrator import CallOrchestrator
from dotenv import load_dotenv

load_dotenv()

# Configure logging
import logging
import os

# Add this at the beginning of your file
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join('logs', 'debug.log'))
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Reacho Voice AI System")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    logger.info("Root endpoint accessed")
    return "Reacho Outbound Voice AI System (FastAPI)"

@app.post("/upload_csv")
async def upload_csv(file: UploadFile = File(...)):
    logger.info(f"CSV upload requested: {file.filename}")
    
    if not file.filename.endswith(".csv"):
        logger.warning(f"Invalid file type uploaded: {file.filename}")
        return JSONResponse({"status": "error", "message": "Only CSV files are accepted."}, status_code=400)
    
    temp_dir = "temp_csv"
    os.makedirs(temp_dir, exist_ok=True)
    safe_filename = file.filename.replace(" ", "_")
    file_path = os.path.join(temp_dir, safe_filename)
    
    try:
        logger.info(f"Saving uploaded file to {file_path}")
        async with aiofiles.open(file_path, "wb") as out_file:
            while content := await file.read(1024 * 1024):
                await out_file.write(content)
    finally:
        await file.close()

    # Process CSV and then start call processing directly
    logger.info(f"Processing CSV file: {file_path}")
    result = await call_orchestrator.process_csv(file_path)
    logger.info(f"CSV processing result: {result}")

    logger.info("Starting call processing synchronously")
    call_orchestrator.start_call_processing()  # Now synchronous

    logger.info("CSV upload and processing completed successfully")
    return {"status": "success", "message": "File uploaded and processing completed."}



@app.post("/outbound_call")
async def outbound_call(request: Request):
    form = await request.form()
    call_sid = form.get("CallSid")
    logger.info(f"Outbound call webhook received for call_sid: {call_sid}")

    ngrok_url = os.getenv("NGROK_URL")
    stream_url = f"wss://{ngrok_url.replace('https://','').replace('http://','')}/stream/{call_sid}"
    logger.info(f"Stream URL: {stream_url}")

    response = VoiceResponse()

    connect = Connect()
    connect.stream(url=stream_url)
    response.append(connect)

    return Response(content=str(response), media_type="text/xml")



@app.post("/call_status")
async def call_status(request: Request):
    form = await request.form()
    call_sid = form.get("CallSid")
    call_status = form.get("CallStatus")
    logger.info(f"Call status update received: call_sid={call_sid}, status={call_status}")
    result = await call_orchestrator.handle_call_status_update(call_sid, call_status)
    logger.info(f"Call status update result: {result}")
    return JSONResponse(result)

@app.websocket("/stream/{call_sid}")
async def websocket_stream(websocket: WebSocket, call_sid: str):
    logger.info(f"WebSocket connection requested for call_sid: {call_sid}")

    if call_sid in active_connections:
        logger.warning(f"Existing WebSocket connection for call_sid: {call_sid}")
        await websocket.close(1000, "Duplicate connection")
        return

    await websocket.accept()
    logger.info(f"WebSocket accepted for call_sid: {call_sid}")
    active_connections[call_sid] = websocket

    stream_sid = None
    is_tts_active = False

    # Initialize state if not already done
    if call_sid not in call_orchestrator.call_states:
        call_orchestrator.call_states[call_sid] = {
            "status": "connected",
            "start_time": datetime.utcnow().isoformat(),
            "transcript": "",
            "responses": [],
            "lead_info": {"call_sid": call_sid}
        }

    # Transcript callback
    async def on_transcript(transcript: str):
        nonlocal is_tts_active
        logger.info(f"Transcription received: {transcript}")

        # If there is ongoing TTS, send the "clear" event to stop it
        if is_tts_active:
            await barge_in(websocket, stream_sid)
            logger.info("Sent clear event to stop ongoing TTS.")
            is_tts_active = False  # Reset TTS flag

        # Process transcription immediately
        call_orchestrator.call_states[call_sid]["transcript"] += " " + transcript
        await call_orchestrator.data_logger.log_transcript(call_sid, transcript, True)

        lead_info = call_orchestrator.call_states[call_sid]["lead_info"]
        ai_response = await call_orchestrator.ai_handler.generate_response(transcript, lead_info)

        # Start TTS for AI response
        audio_data = await call_orchestrator.tts_service.text_to_speech(ai_response)
        if audio_data:
            is_tts_active = True
            await send_audio_to_twilio(websocket, audio_data, stream_sid)

    # Start STT streaming task
    task = asyncio.create_task(call_orchestrator.speech_service.start_streaming(call_sid, on_transcript))

    try:
        while True:
            message = await websocket.receive_text()
            data = json.loads(message)
            event = data.get("event")

            if event == "connected":
                logger.info(f"WebSocket connected for {call_sid}")

            elif event == "start":
                stream_sid = data.get("streamSid")
                logger.info(f"Stream started for {call_sid}")
                lead_info = call_orchestrator.call_states[call_sid].get("lead_info", {})
                intro = await call_orchestrator.ai_handler.generate_response("Introduce yourself to the customer and start the conversation", lead_info)
                audio_data = await call_orchestrator.tts_service.text_to_speech(intro)
                if audio_data:
                    await send_audio_to_twilio(websocket, audio_data, stream_sid)

            elif event == "media":
                payload = data.get("media", {}).get("payload")
                if payload:
                    audio_chunk = base64.b64decode(payload)
                    await call_orchestrator.speech_service.add_audio(call_sid, audio_chunk)

            elif event == "dtmf":
                logger.info(f"DTMF detected for {call_sid}: {data.get('dtmf')}")

            elif event == "mark":
                logger.info(f"Marker received for {call_sid}: {data.get('marker')}")

            elif event == "stop":
                logger.info(f"Stopping media stream for {call_sid}")
                break

            else:
                logger.warning(f"Unhandled event for {call_sid}: {event}")

    except Exception as e:
        logger.error(f"WebSocket error for {call_sid}: {e}", exc_info=True)

    finally:
        await call_orchestrator.speech_service.stop_streaming(call_sid)
        await websocket.close()
        if call_sid in active_connections:
            del active_connections[call_sid]
        logger.info(f"Closed WebSocket for {call_sid}")


async def send_audio_to_twilio(websocket, audio_data: bytes, stream_sid: str):
    logger.info(f"Sending audio data to Twilio for streamSid: {stream_sid}")
    # Encode raw audio (already in mulaw/8000) into base64 string
    audio_b64 = base64.b64encode(audio_data).decode('utf-8')

    # Send the media message to Twilio
    media_msg = {
        "event": "media",
        "streamSid": stream_sid,
        "media": {
            "payload": audio_b64
        }
    }

    await websocket.send_text(json.dumps(media_msg))

    # Generate a unique marker name
    mark_name = str(uuid.uuid4())

    # Send the mark message immediately after media to track when it's done playing
    mark_msg = {
        "event": "mark",
        "streamSid": stream_sid,
        "mark": {
            "name": mark_name
        }
    }

    await websocket.send_text(json.dumps(mark_msg))

async def barge_in(websocket, stream_sid: str):
    # Send a barge-in message to Twilio
    logger.info(f"Sending barge-in message for streamSid: {stream_sid}")
    barge_in_msg = {
        "event": "clear",
        "streamSid": stream_sid,
    }
    await websocket.send_text(json.dumps(barge_in_msg))

@app.get('/api/health')
async def health_check():
    return {"status": "ok"}


@app.on_event("startup")
async def startup():
    logger.info("Application starting up")
    # Create necessary directories
    os.makedirs('logs', exist_ok=True)
    os.makedirs('temp_csv', exist_ok=True)
    
    # Set up references between components
    from services.ai_response_handler import set_call_states_ref
    set_call_states_ref(call_states)
    
    logger.info("Application startup complete")

@app.on_event("shutdown")
async def shutdown():
    logger.info("Application shutting down")
    # Close any active connections
    for call_sid, websocket in active_connections.items():
        try:
            await websocket.close(1000, "Server shutting down")
            logger.info(f"Closed WebSocket connection for call_sid: {call_sid}")
        except Exception as e:
            logger.error(f"Error closing WebSocket for {call_sid}: {e}")
    
    # Log final call states
    for call_sid, state in call_states.items():
        if state.get('status') != 'completed':
            try:
                state['status'] = 'interrupted'
                state['end_time'] = datetime.utcnow().isoformat()
                await call_orchestrator.data_logger.log_call_completion(call_sid, state)
            except Exception as e:
                logger.error(f"Error logging final state for call {call_sid}: {e}")
    
    logger.info("Shutdown complete")

if __name__ == "__main__":
    os.makedirs('logs', exist_ok=True)
    os.makedirs('temp_csv', exist_ok=True)
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv('PORT', 8555)))
