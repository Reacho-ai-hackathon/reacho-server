import asyncio
import logging
from google.cloud import speech
import os
from collections import defaultdict

# Configure module logger
logger = logging.getLogger(__name__)

speech_client = speech.SpeechClient()

class SpeechRecognitionService:
    """Uses Google Speech-to-Text for real-time transcription"""
    def __init__(self):
        logger.debug("Initializing SpeechRecognitionService")
        self.client = speech_client
        # Add buffer to accumulate audio chunks
        self.buffers = defaultdict(bytearray)  # stores audio buffers per call_sid
        self.min_buffer_size = 16000  # bytes ( ~1.5 seconds (160 * 75 = ~12,000 bytes) of Twilio 8kHz mulaw audio)

    def get_streaming_config(self):
        return speech.StreamingRecognitionConfig(
            config=speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.MULAW,
                sample_rate_hertz=8000,
                language_code="en-US",
                enable_automatic_punctuation=True,
            ),
            interim_results=True,
        )

    # async def process_audio_stream(self, audio_chunk: bytes) -> str | None:
    #     try:
    #         logger.debug(f"Received audio chunk of size: {len(audio_chunk)} bytes")

    #         # Optional: Save raw audio for debugging
    #         debug_audio_path = f"debug_audio_{os.getpid()}.mulaw"
    #         with open(debug_audio_path, "ab") as f:
    #             f.write(audio_chunk)
    #         logger.debug(f"Appended audio to {debug_audio_path}")

    #         if len(audio_chunk) < self.min_buffer_size:
    #             logger.info(f"Not enough audio buffered yet ({len(audio_chunk)} < {self.min_buffer_size})")
    #             return None

    #         config = speech.RecognitionConfig(
    #             encoding=speech.RecognitionConfig.AudioEncoding.MULAW,
    #             sample_rate_hertz=8000,
    #             language_code="en-US",
    #             audio_channel_count=1,
    #         )

    #         audio = speech.RecognitionAudio(content=audio_chunk)

    #         logger.info("Sending audio to Google STT for recognition...")
    #         response = self.client.recognize(config=config, audio=audio)
    #         logger.info(f"STT response received with {len(response.results)} results")

    #         for result in response.results:
    #             if result.alternatives:
    #                 transcript = result.alternatives[0].transcript
    #                 logger.info(f"Transcript: {transcript} (final: {result.is_final})")
    #                 return transcript

    #         logger.warning("STT returned no valid transcript")
    #         return None

    #     except Exception as e:
    #         logger.error(f"Exception in process_audio_stream: {e}", exc_info=True)
    #         return None

    async def process_audio_stream(self, call_sid: str, audio_chunk: bytes) -> str | None:
        try:
            # Append to the per-call buffer
            self.buffers[call_sid] += audio_chunk
            current_size = len(self.buffers[call_sid])

            # Optional: Save for debugging
            with open(f"debug_audio_{call_sid}.mulaw", "ab") as f:
                f.write(audio_chunk)

            # Wait until we have enough data
            if current_size < self.min_buffer_size:
                return None

            logger.info(f"[{call_sid}] Buffer full — sending to STT")

            # Configure Google STT
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.MULAW,
                sample_rate_hertz=8000,
                language_code="en-US",
                audio_channel_count=1,
            )

            audio = speech.RecognitionAudio(content=bytes(self.buffers[call_sid]))

            # Reset the buffer immediately (or keep tail if desired)
            self.buffers[call_sid] = bytearray()

            # Recognize
            response = self.client.recognize(config=config, audio=audio)
            logger.info(f"[{call_sid}] STT returned {len(response.results)} results")

            for result in response.results:
                if result.alternatives:
                    transcript = result.alternatives[0].transcript
                    logger.info(f"[{call_sid}] Final transcript: {transcript}")
                    return transcript

            logger.warning(f"[{call_sid}] STT returned no valid transcript")
            return None

        except Exception as e:
            logger.error(f"[{call_sid}] Error in process_audio_stream: {e}", exc_info=True)
            return None         
    
    def _process_audio_sync(self, audio_chunk):
        try:
            logger.debug(f"Processing accumulated audio of size: {len(audio_chunk)} bytes")
            streaming_config = self.get_streaming_config()

            # Create a proper request generator
            def request_generator():
                # First request contains the config
                yield speech.StreamingRecognizeRequest(
                    streaming_config=streaming_config
                )
                
                # Second request contains the audio
                yield speech.StreamingRecognizeRequest(
                    audio_content=audio_chunk
                )

            responses = self.client.streaming_recognize(request_generator())
            
            # Process responses
            for response in responses:
                logger.debug(f"Got response with {len(response.results)} results")
                if not response.results:
                    continue
                    
                for result in response.results:
                    if not result.alternatives:
                        continue
                        
                    transcript = result.alternatives[0].transcript
                    logger.debug(f"Got transcript: '{transcript}', is_final: {result.is_final}")
                    
                    if result.is_final:
                        return transcript
                        
            logger.debug("No transcript found in responses")
            return None
        except Exception as e:
            logger.error(f"Error in sync audio processing: {e}", exc_info=True)
            return None
