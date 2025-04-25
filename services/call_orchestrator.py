import threading
import asyncio
import logging
import aiofiles
from datetime import datetime
from .voice_call_service import VoiceCallService
from .speech_recognition_service import SpeechRecognitionService
from .ai_response_handler import AIResponseHandler
from .text_to_speech_service import TextToSpeechService
from .data_logging_service import DataLoggingService

# Configure module logger
logger = logging.getLogger(__name__)

class CallOrchestrator:
    """Manages the state of each call and coordinates the flow between services"""
    def __init__(self, call_queue_ref, call_states_ref, active_connections_ref):
        logger.info("Initializing CallOrchestrator")
        self.call_queue = call_queue_ref
        self.call_states = call_states_ref
        self.active_connections = active_connections_ref
        self.voice_service = VoiceCallService()
        self.speech_service = SpeechRecognitionService()
        self.ai_handler = AIResponseHandler()
        self.tts_service = TextToSpeechService()
        self.data_logger = DataLoggingService()
        self._processing_task = None
        logger.info("CallOrchestrator initialized successfully")

    async def process_csv(self, csv_file_path):
        import csv
        logger.info(f"Processing CSV file: {csv_file_path}")
        try:
            with open(csv_file_path, 'r') as file:
                csv_reader = csv.DictReader(file)
                count = 0
                for row in csv_reader:
                    if 'phone_number' not in row:
                        logger.warning(f"Skipping row without phone_number: {row}")
                        continue
                    logger.debug(f"Queueing call to: {row['phone_number']}")
                    self.call_queue.put(row)
                    count += 1
            logger.info(f"Successfully processed CSV and queued {count} calls")
            return {"status": "success", "message": f"Processed CSV and queued {count} calls"}
        except Exception as e:
            logger.error(f"Error processing CSV file: {e}", exc_info=True)
            await self.data_logger.log_error('csv_processing', str(e), {'file_path': csv_file_path})
            return {"status": "error", "message": str(e)}

    def start_call_processing(self):
        logger.info("Starting call processing in a new event loop thread")
        thread = threading.Thread(target=lambda: asyncio.run(self._process_call_queue()), daemon=True)
        thread.start()

    async def _process_call_queue(self):
        logger.info("Call queue processing loop started")
        queue_empty_count = 0
        while True:
            if not self.call_queue.empty():
                queue_empty_count = 0  # Reset counter when there are calls
                queue_size = self.call_queue.qsize()
                logger.info(f"Processing next call from queue (remaining: {queue_size})")
                lead_info = self.call_queue.get()
                logger.info(f"Initiating call to: {lead_info.get('phone_number')}")
                try:
                    call_sid = await self.voice_service.make_call(lead_info)
                    logger.info(f"Call initiated successfully with SID: {call_sid}")
                    # Store call_sid in lead_info for reference in other methods
                    lead_info['call_sid'] = call_sid
                    self.call_states[call_sid] = {
                        'lead_info': lead_info,
                        'transcript': '',
                        'responses': [],
                        'status': 'initiated',
                        'start_time': datetime.now().isoformat()
                    }
                    logger.info(f"Call state initialized for SID: {call_sid}")
                    await self.data_logger.log_call_event(call_sid, 'initiated', lead_info)
                except Exception as e:
                    logger.error(f"Error initiating call: {e}", exc_info=True)
                    await self.data_logger.log_error('call_initiation', str(e), lead_info)
                logger.info("Waiting 5 seconds before processing next call")
                await asyncio.sleep(5)
            else:
                logger.debug("Call queue empty, waiting 10 seconds")
                queue_empty_count += 1
                if queue_empty_count >= 10:  # Use >= for safety
                    logger.info("No calls in queue for 10 checks, exiting loop")
                    break
                await asyncio.sleep(10)

    async def handle_call_status_update(self, call_sid, status):
        logger.info(f"Call status update for SID {call_sid}: {status}")
        if call_sid in self.call_states:
            logger.info(f"Updating call state for SID {call_sid} to {status}")
            self.call_states[call_sid]['status'] = status
            await self.data_logger.log_call_event(call_sid, status)
            if status in ['completed', 'failed', 'busy', 'no-answer', 'canceled']:
                logger.info(f"Call {call_sid} ended with status: {status}")
                if call_sid in self.active_connections:
                    logger.info(f"Removing active connection for call {call_sid}")
                    del self.active_connections[call_sid]
                self.call_states[call_sid]['end_time'] = datetime.now().isoformat()
                logger.info(f"Logging call completion for {call_sid}")
                await self.data_logger.log_call_completion(call_sid, self.call_states[call_sid])
        else:
            logger.warning(f"Received status update for unknown call SID: {call_sid}")
        return {"status": "success"}
