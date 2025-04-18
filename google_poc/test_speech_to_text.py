import os
from google.cloud import speech

def main():
    client = speech.SpeechClient()
    audio_file = 'output.wav'  # Place a short WAV file in the same folder for testing
    if not os.path.exists(audio_file):
        print('Please add a sample.wav file to test Speech-to-Text.')
        return
    with open(audio_file, 'rb') as f:
        content = f.read()
    audio = speech.RecognitionAudio(content=content)
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=24000,
        language_code='en-US',
    )
    try:
        response = client.recognize(config=config, audio=audio)
        for result in response.results:
            print('Transcript:', result.alternatives[0].transcript)
    except Exception as e:
        print('Error:', e)

if __name__ == '__main__':
    main()