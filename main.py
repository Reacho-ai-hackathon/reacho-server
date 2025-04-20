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

# @app.on_event("startup")
# async def startup():
#     # await database.connect()
#     # metadata.create_all(engine)
#     logger.info("Application starting up")
#     os.makedirs('logs', exist_ok=True)
#     # asyncio.create_task(call_orchestrator.start_call_processing())
#     # logger.info("Call processing task started")

# @app.on_event("shutdown")
# async def shutdown():
#     # await database.disconnect()
#     logger.info("Application shutting down")
#     print("Shutting down...")

@app.get('/')
async def index():
    logger.info("Root endpoint accessed")
    return "Reacho Outbound Voice AI System (FastAPI)"

@app.post("/upload_csv")
async def upload_csv(file: UploadFile = File(...), background_tasks: BackgroundTasks = None):
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
    
    # Process CSV and start call processing after completion
    logger.info(f"Processing CSV file: {file_path}")
    result = await call_orchestrator.process_csv(file_path)
    logger.info(f"CSV processing result: {result}")
    
    # Use background task to start call processing
    logger.info("Starting call processing")
    if background_tasks:
        logger.info("Using background tasks for call processing")
        background_tasks.add_task(call_orchestrator.start_call_processing)
    else:
        # Since start_call_processing returns a task, we should create a background task
        logger.info("Creating async task for call processing")
        asyncio.create_task(call_orchestrator.start_call_processing())

    logger.info("CSV upload and processing completed successfully")
    return {"status": "success", "message": "File uploaded and processing started."}

