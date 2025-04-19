import asyncio
import logging
from google.cloud import speech

# Configure module logger
logger = logging.getLogger(__name__)

speech_client = speech.SpeechClient()

class SpeechRecognitionService:
    """Uses Google Speech-to-Text for real-time transcription"""
    def __init__(self):
        logger.debug("Initializing SpeechRecognitionService")
        self.client = speech_client

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

    async def process_audio_stream(self, audio_chunk):
        logger.debug(f"Processing audio chunk of size: {len(audio_chunk)} bytes")
        try:
            # Use asyncio.to_thread for CPU-bound operations
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None, 
                self._process_audio_sync, 
                audio_chunk
            )
            if result:
                logger.debug(f"Transcription result: {result}")
            return result
        except Exception as e:
            logger.error(f"Error during streaming recognition: {e}", exc_info=True)
            return None
            
    def _process_audio_sync(self, audio_chunk):
        try:
            streaming_config = self.get_streaming_config()

            # Wrap the audio_chunk in StreamingRecognizeRequest
            def request_generator():
                yield speech.StreamingRecognizeRequest(audio_content=audio_chunk)

            responses = self.client.streaming_recognize(streaming_config, request_generator())

            for response in responses:
                if not response.results:
                    continue
                result = response.results[0]
                if not result.alternatives:
                    continue
                transcript = result.alternatives[0].transcript
                if result.is_final:
                    return transcript
            return None
        except Exception as e:
            logger.error(f"Error in sync audio processing: {e}", exc_info=True)
            return None
