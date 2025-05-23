import asyncio
from google.cloud import texttospeech
import logging
from pydub import AudioSegment
import io

# Configure logger
logger = logging.getLogger(__name__)

tts_client = texttospeech.TextToSpeechClient()

class TextToSpeechService:
    """Uses Google Text-to-Speech to convert AI responses to audio"""
    def __init__(self):
        self.client = tts_client

    async def stream_text_to_speech(self, text, chunk_size=250):
        """
        Async generator that yields audio chunks as soon as each is available.
        Splits text into chunks and streams audio for each chunk.
        """
        logger.info(f"[TTS] Streaming text to speech: {text[:50]}..." if len(text) > 50 else f"[TTS] Streaming text to speech: {text}")
        loop = asyncio.get_running_loop()
        # Split text into sentences or fixed-size chunks for streaming
        import re
        sentences = re.split(r'(?<=[.!?]) +', text)
        buffer = ""
        for sentence in sentences:
            if not sentence.strip():
                continue
            buffer += sentence + " "
            # If buffer is large enough or it's the last sentence, synthesize
            if len(buffer) >= chunk_size or sentence == sentences[-1]:
                raw_audio = await loop.run_in_executor(None, self.synthesize, buffer.strip())
                if not raw_audio:
                    yield None
                else:
                    mulaw_audio = await loop.run_in_executor(None, self.convert_linear16_to_mulaw, raw_audio)
                    yield mulaw_audio
                buffer = ""

    # async def text_to_speech(self, text):
    #     logger.info(f"Converting text to speech: {text[:50]}..." if len(text) > 50 else f"Converting text to speech: {text}")
    #     try:
    #         # Use asyncio.to_thread for CPU-bound operations
    #         loop = asyncio.get_running_loop()
    #         audio_content = await loop.run_in_executor(
    #             None,
    #             self.synthesize,
    #             text
    #         )
    #         logger.info(f"Successfully synthesized speech of size: {len(audio_content) if audio_content else 0} bytes")
    #         return audio_content
    #     except Exception as e:
    #         logger.error(f"Error synthesizing speech: {e}", exc_info=True)
    #         return None

    async def text_to_speech(self, text):
        logger.info(f"Converting text to speech: {text[:50]}..." if len(text) > 50 else f"Converting text to speech: {text}")
        try:
            loop = asyncio.get_running_loop()
            raw_audio = await loop.run_in_executor(None, self.synthesize, text)
            if not raw_audio:
                return None

            logger.info("Converting LINEAR16 to MULAW for Twilio WebSocket")
            mulaw_audio = await loop.run_in_executor(None, self.convert_linear16_to_mulaw, raw_audio)

            return mulaw_audio
        except Exception as e:
            logger.error(f"Error synthesizing or converting audio: {e}", exc_info=True)
            return None

    def convert_linear16_to_mulaw(self, linear_audio):
        try:
            audio_segment = AudioSegment.from_file(
                io.BytesIO(linear_audio),
                format="wav"
            )
            # Convert to 8000Hz, 8-bit, mono
            audio_segment = audio_segment.set_frame_rate(8000).set_sample_width(1).set_channels(1)
            
            out_buffer = io.BytesIO()
            # Correct export format for Twilio compatibility
            audio_segment.export(out_buffer, format="mulaw")
            return out_buffer.getvalue()
        except Exception as e:
            logger.error(f"Failed to convert LINEAR16 to MULAW: {e}", exc_info=True)
            return None

    def synthesize(self, text):
        try:
            logger.debug("Calling Google TTS API")
            input_text = texttospeech.SynthesisInput(text=text)
            voice = texttospeech.VoiceSelectionParams(
                language_code="en-US",
                name="en-US-Chirp-HD-F",  # You can dynamically adjust this
                ssml_gender=texttospeech.SsmlVoiceGender.FEMALE,  # Adjust gender dynamically as needed
            )

            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.LINEAR16,  # Change to LINEAR16 for Twilio compatibility
                sample_rate_hertz=16000,  # Use a standard rate (16kHz for better clarity)
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
