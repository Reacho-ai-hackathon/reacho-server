import asyncio
import logging
from google.cloud import speech
import io

# Configure module logger
logger = logging.getLogger(__name__)

speech_client = speech.SpeechClient()

class SpeechRecognitionService:
    """Uses Google Speech-to-Text for real-time transcription"""
    def __init__(self):
        logger.debug("Initializing SpeechRecognitionService")
        self.client = speech_client
        # Add buffer to accumulate audio chunks
        self.audio_buffer = bytearray()
        self.min_buffer_size = 4000  # Minimum buffer size before processing (4KB)

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
            # Add chunk to buffer
            self.audio_buffer.extend(audio_chunk)
            
            # Only process if we have enough audio data
            if len(self.audio_buffer) < self.min_buffer_size:
                logger.debug(f"Buffer size: {len(self.audio_buffer)} bytes - waiting for more audio")
                return None
                
            # Use asyncio.to_thread for CPU-bound operations
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None, 
                self._process_audio_sync, 
                bytes(self.audio_buffer)
            )
            
            # Clear buffer after processing
            self.audio_buffer = bytearray()
            
            if result:
                logger.info(f"Transcription result: {result}")
            return result
        except Exception as e:
            logger.error(f"Error during streaming recognition: {e}", exc_info=True)
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
