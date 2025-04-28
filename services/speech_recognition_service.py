
import threading
import queue
import logging
from collections import defaultdict
from google.cloud import speech
import asyncio
from services.utils import get_embedding

logger = logging.getLogger(__name__)

class SpeechRecognitionService:
    def __init__(self):
        self.client = speech.SpeechClient()
        self.audio_queues = defaultdict(queue.Queue)  # thread-safe queues for each call_sid
        self.streaming_threads = {}  # call_sid -> Thread
        self.stop_signals = defaultdict(threading.Event)  # call_sid -> Event

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

    async def add_audio(self, call_sid: str, audio_chunk: bytes):
        # logger.debug(f"[{call_sid}] Queued audio chunk of size {len(audio_chunk)}")
        self.audio_queues[call_sid].put(audio_chunk)

    async def stop_streaming(self, call_sid: str):
        logger.info(f"[{call_sid}] Stopping streaming thread")
        self.stop_signals[call_sid].set()
        self.audio_queues[call_sid].put(None)
        thread = self.streaming_threads.get(call_sid)
        if thread:
            thread.join(timeout=5)
            del self.streaming_threads[call_sid]
        if call_sid in self.audio_queues:
            del self.audio_queues[call_sid]
        if call_sid in self.stop_signals:
            del self.stop_signals[call_sid]

    def _audio_generator(self, call_sid: str, save_audio: bool = False):
        audio_save_path = None
        audio_file = None
        if save_audio:
            import os
            audio_save_dir = os.path.join("tmp_audio", f"audio_debug_{call_sid}")
            os.makedirs(audio_save_dir, exist_ok=True)
            audio_save_path = os.path.join(audio_save_dir, f"raw_audio_{call_sid}.pcm")
            audio_file = open(audio_save_path, "ab")
            logger.info(f"[{call_sid}] Saving raw audio chunks to {audio_save_path}")
        try:
            while not self.stop_signals[call_sid].is_set():
                audio_chunk = self.audio_queues[call_sid].get()
                if audio_chunk is None:
                    break
                if save_audio and audio_file:
                    audio_file.write(audio_chunk)
                yield speech.StreamingRecognizeRequest(audio_content=audio_chunk)
        finally:
            if audio_file:
                audio_file.close()
                logger.info(f"[{call_sid}] Finished saving raw audio to {audio_save_path}")

    def _run_recognizer(self, call_sid: str, transcript_callback, loop):
        try:
            logger.info(f"[{call_sid}] _run_recognizer called")
            requests = self._audio_generator(call_sid, save_audio=False)
            config = self.get_streaming_config()
            logger.info(f"[{call_sid}] requests generator created")
            responses = self.client.streaming_recognize(config=config, requests=requests)
            for response in responses:
                for result in response.results:
                    logger.info(f"[{call_sid}] Result: {result}")
                    if result.is_final and result.alternatives:
                        transcript = result.alternatives[0].transcript.strip()
                        logger.info(f"[{call_sid}] Generated transcript: {transcript}")
                        try:
                            if not transcript:
                                continue
                            transcript_embedding = get_embedding(transcript)
                            # Schedule the async callback in the provided event loop
                            future = asyncio.run_coroutine_threadsafe(transcript_callback(transcript, transcript_embedding), loop)
                            logger.info(f"[{call_sid}] Transcript callback scheduled")
                            result = future.result(timeout=10)
                            logger.info(f"[{call_sid}] Transcript callback completed")
                        except Exception as cb_exc:
                            logger.error(f"[{call_sid}] Error in transcript callback: {cb_exc}", exc_info=True)
        except Exception as e:
            logger.error(f"[{call_sid}] Error in Google STT stream: {e}", exc_info=True)

    async def start_streaming(self, call_sid: str, transcript_callback):
        self.stop_signals[call_sid].clear()
        loop = asyncio.get_running_loop()
        thread = threading.Thread(
            target=self._run_recognizer,
            args=(call_sid, transcript_callback, loop),
            daemon=True,
        )
        self.streaming_threads[call_sid] = thread
        thread.start()