# @app.post("/outbound_call")
# async def outbound_call(request: Request):
#     form = await request.form()
#     call_sid = form.get("CallSid")
#     logger.info(f"Outbound call webhook received for call_sid: {call_sid}")
#     response_text = f"Hello! This is AI calling you. How can I assist you today?"
#     response = VoiceResponse()
#     response.say(response_text)
#     # Start streaming audio to websocket
#     ngrok_url = os.getenv("NGROK_URL")
#     logger.info(f"Using ngrok URL: {ngrok_url}")
#     stream_url = f"wss://{ngrok_url.replace('https://','').replace('http://','')}/stream/{call_sid}"
#     logger.info(f"Stream URL created: {stream_url}")
#     connect = Connect()
#     connect.stream(url=stream_url, track="both_tracks")
#     response.append(connect)
#     # # Add Gather to keep call open and listen to speech
#     gather = Gather(input="speech", action="/process_speech", method="POST", speechTimeout="auto")
#     response.append(gather)
#     logger.info(f"Returning TwiML response for call_sid: {call_sid}")
#     logger.info(f"Returning TwiML response for process_speech call_sid: {call_sid}")
#     return Response(content=str(response), media_type="text/xml")


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

    # Check if there's already an active connection for this call
    if call_sid in active_connections:
        logger.warning(f"Existing WebSocket connection found for call_sid: {call_sid}")
        await websocket.close(1000, "Duplicate connection")
        return

    try:
        await websocket.accept()
        logger.info(f"WebSocket connection accepted for call_sid: {call_sid}")
        active_connections[call_sid] = websocket

        # Initialize call state if not exists
        if call_sid not in call_orchestrator.call_states:
            logger.info(f"Creating new call state for call_sid: {call_sid}")
            call_orchestrator.call_states[call_sid] = {
                "status": "connected",
                "start_time": datetime.utcnow().isoformat(),
                "transcript": "",
                "responses": [],
                "lead_info": {"call_sid": call_sid}
            }

        # Process WebSocket messages
        try:
            logger.info(f"Starting WebSocket message loop for call_sid: {call_sid}")
            while True:
                message = await websocket.receive_text()
                data = json.loads(message)
                logger.debug(f"WebSocket message received for call_sid: {call_sid}, event: {data.get('event')}, data: {data}")

                event = data.get("event")

                if event == "connected":
                    # Handle the connected event
                    logger.info(f"WebSocket connected for call_sid: {call_sid}")
                
                elif event == "start":
                    # Handle the start of the media stream
                    logger.info(f"Media stream started for call_sid: {call_sid}")
                
                elif event == "media":
                    # Handle incoming media (audio) data from Twilio
                    payload = data.get("media", {}).get("payload")
                    if payload:
                        try:
                            logger.debug(f"Processing audio payload for call_sid: {call_sid}")
                            audio_chunk = base64.b64decode(payload)
                            transcript = await call_orchestrator.speech_service.process_audio_stream(call_sid, audio_chunk)

                            if transcript:
                                logger.info(f"Transcript received for call_sid: {call_sid}: {transcript}")
                                # Update transcript in call state
                                call_orchestrator.call_states[call_sid]["transcript"] += " " + transcript
                                
                                # Log the transcript
                                await call_orchestrator.data_logger.log_transcript(call_sid, transcript, True)
                                
                                # Generate AI response
                                lead_info = call_orchestrator.call_states[call_sid].get("lead_info", {})
                                ai_response = await call_orchestrator.ai_handler.generate_response(transcript, lead_info)

                                logger.info(f"AI response generated for call_sid: {call_sid}: {ai_response[:50]}..." if len(ai_response) > 50 else f"AI response generated: {ai_response}")
                                
                                # Log the AI response
                                await call_orchestrator.data_logger.log_ai_response(call_sid, ai_response)

                                # Convert response to speech and send back
                                audio_data = await call_orchestrator.tts_service.text_to_speech(ai_response)
                                if audio_data:
                                    await barge_in(websocket, data.get("streamSid"))
                                    await send_audio_to_twilio(websocket, audio_data, data.get("streamSid"))
                                else:
                                    logger.warning(f"No audio data generated for call_sid: {call_sid}")
                        except Exception as e:
                            logger.error(f"Error processing audio for {call_sid}: {e}", exc_info=True)
                            await call_orchestrator.data_logger.log_error('audio_processing', str(e), {'call_sid': call_sid})

                elif event == "dtmf":
                    # Handle DTMF tones
                    dtmf_tones = data.get("dtmf")
                    logger.info(f"DTMF tones detected for call_sid: {call_sid}: {dtmf_tones}")
                    # Process DTMF tones as needed, for example to navigate a menu or trigger actions

                elif event == "stop":
                    # Handle stop event (media stream ended)
                    logger.info(f"Media stream stopped for call_sid: {call_sid}")
                    break
                
                elif event == "mark":
                    # Handle marker events, useful for analytics or logging specific moments
                    marker = data.get("marker")
                    logger.info(f"Marker event received for call_sid: {call_sid}: {marker}")

                else:
                    logger.warning(f"Unknown event type for call_sid: {call_sid}: {event}")

        except Exception as e:
            logger.error(f"Error in WebSocket message processing for {call_sid}: {e}", exc_info=True)
            await call_orchestrator.data_logger.log_error('websocket_processing', str(e), {'call_sid': call_sid})

    except Exception as e:
        logger.error(f"WebSocket connection error for {call_sid}: {e}", exc_info=True)
    finally:
        # Clean up resources
        logger.info(f"Closing WebSocket connection for call_sid: {call_sid}")
        if call_sid in active_connections:
            del active_connections[call_sid]
        if websocket.client_state != WebSocket.DISCONNECTED:
            await websocket.close()
            call_orchestrator.speech_service.buffers.pop(call_sid, None)

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


# @app.websocket("/stream/{call_sid}")
# async def websocket_stream(websocket: WebSocket, call_sid: str):
#     logger.info(f"WebSocket connection requested for call_sid: {call_sid}")
    
#     # Check if there's already an active connection for this call
#     if call_sid in active_connections:
#         logger.warning(f"Existing WebSocket connection found for call_sid: {call_sid}")
#         await websocket.close(1000, "Duplicate connection")
#         return
        
