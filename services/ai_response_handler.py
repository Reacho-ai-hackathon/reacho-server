import asyncio
import google.generativeai as genai
import os
import logging
import traceback

# Logger setup
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Or INFO in production

handler = logging.StreamHandler()
formatter = logging.Formatter(
    '[%(asctime)s] [%(levelname)s] %(name)s: %(message)s'
)
handler.setFormatter(formatter)
logger.addHandler(handler)

genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
model = genai.GenerativeModel('models/gemini-1.5-pro-latest')

call_states = None

def set_call_states_ref(ref):
    global call_states
    call_states = ref
    logger.info("Call states reference set.")

class AIResponseHandler:
    """Processes transcripts and generates responses using Gemini"""

    def __init__(self):
        self.model = model
        logger.info("AIResponseHandler initialized.")

    async def generate_response(self, transcript, lead_info):
        """Generate an AI response based on the transcript and lead information"""
        call_sid = lead_info.get('call_sid', 'unknown')
        logger.info(f"[{call_sid}] Received transcript for response: '{transcript}'")

        try:
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                self._generate_response_sync,
                transcript,
                lead_info
            )
            return response
        except Exception as e:
            logger.error(f"[{call_sid}] Async error during AI response: {e}")
            logger.debug(traceback.format_exc())
            return "Sorry, I'm having trouble right now. Let's continue shortly."

    def _generate_response_sync(self, transcript, lead_info):
        call_sid = lead_info.get("call_sid", "unknown")
        try:
            context = self._create_context(lead_info)
            previous_dialogue = self._get_previous_conversation(lead_info, transcript)

            full_prompt = f"""{context}

Here's the conversation so far:
{previous_dialogue}
AI:"""

            logger.debug(f"[{call_sid}] Sending prompt to Gemini:\n{full_prompt[:1000]}...")  # Truncate for logging

            response = self.model.generate_content(full_prompt)
            ai_text = response.text.strip()

            logger.info(f"[{call_sid}] AI generated response: {ai_text}")

            if call_states and call_sid:
                call_states.setdefault(call_sid, {'transcripts': [], 'responses': []})
                call_states[call_sid]['responses'].append(ai_text)

            return ai_text
        except Exception as e:
            logger.error(f"[{call_sid}] Error during sync response generation: {e}")
            logger.debug(traceback.format_exc())
            return "Sorry, I'm having trouble responding. Let's continue."

    def _get_previous_conversation(self, lead_info, latest_input):
        """Builds a chat history-style string from previous exchanges"""
        call_sid = lead_info.get("call_sid", "unknown")
        history = []

        if call_states is not None and call_sid:
            # Initialize call state if missing
            if call_sid not in call_states:
                call_states[call_sid] = {"transcripts": [], "responses": []}
                logger.debug(f"[{call_sid}] Call state initialized.")
            else:
                # Safely initialize missing keys
                call_states[call_sid].setdefault("transcripts", [])
                call_states[call_sid].setdefault("responses", [])
            
            past_responses = call_states[call_sid]["responses"]
            past_transcripts = call_states[call_sid]["transcripts"]

            for human, ai in zip(past_transcripts, past_responses):
                history.append(f"Customer: {human}\nAI: {ai}")

            # Append new customer input
            call_states[call_sid]["transcripts"].append(latest_input)

        history.append(f"Customer: {latest_input}")
        conversation = "\n".join(history[-5:])  # Limit to last 5 exchanges
        logger.debug(f"[{call_sid}] Conversation history:\n{conversation}")
        return conversation

    def _create_context(self, lead_info):
        """Create a more detailed and instructive system context"""
        name = lead_info.get('name', 'the customer')
        company = lead_info.get('company', '')
        product = lead_info.get('product_interest', '')

        context = f"""You are Reacho, a friendly and smart AI voice assistant helping with outbound calls.
You're speaking with {name}{' from ' + company if company else ''}. 
The goal is to engage the customer naturally and assist them regarding {product if product else 'their inquiry'}.

Instructions:
- Be conversational and helpful.
- Never sound robotic or like you're reading a script.
- Ask open-ended questions when possible.
- Adjust tone to match the customer.
- If unsure, ask for clarification kindly.
- Do not drag the conversation unnecessarily stick to 1 to 2 lines.
- If the coustomer is not interested, politely end the conversation.
- If the customer is interested, provide relevant information and ask if they have any questions.
- If customer asks you to stop, then do not response anything unless they ask you to continue."""

        logger.debug(f"Context built: {context}")
        return context
