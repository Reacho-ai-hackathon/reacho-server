import asyncio
from google.cloud import texttospeech
import logging

# Configure logger
logger = logging.getLogger(__name__)

tts_client = texttospeech.TextToSpeechClient()

class TextToSpeechService:
    """Uses Google Text-to-Speech to convert AI responses to audio"""
    def __init__(self):
        self.client = tts_client

    async def text_to_speech(self, text):
        logger.info(f"Converting text to speech: {text[:50]}..." if len(text) > 50 else f"Converting text to speech: {text}")
        try:
            # Use asyncio.to_thread for CPU-bound operations
            loop = asyncio.get_running_loop()
            audio_content = await loop.run_in_executor(
                None,
                self.synthesize,
                text
            )
            logger.info(f"Successfully synthesized speech of size: {len(audio_content) if audio_content else 0} bytes")
            return audio_content
        except Exception as e:
            logger.error(f"Error synthesizing speech: {e}", exc_info=True)
            return None

    def synthesize(self, text):
        try:
            logger.debug("Calling Google TTS API")
            input_text = texttospeech.SynthesisInput(text=text)
            voice = texttospeech.VoiceSelectionParams(
                language_code="en-US",
                name="en-US-Neural2-F",  # You can dynamically adjust this
                ssml_gender=texttospeech.SsmlVoiceGender.FEMALE,  # Adjust gender dynamically as needed
            )
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3,
                speaking_rate=1.0,  # Adjustable speaking rate if needed
            )
            
            # Get TTS response
            response = self.client.synthesize_speech(
                input=input_text, voice=voice, audio_config=audio_config
            )
            logger.debug("Google TTS API call completed successfully")
            return response.audio_content
        except Exception as e:
            logger.error(f"Error in TTS synthesis: {e}", exc_info=True)
            return None