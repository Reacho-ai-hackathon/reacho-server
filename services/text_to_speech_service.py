import io
import re
import logging
import asyncio
from pydub import AudioSegment
from collections import defaultdict
from google.cloud import texttospeech
from typing import List
from services.utils import lang_map, lang_model_map
from google.cloud import translate_v2 as translate

# Configure logger
logger = logging.getLogger(__name__)

tts_client = texttospeech.TextToSpeechClient()

class TextToSpeechService:
    """Uses Google Text-to-Speech to convert AI responses to audio"""
    def __init__(self):
        self.client = tts_client
        self.translate_client = translate.Client()
        self.language_codes = defaultdict(lambda: "en-US")  # Default per call_sid

    def split_sentences_by_language(self, text: str, call_sid: str) -> List[str]:
        """
        Translates and splits the input text into sentences based on the active language's punctuation rules.
        Handles edge cases like punctuation-only strings or no space after punctuation.

        Returns:
            List[str]: A list of sentence strings in the target language.
        """
        text = text.strip()
        if not text:
            logger.warning("[TTS] Empty input text received for sentence splitting.")
            return []
        
        logger.info(f"[TTS] in split sentence by language with call_sid: {call_sid} with self.language_codes[call_sid] as {self.language_codes[call_sid]}")
        language_code = self.language_codes[call_sid]  # e.g., 'hi-IN', 'te-IN', 'en-US'
        target_lang = language_code.split('-')[0]  # 'hi', 'te', or 'en'

        logger.info(f"[TTS] Starting sentence splitting. Original text: '{text}'")
        logger.info(f"[TTS] Target language for translation: '{target_lang}'")

        # Translate text
        try:
            translated = self.translate_client.translate(text, target_language=target_lang)
            translated_text = translated["translatedText"].strip()
            logger.info(f"[TTS] Translated text: '{translated_text}'")
        except Exception as e:
            logger.error(f"[TTS] Translation failed: {e}. Proceeding with original text.")
            translated_text = text

        # Choose sentence split pattern based on language
        if language_code == "hi-IN":
            pattern = r'(?<=[।!?])\s+'
        elif language_code == "te-IN":
            pattern = r'(?<=[।!?])\s+|(?<=[.!?])\s+'
        else:
            pattern = r'(?<=[.!?])\s+'

        # Attempt to split sentences
        try:
            sentences = re.split(pattern, translated_text)
            final_sentences = [s.strip() for s in sentences if s.strip()]
            logger.info(f"[TTS] Split into {len(final_sentences)} sentence(s): {final_sentences}")
            return final_sentences
        except re.error as e:
            logger.error(f"[TTS] Regex error while splitting text: {e}. Returning full text.")
            return [translated_text]

    async def stream_text_to_speech(self, text, call_sid, chunk_size=250):
        """
        Async generator that yields audio chunks as soon as each is available.
        Splits text into chunks and streams audio for each chunk.
        """
        logger.info(f"[TTS] Streaming text to speech: {text[:50]}..." if len(text) > 50 else f"[TTS] Streaming text to speech: {text}")
        loop = asyncio.get_running_loop()
        # Split text into sentences or fixed-size chunks for streaming
        sentences = self.split_sentences_by_language(text, call_sid)
        buffer = ""
        for sentence in sentences:
            if not sentence.strip():
                continue
            buffer += sentence + " "
            # If buffer is large enough or it's the last sentence, synthesize
            if len(buffer) >= chunk_size or sentence == sentences[-1]:
                raw_audio = await loop.run_in_executor(None, self.synthesize, buffer.strip(), call_sid)
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

    def synthesize(self, text, call_sid):
        try:
            logger.debug("Calling Google TTS API")
            input_text = texttospeech.SynthesisInput(text=text)
            logging.info(f"[Text to Speech] active language {self.language_codes[call_sid]} using model: {lang_model_map.get(self.language_codes[call_sid], 'en-US-Chirp-HD-F')}")
            voice = texttospeech.VoiceSelectionParams(
                # language_code="en-US",
                # name="en-US-Chirp-HD-F",  # You can dynamically adjust this
                language_code = self.language_codes[call_sid],
                name = lang_model_map.get(self.language_codes[call_sid], "en-US-Chirp-HD-F"),
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
