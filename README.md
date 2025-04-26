# Reacho Voice AI System

A Python Flask application that receives phone calls using Twilio, streams the caller's voice in real-time to a WebSocket server, transcribes the audio using Google Speech-to-Text, sends the transcript to Gemini (Google's LLM) to generate a response, then uses Google Text-to-Speech to create an audio reply and plays it back to the user.

## Architecture

The system follows a modern event-driven architecture with the following major components:

- **Call Orchestrator**: Coordinates the call flow and manages the state of each call
- **Voice Call Service**: Handles call initiation and telephony operations
- **Text-to-Speech Service**: Converts text scripts to natural-sounding speech
- **Speech Recognition Service**: Transcribes customer responses
- **AI Response Handler**: Processes transcribed responses and generates appropriate follow-ups
- **Data Logging Service**: Records call details, transcripts, and outcomes

## Prerequisites

- Python 3.8+
- Twilio account with a phone number
- Google Cloud Platform account with the following APIs enabled:
  - Speech-to-Text API
  - Text-to-Speech API
  - Gemini API

## Setup

1. Clone the repository

2. Create and activate a virtual environment:

   ```bash
   python -m venv env
   source env/bin/activate  # On Windows: env\Scripts\activate
   ```

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Create a `.env` file based on the `.env.example` template and fill in your credentials:

   ```bash
   cp .env.example .env
   # Edit the .env file with your credentials
   ```

5. Set up Twilio:
   - Configure your Twilio phone number to point to your application's `/call` endpoint
   - For local development, use a tool like ngrok to expose your local server

## Running the Application

```bash
python app.py
```

The application will start on http://localhost:5000

## Usage

1. Call your Twilio phone number
2. Speak to the AI assistant
3. The system will:
   - Stream your voice to the WebSocket server
   - Transcribe your speech using Google Speech-to-Text
   - Generate a response using Gemini
   - Convert the response to speech using Google Text-to-Speech
   - Play the response back to you

## Development

### Component Details

- **Call Orchestrator**: Manages the state of each call and coordinates the flow between services
- **Voice Call Service**: Handles Twilio integration and call management
- **Text-to-Speech Service**: Uses Google Text-to-Speech to convert AI responses to audio
- **Speech Recognition Service**: Uses Google Speech-to-Text for real-time transcription
- **AI Response Handler**: Processes transcripts and generates responses using Gemini

## License

MIT
