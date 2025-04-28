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
    