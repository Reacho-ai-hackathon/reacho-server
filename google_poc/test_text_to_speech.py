import os
from google.cloud import texttospeech

def main():
    client = texttospeech.TextToSpeechClient()
    synthesis_input = texttospeech.SynthesisInput(text="Hello, This is Reacho ")
    voice = texttospeech.VoiceSelectionParams(
        language_code="en-US",
        ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL
    )
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.LINEAR16
    )
    try:
        response = client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )
        with open("output.wav", "wb") as out:
            out.write(response.audio_content)
        print("Audio content written to output.wav")
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    main()