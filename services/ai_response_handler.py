import asyncio
import google.generativeai as genai
import os
import logging
import traceback
from storage.db_config import get_database
import dotenv
from storage.db_utils import CRUDBase
from storage.models.campaign import Campaign
import re


dotenv.load_dotenv()

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

class CampaignCRUD(CRUDBase[Campaign]):
    def __init__(self):
        super().__init__(Campaign, "campaigns")

class AIResponseHandler:
    """Processes transcripts and generates responses using Gemini"""

    def __init__(self):
        self.model = model
        self.campaign_crud = CampaignCRUD()
        # Define a regex pattern to match unwanted standalone tokens (e.g., punctuation marks)
        self.unwanted_pattern = r'^[\W_]+$'  # Matches tokens that consist of only punctuation or symbols (non-word characters)
        logger.info("AIResponseHandler initialized.")

    async def stream_response(self, transcript, lead_info, role: str = "user"):
        """
        Async generator that yields partial AI responses as soon as they are available (streaming).
        Uses Gemini's async streaming API (generate_content_async with stream=True).
        The 'role' parameter determines the context: 'user' uses full history, 'followup' sends only the follow-up prompt.
        """
        call_sid = lead_info.get('call_sid', 'unknown')
        logger.info(f"[AI_STREAM][{call_sid}] Starting streaming AI response for transcript: '{transcript}' (role={role})")
        try:
            # Build prompt/context based on role
            if role == "followup":
                # Only send the follow-up prompt as context
                prompt = transcript + f"\n{lead_info['name']}" if 'name' in lead_info else transcript
            else:
                # Use full conversation history/context
                context = self._create_context(lead_info)
                previous_dialogue = self._get_previous_conversation(lead_info, transcript)
                prompt = f"""{context}\n\nHere's the conversation so far:\n{previous_dialogue}\nAI:"""

            # transcript_embedding = genai.embed_content(
            #     content=transcript,
            #     model="text-embedding-004",
            #     title="transcript",
            #     output_dimensionality=768,
            #     task_type="RETRIEVAL_DOCUMENT"
            # )
            # logger.debug(f"[AI_STREAM][{call_sid}] Embedded transcript: {transcript_embedding.get('embedding')}")

            partial = ""
            token_count = 0
            response_stream = await self.model.generate_content_async(prompt, stream=True)
            async for chunk in response_stream:
                token = getattr(chunk, 'text', None)

                # Skip tokens that are empty, contain only unwanted characters, or are just whitespace
                # Additionally, allow punctuation when it's part of a sentence (surrounded by letters or numbers)
                if token and not token.isspace():
                    # If the token is only punctuation or symbols (standalone), skip it
                    if re.match(self.unwanted_pattern, token) and len(token) == 1:
                        # If token is a single character and matches unwanted pattern, skip it
                        logger.debug(f"[AI_STREAM][{call_sid}] Skipping standalone invalid token: {token}")
                        continue
                    
                    token_count += 1
                    partial += token
                    
                    # Log the valid token
                    logger.debug(f"[AI_STREAM][{call_sid}] Token {token_count}: {token}")
                    
                    # Yield the valid token
                    yield token
                else:
                    # Log if a token is being skipped (optional)
                    logger.debug(f"[AI_STREAM][{call_sid}] Skipping empty or invalid token: {token}")

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
        logger.debug(f"[{call_sid}] Conversation history:\n{conversation}")
        return conversation

    def _create_context(self, lead_info):
        campaign=lead_info.get('campaign', {})
        logger.info(f"campaign info :{campaign}")
        campaign_name = campaign.name
        campaign_description = campaign.description


        """Create a contextual, adaptive AI prompt based on outreach purpose."""
        name = lead_info.get('name', 'the customer')
        age = lead_info.get('age', '')
        gender = lead_info.get('gender', '')
        email = lead_info.get('email', '')
        organisation = lead_info.get('organisation', '')
        designation = lead_info.get('designation', '')

        base_intro = "You are Reacho, a friendly, helpful, and intelligent AI voice assistant making smart outbound calls"

        instructions_common = """
General Guidelines:
- Keep all replies short and crisp — no more than 1-2 short sentences.
- Speak in a friendly, conversational tone without sounding robotic or overly formal.
- Adapt to the user's tone and language.
- Ask questions only when appropriate and helpful.
- Be kind, especially if the person seems disinterested or confused.
- If the person asks you to stop, end the conversation politely and do not continue.
- Do not perform any bookings or make promises
"""

        context = f"""{base_intro}
        You're speaking with {name}, a potential lead. Here's what we know about them:
        - Name: {name}
        - Age: {age}
        - Gender: {gender}
        - Email: {email}
        - Organisation: {organisation}
        - Designation: {designation}

        Your goal is to gauge their interest in the product—essentially, try to sell it.
        Campaign or Product Details:
        - Name: BrightFuture: Solar panels
        - Description: The BrightFuture Solar Panels campaign is designed to promote the adoption of sustainable solar energy solutions for both residential and commercial properties. The panels, featuring advanced photovoltaic cells with up to 22% efficiency, are durable and built to withstand extreme weather, offering a lifespan of over 25 years. The product comes with a 25-year performance warranty and a 10-year product warranty, ensuring long-term reliability. Residential panels are priced at $250 each, while commercial panels cost $300 each. Installation costs range from $1,500 for residential setups to $5,000 for larger commercial installations. The campaign also highlights available incentives such as a 26% federal tax credit and local rebates that can reduce costs by up to 30%. With average annual savings of $1,200 for residential users and up to $15,000 for businesses, customers can expect a return on investment in as little as 4-8 years. Routine maintenance is minimal, with an annual cost of about $100, and occasional inverter replacement is required every 10-15 years. Overall, the BrightFuture Solar Panels offer an eco-friendly, cost-effective energy solution, helping customers lower their electricity bills while contributing to a cleaner, greener future.

        Based on the campaign details you need to ask follow up questions 

        Determine whether they would be a good lead for the sales team.
    You need to briefly explain about the product specified in the campaign and try to sell the product to them. 

Specific Goals:
- Keep the conversation focused on the product. If they bring up unrelated topics, steer it back gently.
- Introduce the product briefly and naturally.
- Ask a relevant question to assess their interest or needs.
- If they show interest, let them know a team member will reach out soon.
- If they are not interested, thank them kindly and guide the conversation to a polite close.

    {instructions_common}
    """
        logger.debug(f"Context built:\n{context}")
        return context
