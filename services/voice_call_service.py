import os
import logging
from twilio.rest import Client
from storage.models.call import Call, CallCreate
from storage.db_utils import CRUDBase
from datetime import datetime, timezone
from dotenv import load_dotenv
from services.utils import safe_log_doc  # Utility for safe logging of MongoDB docs

load_dotenv()

# Configure module logger
logger = logging.getLogger(__name__)

class CallCRUD(CRUDBase[Call]):
    def __init__(self):
        super().__init__(Call, "calls")

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
        self.from_number = os.getenv('TWILIO_PHONE_NUMBER')
        ngrok_url = os.getenv('NGROK_URL', 'https://f9d7-2405-201-c01e-404e-a4ec-ca60-86bd-e8ce.ngrok-free.app')
        self.callback_url = f"{ngrok_url}/outbound_call"
        self.status_callback = f"{ngrok_url}/call_status"
        self.call_crud = CallCRUD()

        logger.info(f"VoiceCallService initialized with from_number: {self.from_number}")
        logger.info(f"Callback URL: {self.callback_url}")
        logger.info(f"Status callback URL: {self.status_callback}")

    async def make_call(self, lead_info):
        logger.info(f"Making call to {lead_info['phno']}")
        try:
            logger.info(f"From number: {self.from_number}")
            call = self.client.calls.create(
                to=lead_info['phno'],
                from_=self.from_number,
                url=self.callback_url,
                status_callback=self.status_callback,
                status_callback_event=['initiated', 'ringing', 'answered', 'completed'],
                status_callback_method='POST'
            )
            logger.info(f"Call initiated successfully with SID: {call.sid}")

            call_create_obj = CallCreate(
                user_id=lead_info['user_id'],
                call_sid=call.sid,
                stream_sid="",  # Not available at this stage
                phno=lead_info['phno'],
                campaign_id=lead_info['campaign_id'],
                status="initiated",
                call_start_time=datetime.now(timezone.utc),
                call_end_time=None,
                sentiment=None
            )
            # Insert into DB
            call_created = await self.call_crud.create(call_create_obj)
            # Safely log the inserted call document (ObjectId serialization)
            safe_log_doc(call_created.model_dump(), logger, msg_prefix="Call created: ")
            logger.info(f"Call {call_created.id} created successfully")

            return call_created.call_sid
        except Exception as e:
            # If the exception contains a MongoDB document, safely log it
            safe_log_doc({"error": str(e)}, logger, level=logging.ERROR, msg_prefix=f"Error making call to {lead_info['phno']}: ")
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