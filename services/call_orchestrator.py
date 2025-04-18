import time
import threading
from datetime import datetime
from queue import Queue
from .voice_call_service import VoiceCallService
from .speech_recognition_service import SpeechRecognitionService
from .ai_response_handler import AIResponseHandler
from .text_to_speech_service import TextToSpeechService
from .data_logging_service import DataLoggingService

# These will be set by the main app
call_queue = None
call_states = None
active_connections = None

class CallOrchestrator:
    """Manages the state of each call and coordinates the flow between services"""
    def __init__(self, call_queue_ref, call_states_ref, active_connections_ref):
        global call_queue, call_states, active_connections
        call_queue = call_queue_ref
        call_states = call_states_ref
        active_connections = active_connections_ref
        self.voice_service = VoiceCallService()
        self.speech_recognition = SpeechRecognitionService()
        self.ai_handler = AIResponseHandler()
        self.tts_service = TextToSpeechService()
        self.data_logger = DataLoggingService()

    def process_csv(self, csv_file_path):
        import csv
        try:
            with open(csv_file_path, 'r') as file:
                csv_reader = csv.DictReader(file)
                for row in csv_reader:
                    if 'phone_number' not in row:
                        continue
                    call_queue.put(row)
            return {"status": "success", "message": f"Processed CSV and queued calls"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def start_call_processing(self):
        threading.Thread(target=self._process_call_queue, daemon=True).start()
        return {"status": "success", "message": "Call processing started"}

    def _process_call_queue(self):
        while True:
            if not call_queue.empty():
                lead_info = call_queue.get()
                try:
                    call_sid = self.voice_service.make_call(lead_info)
                    call_states[call_sid] = {
                        'lead_info': lead_info,
                        'transcript': '',
                        'responses': [],
                        'status': 'initiated',
                        'start_time': datetime.now().isoformat()
                    }
                    self.data_logger.log_call_event(call_sid, 'initiated', lead_info)
                except Exception as e:
                    self.data_logger.log_error('call_initiation', str(e), lead_info)
                time.sleep(5)
            else:
                time.sleep(10)

    def handle_call_status_update(self, call_sid, status):
        if call_sid in call_states:
            call_states[call_sid]['status'] = status
            self.data_logger.log_call_event(call_sid, status)
            if status in ['completed', 'failed', 'busy', 'no-answer', 'canceled']:
                if call_sid in active_connections:
                    del active_connections[call_sid]
                call_states[call_sid]['end_time'] = datetime.now().isoformat()
                self.data_logger.log_call_completion(call_sid, call_states[call_sid])
        return {"status": "success"}