#     try:
#         await websocket.accept()
#         logger.info(f"WebSocket connection accepted for call_sid: {call_sid}")
#         active_connections[call_sid] = websocket
        
#         # Initialize call state if not exists
#         if call_sid not in call_orchestrator.call_states:
#             logger.info(f"Creating new call state for call_sid: {call_sid}")
#             call_orchestrator.call_states[call_sid] = {
#                 "status": "connected",
#                 "start_time": datetime.utcnow().isoformat(),
#                 "transcript": "",
#                 "responses": [],
#                 "lead_info": {"call_sid": call_sid}
#             }
            
#         # Process WebSocket messages
#         try:
#             logger.info(f"Starting WebSocket message loop for call_sid: {call_sid}")
#             while True:
#                 message = await websocket.receive_text()
#                 data = json.loads(message)
#                 logger.debug(f"WebSocket message received for call_sid: {call_sid}, event: {data.get('event')}")
                
#                 # Handle media events (audio processing)
#                 if data.get("event") == "media":
#                     payload = data.get("media", {}).get("payload")
#                     if payload:
#                         try:
#                             logger.debug(f"Processing audio payload for call_sid: {call_sid}")
#                             audio_chunk = base64.b64decode(payload)
#                             transcript = await call_orchestrator.speech_service.process_audio_stream(call_sid, audio_chunk)
                            
#                             if transcript:
#                                 logger.info(f"Transcript received for call_sid: {call_sid}: {transcript}")
#                                 # Update transcript in call state
#                                 call_orchestrator.call_states[call_sid]["transcript"] += " " + transcript
                                
#                                 # Log the transcript
#                                 await call_orchestrator.data_logger.log_transcript(call_sid, transcript, True)
                                
#                                 # Get lead info and generate AI response
#                                 lead_info = call_orchestrator.call_states[call_sid].get("lead_info", {})
#                                 lead_info['call_sid'] = call_sid  # Ensure call_sid is in lead_info
                                
#                                 logger.info(f"Generating AI response for call_sid: {call_sid}")
#                                 ai_response = await call_orchestrator.ai_handler.generate_response(transcript, lead_info)
#                                 logger.info(f"AI response generated for call_sid: {call_sid}: {ai_response[:50]}..." 
#                                             if len(ai_response) > 50 else f"AI response generated: {ai_response}")
                                
#                                 # Log the AI response
#                                 await call_orchestrator.data_logger.log_ai_response(call_sid, ai_response)
                                
#                                 # Convert response to speech and send back
#                                 logger.info(f"Converting response to speech for call_sid: {call_sid}")
#                                 audio_data = await call_orchestrator.tts_service.text_to_speech(ai_response)
#                                 if audio_data:
#                                     logger.info(f"Sending audio response for call_sid: {call_sid}")
#                                     b64_audio = base64.b64encode(audio_data).decode('utf-8')
#                                     twilio_audio_packet = {
#                                         "event": "media",
#                                         "media": {
#                                             "payload": b64_audio
#                                         }
#                                     }

#                                     logger.info(f"Sending audio data from websocket: {twilio_audio_packet}")

#                                     # send it back over WebSocket
#                                     await websocket.send_text(json.dumps(twilio_audio_packet))
#                                     await asyncio.sleep(0.02)


#                                     # await websocket.send_bytes(audio_data)
#                                 else:
#                                     logger.warning(f"No audio data generated for call_sid: {call_sid}")
#                         except Exception as e:
#                             logger.error(f"Error processing audio for {call_sid}: {e}", exc_info=True)
#                             await call_orchestrator.data_logger.log_error('audio_processing', str(e), {'call_sid': call_sid})
                
