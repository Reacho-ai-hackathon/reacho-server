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
                    language_code="en-IN",
                    name="en-IN-Chirp3-HD-Aoede",  # You can dynamically adjust this
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
