from google.cloud import speech

speech_client = speech.SpeechClient()

class SpeechRecognitionService:
    """Uses Google Speech-to-Text for real-time transcription"""
    def __init__(self):
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

    def process_audio_stream(self, audio_generator):
        try:
            streaming_config = self.get_streaming_config()
            responses = self.client.streaming_recognize(streaming_config, audio_generator)
            for response in responses:
                if not response.results:
                    continue
                result = response.results[0]
                if not result.alternatives:
                    continue
                transcript = result.alternatives[0].transcript
                is_final = result.is_final
                yield (transcript, is_final)
        except Exception as e:
            print(f"Error during streaming recognition: {e}")
            yield (None, None)