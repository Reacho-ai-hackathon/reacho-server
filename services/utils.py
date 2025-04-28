import logging
from bson import ObjectId
import google.generativeai as genai
import dotenv
import os
dotenv.load_dotenv()

genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))

def safe_log_doc(doc, logger=None, level=logging.INFO, msg_prefix=None):
    """
    Safely log a MongoDB document or any dict with ObjectId fields.
    Converts ObjectId fields to string for JSON serialization.
    """
    def convert(obj):
        if isinstance(obj, dict):
            return {k: convert(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert(i) for i in obj]
        elif isinstance(obj, ObjectId):
            return str(obj)
        return obj

    safe_doc = convert(doc)
    msg = f"{msg_prefix or ''}{safe_doc}"
    if logger:
        logger.log(level, msg)
    else:
        print(msg)
    return safe_doc

def get_embedding(text, model_name="text-embedding-004"):
    return genai.embed_content(
        content=text,
        model=model_name,
        title="transcript",
        output_dimensionality=768,
        task_type="RETRIEVAL_DOCUMENT"
    )
    

# Define the function
def analyze_overall_sentiment(chunks):
    """
    Analyze the overall sentiment of a chat conversation using Gemini Pro.
    
    Args:
        chunks (list): List of dicts with 'role' and 'content' keys.
        
    Returns:
        str: One of 'Positive', 'Negative', or 'Neutral'
    """
    # Build conversation string
    conversation = "\n".join(f"{chunk['role']}: {chunk['content']}" for chunk in chunks)

    # Create the prompt
    prompt = f"""
Analyze the overall sentiment of the following conversation and respond with only one word: Positive, Negative, or Neutral.

Conversation:
{conversation}

Overall Sentiment:"""

    # Generate the response
    model = genai.GenerativeModel('models/gemini-2.0-flash')
    response = model.generate_content(prompt)
    

    # Clean and return
    return response.text.strip()

# # Example usage
# chunks = [
#     {"role": "SYSTEM", "content": "Introduce yourself to the customer and start the conversation by explaining our services."},
#     {"role": "ASSISTANT", "content": "Hi Vijay, this is Reacho, an AI assistant calling on behalf of [Your Company]..."},
#     {"role": "USER", "content": "Yeah. Yeah."}
# ]

# sentiment = analyze_overall_sentiment(chunks)
# print("Overall Sentiment:", sentiment)