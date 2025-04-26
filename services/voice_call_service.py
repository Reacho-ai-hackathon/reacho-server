import os
import logging
from twilio.rest import Client

# Configure module logger
logger = logging.getLogger(__name__)

class VoiceCallService:
    """Handles Twilio integration and call management"""
    def __init__(self):
        logger.info("Initializing VoiceCallService")

        account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        if not account_sid or not auth_token:
            logger.error("Missing Twilio credentials! Please set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN.")
            raise ValueError("Missing Twilio credentials")

        self.client = Client(account_sid, auth_token)
        self.from_number = os.getenv('TWILIO_phno')
        ngrok_url = os.getenv('NGROK_URL', 'https://f9d7-2405-201-c01e-404e-a4ec-ca60-86bd-e8ce.ngrok-free.app')
        self.callback_url = f"{ngrok_url}/outbound_call"
        self.status_callback = f"{ngrok_url}/call_status"

        logger.info(f"VoiceCallService initialized with from_number: {self.from_number}")
        logger.info(f"Callback URL: {self.callback_url}")
        logger.info(f"Status callback URL: {self.status_callback}")

    async def make_call(self, lead_info):
        logger.info(f"Making call to {lead_info['phno']}")
        try:
            call = self.client.calls.create(
                to=lead_info['phno'],
                from_=self.from_number,
                url=self.callback_url,
                status_callback=self.status_callback,
                status_callback_event=['initiated', 'ringing', 'answered', 'completed'],
                status_callback_method='POST'
            )
            logger.info(f"Call initiated successfully with SID: {call.sid}")
            return call.sid
        except Exception as e:
            logger.error(f"Error making call to {lead_info['phno']}: {e}", exc_info=True)
            raise

    async def end_call(self, call_sid):
        logger.info(f"Attempting to end call with SID: {call_sid}")
        try:
            self.client.calls(call_sid).update(status="completed")
            logger.info(f"Call {call_sid} ended successfully")
            return {"status": "success", "message": f"Call {call_sid} ended"}
        except Exception as e:
            logger.error(f"Error ending call {call_sid}: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}