import os
from twilio.rest import Client

ngrok_url = os.getenv('NGROK_URL', 'https://3e54-2405-201-c01e-40d3-bc8f-6e8c-9cee-acfb.ngrok-free.app')
twilio_client = Client(
    os.getenv('TWILIO_ACCOUNT_SID'),
    os.getenv('TWILIO_AUTH_TOKEN')
)

class VoiceCallService:
    """Handles Twilio integration and call management"""
    def __init__(self):
        self.client = twilio_client
        self.from_number = os.getenv('TWILIO_PHONE_NUMBER')
        self.callback_url = f"{ngrok_url}/outbound_call"
        self.status_callback = f"{ngrok_url}/call_status"

    def make_call(self, lead_info):
        print(f"Making call to {lead_info['phone_number']}")
        call = self.client.calls.create(
            to=lead_info['phone_number'],
            from_=self.from_number,
            url=self.callback_url,
            status_callback=self.status_callback,
            status_callback_event=['initiated', 'ringing', 'answered', 'completed'],
            status_callback_method='POST'
        )
        return call.sid

    def end_call(self, call_sid):
        try:
            self.client.calls(call_sid).update(status="completed")
            return {"status": "success", "message": f"Call {call_sid} ended"}
        except Exception as e:
            print(f"Error ending call: {e}")
            return {"status": "error", "message": str(e)}