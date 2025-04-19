import asyncio
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

    async def generate_response(self, transcript, lead_info):
        """Generate an AI response based on the transcript and lead information"""
        try:
            # Use asyncio.to_thread for CPU-bound operations
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                self._generate_response_sync,
                transcript,
                lead_info
            )
            return response
        except Exception as e:
            print(f"Error generating AI response: {e}")
            return "I'm sorry, I'm having trouble processing that right now."
    
    def _generate_response_sync(self, transcript, lead_info):
        """Synchronous version of generate_response for use with run_in_executor"""
        try:
            # Create context for the AI
            context = self._create_context(lead_info)
            
            # Combine context and transcript into a prompt
            prompt = f"{context}\n\nCustomer: '{transcript}'\n\nYou:"
            
            # Generate response using Gemini
            response = self.model.generate_content(prompt)
            ai_text = response.text
            
            # Store the response in call_states if available
            call_sid = lead_info.get('call_sid')
            if call_states and call_sid and call_sid in call_states:
                call_states[call_sid]['responses'].append(ai_text)
                
            return ai_text
        except Exception as e:
            print(f"Error in sync AI response generation: {e}")
            return "I'm sorry, I'm having trouble processing that right now."
            
    def _create_context(self, lead_info):
        """Create a context prompt based on lead information"""
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