#                 # Handle call end events
#                 elif data.get("event") == "end":
#                     logger.info(f"Call end event received for call_sid: {call_sid}")
#                     if call_sid in call_orchestrator.call_states:
#                         call_orchestrator.call_states[call_sid]["status"] = "completed"
#                         await call_orchestrator.data_logger.log_call_event(call_sid, "completed")
#                     break
                    
#         except Exception as e:
#             logger.error(f"Error in WebSocket message processing for {call_sid}: {e}", exc_info=True)
#             await call_orchestrator.data_logger.log_error('websocket_processing', str(e), {'call_sid': call_sid})
            
#     except Exception as e:
#         logger.error(f"WebSocket connection error for {call_sid}: {e}", exc_info=True)
#     finally:
#         # Clean up resources
#         logger.info(f"Closing WebSocket connection for call_sid: {call_sid}")
#         if call_sid in active_connections:
#             del active_connections[call_sid]
#         if websocket.client_state != WebSocket.DISCONNECTED:
#             await websocket.close()
#             call_orchestrator.speech_service.buffers.pop(call_sid, None)

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


# @app.post("/process_speech")
# async def process_speech(request: Request):
#     form = await request.form()
#     call_sid = form.get("CallSid")
#     speech_result = form.get("SpeechResult")
#     logger.info(f"Process speech webhook received for call_sid: {call_sid}")
    
#     response = VoiceResponse()
    
#     # # Process the transcript if available from Twilio's speech recognition
#     # if speech_result and call_sid in call_orchestrator.call_states:
#     #     logger.info(f"Speech result from Twilio: {speech_result}")
#     #     # Update transcript in call state
#     #     call_orchestrator.call_states[call_sid]["transcript"] += " " + speech_result
#     #     # Log the transcript
#     #     await call_orchestrator.data_logger.log_transcript(call_sid, speech_result, True)
        
#     #     # Get lead info and generate AI response
#     #     lead_info = call_orchestrator.call_states[call_sid].get("lead_info", {})
#     #     lead_info['call_sid'] = call_sid  # Ensure call_sid is in lead_info
        
#     #     # Generate AI response
#     #     logger.info("Generating AI response for speech result")
#     #     ai_response = await call_orchestrator.ai_handler.generate_response(speech_result, lead_info)
#     #     logger.info(f"AI response generated: {ai_response[:50]}..." if len(ai_response) > 50 else f"AI response generated: {ai_response}")
        
#     #     # Log the AI response
#     #     await call_orchestrator.data_logger.log_ai_response(call_sid, ai_response)
        
#     #     # Say the response
#     #     response.say(ai_response)
#     # elif call_sid in call_orchestrator.call_states:
#     #     # Use last generated response if available
#     #     last_response = call_orchestrator.call_states[call_sid]["responses"][-1] if call_orchestrator.call_states[call_sid]["responses"] else ""
#     #     logger.info(f"Using last response: {last_response[:50]}..." if len(last_response) > 50 else f"Using last response: {last_response}")
#     #     response.say(last_response or "Sorry, I didn't catch that. Could you repeat?")
#     # else:
#     #     logger.warning(f"No call state found for call_sid: {call_sid}")
#     #     response.say("Sorry, I didn't catch that. Could you repeat?")
    
#     # Continue streaming
#     ngrok_url = os.getenv("NGROK_URL")
#     stream_url = f"wss://{ngrok_url.replace('https://','').replace('http://','')}/stream/{call_sid}"
#     connect = Connect()
#     connect.stream(url=stream_url)
#     response.append(connect)
    
#     # Add Gather to keep call open and listen to speech
#     gather = Gather(input="speech", action="/process_speech", method="POST", speechTimeout="auto")
#     response.append(gather)
    
#     logger.info(f"Returning TwiML response for call_sid: {call_sid}")
#     return Response(content=str(response), media_type="text/xml")

if __name__ == "__main__":
    os.makedirs('logs', exist_ok=True)
    os.makedirs('temp_csv', exist_ok=True)
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv('PORT', 8555)))
