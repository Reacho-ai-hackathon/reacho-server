import google.generativeai as genai
import os

genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
model = genai.GenerativeModel('models/gemini-1.5-pro-latest')

call_states = None

def set_call_states_ref(ref):
    global call_states
    call_states = ref

class AIResponseHandler:
    """Processes transcripts and generates responses using Gemini"""
    def __init__(self):
        self.model = model

    def generate_response(self, call_sid, transcript, lead_info):
        try:
            context = self._create_context(lead_info)
            prompt = f"{context}\n\nCustomer: '{transcript}'\n\nYou:"
            response = self.model.generate_content(prompt)
            ai_text = response.text
            if call_states and call_sid in call_states:
                call_states[call_sid]['responses'].append(ai_text)
            return ai_text
        except Exception as e:
            return "I'm sorry, I'm having trouble processing that right now. Could you please repeat?"

    def _create_context(self, lead_info):
        name = lead_info.get('name', 'the customer')
        company = lead_info.get('company', '')
        product_interest = lead_info.get('product_interest', '')
        context = f"You are an AI assistant making an outbound call to {name}"
        if company:
            context += f" from {company}"
        context += ". Your goal is to have a natural, helpful conversation."
        if product_interest:
            context += f" The customer has shown interest in {product_interest}."
        context += "\n\nBe conversational, professional, and helpful. Avoid sounding like a script."
        return context