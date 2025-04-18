from google.cloud import texttospeech

tts_client = texttospeech.TextToSpeechClient()

class TextToSpeechService:
    """Uses Google Text-to-Speech to convert AI responses to audio"""
    def __init__(self):
        self.client = tts_client

    def synthesize(self, text):
        try:
            synthesis_input = texttospeech.SynthesisInput(text=text)
            voice = texttospeech.VoiceSelectionParams(
                language_code="en-US",
                ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL
            )
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3
            )
            response = self.client.synthesize_speech(
                input=synthesis_input, voice=voice, audio_config=audio_config
            )
            return response.audio_content
        except Exception as e:
            print(f"Error synthesizing speech: {e}")
            return None