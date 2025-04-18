# Google POC Scripts

This folder contains proof-of-concept scripts for integrating Google Cloud services with the Reacho Outbound Call System.

## Prerequisites

- Python 3.8+
- Google Cloud account with the following APIs enabled:
  - Speech-to-Text API
  - Text-to-Speech API
  - Gemini API
- Service account key JSON file for Speech-to-Text and Text-to-Speech (set `GOOGLE_APPLICATION_CREDENTIALS`)
- API key for Gemini (set `GOOGLE_API_KEY`)

## Setup

1. **Install dependencies:**

   ```bash
   pip3 install -r requirements.txt
   ```

2. **Set environment variables:**

   - For Speech-to-Text and Text-to-Speech:
     ```bash
     export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/service-account-key.json"
     ```
   - For Gemini:
     ```bash
     export GOOGLE_API_KEY="your-gemini-api-key"
     ```

3. **Prepare sample files:**
   - For Speech-to-Text, place a short WAV file named `sample.wav` in this folder.

## Running the Scripts

### 1. Gemini POC

- **File:** `test_gemini.py`
- **Run:**
  ```bash
  python3 test_gemini.py
  ```
- **Expected Output:**
  Gemini should respond with a greeting message.
- **Troubleshooting:**
  - If you see `GOOGLE_API_KEY not set in environment.`, ensure the environment variable is set.
  - If you get authentication errors, verify your API key.

### 2. Speech-to-Text POC

- **File:** `test_speech_to_text.py`
- **Run:**
  ```bash
  python3 test_speech_to_text.py
  ```
- **Expected Output:**
  The transcript of `sample.wav` will be printed.
- **Troubleshooting:**
  - If you see `Please add a sample.wav file to test Speech-to-Text.`, add a WAV file.
  - For credential errors, check `GOOGLE_APPLICATION_CREDENTIALS`.

### 3. Text-to-Speech POC

- **File:** `test_text_to_speech.py`
- **Run:**
  ```bash
  python3 test_text_to_speech.py
  ```
- **Expected Output:**
  An audio file `output.wav` will be created with the spoken message.
- **Troubleshooting:**
  - For credential errors, check `GOOGLE_APPLICATION_CREDENTIALS`.

## Common Issues

- **Missing dependencies:** Run `pip3 install -r requirements.txt`.
- **Authentication errors:** Ensure environment variables are set and credentials are valid.
- **API not enabled:** Enable the required APIs in your Google Cloud Console.

For further help, refer to the official Google Cloud documentation or contact the project maintainer.
