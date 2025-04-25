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
model = genai.GenerativeModel('models/gemini-2.0-flash')

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

    async def stream_response(self, transcript, lead_info):
        """
        Async generator that yields partial AI responses as soon as they are available (streaming).
        Uses Gemini's async streaming API (generate_content_async with stream=True).
        """
        call_sid = lead_info.get('call_sid', 'unknown')
        logger.info(f"[AI_STREAM][{call_sid}] Starting streaming AI response for transcript: '{transcript}'")
        try:
            context = self._create_context(lead_info)
            previous_dialogue = self._get_previous_conversation(lead_info, transcript)
            full_prompt = f"""{context}\n\nHere's the conversation so far:\n{previous_dialogue}\nAI:"""
            logger.debug(f"[AI_STREAM][{call_sid}] Sending prompt to Gemini (async stream):\n{full_prompt[:1000]}...")

            partial = ""
            token_count = 0
            # Use Gemini's async streaming API
            response_stream = await self.model.generate_content_async(full_prompt, stream=True)
            async for chunk in response_stream:
                token = getattr(chunk, 'text', None)
                if token:
                    token_count += 1
                    partial += token
                    logger.debug(f"[AI_STREAM][{call_sid}] Token {token_count}: {token}")
                    yield token
            logger.info(f"[AI_STREAM][{call_sid}] Streaming response complete. Total tokens: {token_count}. Full response: {partial}")

            # Optionally, save the full response to call_states
            if call_states and call_sid:
                call_states.setdefault(call_sid, {'transcripts': [], 'responses': []})
                call_states[call_sid]['responses'].append(partial)
        except Exception as e:
            logger.error(f"[AI_STREAM][{call_sid}] Error during streaming response generation: {e}")
            logger.debug(traceback.format_exc())
            yield "Sorry, I'm having trouble responding. Let's continue."

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
        conversation = "\n".join(history)  # Limit to last 5 exchanges
        # conversation = "\n".join(history[-5:])  # Limit to last 5 exchanges
        logger.debug(f"[{call_sid}] Conversation history:\n{conversation}")
        return conversation

    def _create_context(self, lead_info):
        """Create a contextual, adaptive AI prompt based on outreach purpose."""
        name = lead_info.get('name', 'the customer')
        company = lead_info.get('company', '')
        product = lead_info.get('product_interest', 'our services')
        use_case = lead_info.get('use_case', 'lead_qualification')  # e.g. 'event_reminder', 'feedback', etc.

        base_intro = "You are Reacho, a friendly, helpful, and intelligent AI voice assistant making smart outbound calls"

        instructions_common = """
    General Guidelines:
    - Speak in a natural, conversational tone. Keep it warm and human-like.
    - Use 1-2 short, clear sentences per reply. Don't be robotic or overly scripted.
    - Be adaptive to the user's tone and language.
    - Ask questions only when appropriate and helpful.
    - Be kind, especially if the person seems disinterested or confused.
    - If the person asks you to stop, end politely and don't continue.
    """

        # Context depending on use case
        if use_case == 'lead_qualification':
            context = f"""{base_intro}
    You're speaking with {name}, and your goal is to gauge their interest in {product} and determine if they'd be a good lead for the sales team.

    Specific Goals:
    - Introduce the product briefly and naturally.
    - Ask a question to assess interest or need.
    - If they show interest, offer to send more info or schedule a call.
    - If not interested, thank them kindly and end the call.

    {instructions_common}
    """
        elif use_case == 'event_reminder':
            context = f"""{base_intro}
    You're reminding {name} about an upcoming event they're registered for. Confirm their attendance and answer any simple questions they might have.

    Specific Goals:
    - Gently confirm attendance.
    - Offer helpful details (e.g. time, location, link).
    - If they say they can't attend, thank them politely.

    {instructions_common}
    """
        elif use_case == 'feedback':
            context = f"""{base_intro}
    You're calling {name} to gather quick feedback about a recent experience or event.

    Specific Goals:
    - Ask a light, open-ended question (e.g. “How was your experience?”).
    - Be encouraging and positive.
    - Thank them for sharing, and let them know their input matters.

    {instructions_common}
    """
        else:
            # Fallback general use-case
            context = f"""{base_intro}
    You're calling {name} regarding {product}.

    {instructions_common}
    """

        logger.debug(f"Context built:\n{context}")
        return context
