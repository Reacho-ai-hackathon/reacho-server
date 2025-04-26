# Reacho Outbound Voice AI System

An automated outbound calling system that processes CSV files with lead information and manages calls automatically from start to finish. The system uses Twilio for telephony, Google Speech-to-Text for transcription, Gemini for AI responses, and Google Text-to-Speech for voice synthesis.

## Architecture

The system follows a modular architecture with the following components:

- **Call Orchestrator**: Coordinates the call flow and manages the state of each call
- **Voice Call Service**: Handles Twilio integration and outbound call management
- **Text-to-Speech Service**: Converts AI responses to natural-sounding speech using Google TTS
- **Speech Recognition Service**: Transcribes customer responses using Google Speech-to-Text
- **AI Response Handler**: Processes transcripts and generates appropriate responses using Gemini
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

5. Make sure to add your Twilio phone number to the `.env` file:

   ```
   TWILIO_phno=your_twilio_phno
   ```

## Running the Application

```bash
# python outbound_call_system.py
gunicorn -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker -b 0.0.0.0:5000 outbound_call_system:app
```

The application will start on http://localhost:5000

## Usage

### Uploading Lead Information

1. Prepare a CSV file with lead information. The CSV must include at least a `phno` column. Other recommended columns include:

   - `name`: Customer's name
   - `company`: Customer's company
   - `product_interest`: Products or services the customer is interested in

2. Upload the CSV file using the `/upload_csv` endpoint:

   ```bash
   curl -X POST -F "file=@leads.csv" http://localhost:5000/upload_csv
   ```

   Or use a tool like Postman to upload the file.

3. The system will automatically:
   - Process the CSV file
   - Queue the calls
   - Start making outbound calls
   - Manage the entire conversation flow

### Monitoring Calls

You can monitor active calls using the following API endpoints:

- Get all active calls: `GET /api/calls`
- Get details for a specific call: `GET /api/call/{call_sid}`
- End a specific call: `POST /api/end_call/{call_sid}`

## Call Flow

1. The system reads lead information from the uploaded CSV
2. Calls are queued and processed one by one
3. When a call is answered, the system:
   - Greets the customer using a personalized message
   - Streams the customer's voice to Google Speech-to-Text
   - Transcribes the speech in real-time
   - Generates contextual responses using Gemini AI
   - Converts responses to speech using Google Text-to-Speech
   - Plays the responses back to the customer
4. All call data, transcripts, and outcomes are logged

## Logs

The system maintains detailed logs in the `logs` directory:

- `call_events.log`: Records all call events (initiated, answered, completed, etc.)
- `transcripts.log`: Records all transcribed customer speech
- `ai_responses.log`: Records all AI-generated responses
- `errors.log`: Records any errors that occur during call processing
- Individual call logs: `call_{call_sid}.json` contains complete data for each call

## Development

### Module Details

- **CallOrchestrator**: Manages the state of each call and coordinates the flow between services
- **VoiceCallService**: Handles Twilio integration and outbound call management
- **TextToSpeechService**: Uses Google Text-to-Speech to convert AI responses to audio
- **SpeechRecognitionService**: Uses Google Speech-to-Text for real-time transcription
- **AIResponseHandler**: Processes transcripts and generates responses using Gemini
- **DataLoggingService**: Records call details, transcripts, and outcomes

## License

MIT
