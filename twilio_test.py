import asyncio
import websockets
import base64
import json
import uuid
import wave
from pydub import AudioSegment

# Replace with your local or ngrok WebSocket endpoint
STREAM_ENDPOINT = "ws://localhost:5000/stream/test-call-sid"
STREAM_SID = str(uuid.uuid4())

# Load your test WAV file (must be μ-law 8000Hz mono)
INPUT_FILE = "short-test.wav"

# Convert WAV to mulaw using pydub if needed
def load_mulaw_audio(file_path):
    audio = AudioSegment.from_file(file_path)
    audio = audio.set_frame_rate(8000).set_channels(1).set_sample_width(1)
    return audio.raw_data

# Chunk the audio into 20ms = 160 bytes (for 8kHz μ-law)
def chunk_audio(audio_bytes, chunk_size=160):
    return [audio_bytes[i:i + chunk_size] for i in range(0, len(audio_bytes), chunk_size)]

async def send_media_chunks(uri, audio_chunks):
    async with websockets.connect(uri) as websocket:
        print("[client] Connected to server")

        # Send the start event
        await websocket.send(json.dumps({
            "event": "start",
            "streamSid": STREAM_SID
        }))

        # Simulate real-time stream
        for chunk in audio_chunks:
            await asyncio.sleep(0.02)  # 20ms
            encoded = base64.b64encode(chunk).decode('utf-8')
            await websocket.send(json.dumps({
                "event": "media",
                "streamSid": STREAM_SID,
                "media": {"payload": encoded}
            }))

        # Send stop event
        await websocket.send(json.dumps({
            "event": "stop",
            "streamSid": STREAM_SID
        }))

        print("[client] Stream complete")

async def main():
    audio_bytes = load_mulaw_audio(INPUT_FILE)
    chunks = chunk_audio(audio_bytes)
    await send_media_chunks(STREAM_ENDPOINT, chunks)

if __name__ == "__main__":
    asyncio.run(main())
