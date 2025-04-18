# mock_twilio_stream.py

import websocket
import json
import base64
import time
import threading
import os

CALL_SID = 'TEST_CALL_SID_1234'

ngrok_url = os.getenv('NGROK_URL')

print("NGROK_URL:", ngrok_url)
# WS_URL = f"wss://{ngrok_url.replace('https://', '').replace('http://', '')}/stream/{CALL_SID}"
WS_URL = f"http://localhost:5000/stream/{CALL_SID}"

# Simulate silence (or dummy audio) - 160 bytes of silence in MuLaw 8kHz
dummy_audio = base64.b64encode(b'\xff' * 160).decode('utf-8')  # fake silent chunk

def send_audio(ws):
    for i in range(30):  # Send 30 frames = simulate ~3 seconds
        media_msg = {
            "event": "media",
            "media": {
                "payload": dummy_audio
            }
        }
        ws.send(json.dumps(media_msg))
        print(f"[{i}] Sent dummy audio chunk")
        time.sleep(0.1)  # simulate real-time stream

    ws.close()
    print("Closed WebSocket after sending chunks.")

def on_open(ws):
    print("WebSocket opened")
    threading.Thread(target=send_audio, args=(ws,)).start()

def on_message(ws, message):
    print("Server message:", message)

def on_error(ws, error):
    print("WebSocket error:", error)

def on_close(ws, close_status_code, close_msg):
    print("WebSocket closed", close_status_code, close_msg)

if __name__ == "__main__":
    ws = websocket.WebSocketApp(
        WS_URL,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    ws.run_forever()
