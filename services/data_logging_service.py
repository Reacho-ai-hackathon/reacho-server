import os
import json
from datetime import datetime
import aiofiles

class DataLoggingService:
    """Records call details, transcripts, and outcomes"""
    def __init__(self):
        self.log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'logs')
        os.makedirs(self.log_dir, exist_ok=True)

    async def log_call_event(self, call_sid, event_type, data=None):
        try:
            timestamp = datetime.now().isoformat()
            log_entry = {
                'timestamp': timestamp,
                'call_sid': call_sid,
                'event_type': event_type
            }
            if data:
                log_entry['data'] = data
            async with aiofiles.open(os.path.join(self.log_dir, 'call_events.log'), 'a') as f:
                await f.write(json.dumps(log_entry) + '\n')
        except Exception as e:
            print(f"Error logging call event: {e}")

    async def log_transcript(self, call_sid, transcript, is_final):
        try:
            timestamp = datetime.now().isoformat()
            log_entry = {
                'timestamp': timestamp,
                'call_sid': call_sid,
                'transcript': transcript,
                'is_final': is_final
            }
            async with aiofiles.open(os.path.join(self.log_dir, 'transcripts.log'), 'a') as f:
                await f.write(json.dumps(log_entry) + '\n')
        except Exception as e:
            print(f"Error logging transcript: {e}")

    async def log_ai_response(self, call_sid, response):
        try:
            timestamp = datetime.now().isoformat()
            log_entry = {
                'timestamp': timestamp,
                'call_sid': call_sid,
                'response': response
            }
            async with aiofiles.open(os.path.join(self.log_dir, 'ai_responses.log'), 'a') as f:
                await f.write(json.dumps(log_entry) + '\n')
        except Exception as e:
            print(f"Error logging AI response: {e}")

    async def log_error(self, error_type, error_message, context=None):
        try:
            timestamp = datetime.now().isoformat()
            log_entry = {
                'timestamp': timestamp,
                'error_type': error_type,
                'error_message': error_message
            }
            if context:
                log_entry['context'] = context
            async with aiofiles.open(os.path.join(self.log_dir, 'errors.log'), 'a') as f:
                await f.write(json.dumps(log_entry) + '\n')
        except Exception as e:
            print(f"Error logging error: {e}")

    async def log_call_completion(self, call_sid, call_data):
        try:
            async with aiofiles.open(os.path.join(self.log_dir, f'call_{call_sid}.json'), 'w') as f:
                await f.write(json.dumps(call_data, indent=2))
        except Exception as e:
            print(f"Error logging call completion: {e}")