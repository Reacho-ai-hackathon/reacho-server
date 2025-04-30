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
def analyze_conversation(chunks):
    """
    Analyze the overall sentiment and summarize a chat conversation using Gemini Pro.

    Args:
        chunks (list): List of dicts with 'role' and 'content' keys.

    Returns:
        dict: {
            'sentiment': 'Positive' | 'Negative' | 'Neutral',
            'summary': '...'
        }
    """
    # Build conversation string
    conversation = "\n".join(f"{chunk['role']}: {chunk['content']}" for chunk in chunks)

    # Create the combined prompt
    prompt = f"""
Analyze the following conversation and provide:
1. Overall Sentiment (just one word: Positive, Negative, or Neutral)
2. A brief summary (4-5 sentences)

Format your response like this:
Sentiment: <Sentiment>
Summary: <Summary text>

Conversation:
{conversation}
"""

    # Generate the response
    model = genai.GenerativeModel('models/gemini-2.0-flash')
    response = model.generate_content(prompt)

    # Parse output
    output = response.text.strip()
    sentiment = ""
    summary = ""

    for line in output.splitlines():
        if line.strip().lower().startswith("sentiment:"):
            sentiment = line.split(":", 1)[1].strip()
        elif line.strip().lower().startswith("summary:"):
            summary = line.split(":", 1)[1].strip()
        elif summary and not line.strip().startswith("Sentiment:"):
            summary += " " + line.strip()

    return {
        "sentiment": sentiment,
        "summary": summary
    }


# Example usage
# chunks = [
#     {"role": "SYSTEM", "content": "Introduce yourself to the customer and start the conversation by explaining our services."},
#     {"role": "ASSISTANT", "content": "Hi Vijay, this is Reacho, an AI assistant calling on behalf of [Your Company]..."},
#     {"role": "USER", "content": "Yeah. Yeah."}
# ]

# result = analyze_conversation(chunks)
# print("Overall Sentiment:", result["sentiment"])
# print("Conversation Summary:", result["summary"])


LANGUAGE_TRIGGERS = {
    "english": [
        "english", "इंग्लिश", "इंगलिश", "इंग्लीश", "ఇంగ్లీష్", "ఇంగ్లిష్", "ఆంగ్లం", "अंग्रेजी", "ఇంగ్లీషులో", "अंग्रेज़ी",
        "angrezi", "anglish", "englisch", "anglais", "engleski", "anglic", "english language", 
        "angragi", "angrezī", "angrezī bhāṣā", "angrezī bāṣā"
    ],
    "hindi": [
        "hindi", "हिंदी", "हिन्दी", "हिंदुस्तानी", "हिंदी में", "हिंदी भाषा", "హిందీలో", "హిందీ", "హిందీభాష", "హిందీ భాష",
        "हिन्दी बोलिए", "हिन्दी साहित्य", "hindustani", "hindī", "hindī bhasha", 
        "hindī bhāṣā", "hindī zabān", "hindī bhāṣā boliye", "hindī bhaṣā"
    ],
    "telugu": [
        "telugu", "तेलुगु", "తెలుగు", "తెలుగు లో", "తెలుగు భాష", "टेलुगु", "तेलुगू",
        "తేలుగు", "telugu bhasha", "teluḍu", "teḷuḍu", "telugulo", "teḷugu bhāṣā", 
        "telugī", "telugu language", "telugu vaibhāvamu"
    ],
}

lang_map = {
    "english": "en-US",
    "hindi": "hi-IN",
    "telugu": "te-IN",
}

lang_model_map = {
    "en-US": "en-US-Chirp-HD-F",
    "en-IN": "en-US-Chirp-HD-F",
    # "en-IN": "en-IN-Chirp3-HD-Erinome",
    "hi-IN": "hi-IN-Chirp3-HD-Leda",
    "te-IN": "te-IN-Chirp3-HD-Aoede",
}

def detect_language_switch_intent(transcript: str) -> str | None:
    transcript = transcript.lower()

    # Phrase-based matching, soft pattern search
    for lang, keywords in LANGUAGE_TRIGGERS.items():
        for keyword in keywords:
            # print(f"keyword in transcript {keyword}, {transcript}: {keyword in transcript}")
            if (
                keyword in transcript and
                any(
                    phrase in transcript
                    for phrase in [
                            # English
                            "talk in", "speak in", "can we talk", "can we speak", "let's talk in", "let's speak in",
                            "please speak in", "we should talk in", "let's use", "use", "language", "switch to", "change to",
                            
                            # Hindi Phrases (Direct or Transliteration)
                            "बात करें", "बात करो", "बोलो", "बोल", "बात करना", "हिंदी में बात करें", "हिंदी में बोलें", "हिंदी में बोलो", "टेलुगु", "बात कर", "बातचीत", "तेलुगु शुरू",
                            "हिंदी बोलो", "हिंदी में बात करो", "हिंदी में बात करें", "हिंदी बोलने की कोशिश करो", "हिंदी में बात करने के लिए", "अंग्रेजी", "इंग्लिश", "इंगलिश", "इंग्लीश", "ఇంగ్లీష్", "ఇంగ్లిష్", "ఆంగ్లం",
                            
                            # Telugu Phrases (Direct or Transliteration)
                            "మాట్లాడండి", "మాట్లాడాం", "మాట్లాడ", "తెలుగు లో మాట్లాడ", "తెలుగులో మాట్లాడ", "తెలుగు మాట్లాడ",
                            "తెలుగు మాట్లాడండి", "తెలుగు మాటలు", "తెలుగు మాట్లాడాలా", "తెలుగులో మాట్లాడవచ్చా", "తెలుగులో మాట్లాడుకుందాం",
                            "తెలుగులో మాట్లాడండి", "తెలుగులో మాట్లాడతారా?", "తెలుగు మాట్లాడదాం", "హిందీలో మాట్లాడండి", "హిందీ స్టార్ట్",

                            # General variations in Hindi/English for switching
                            "can we speak", "can we switch to", "let's change to", "let's switch to", "can you speak in", "can we use", "change language",
                            "switch language", "let's go to", "use in", "talk in", "language change", "speak in", "start speaking in", "can we continue in hindi",
                            "can we continue in telugu",
                            
                            # More common variations
                            "talk in the", "speak in the", "can we talk", "can we talk in", "can you speak",
                            "speak in this language", "speak in a new language", "let's go to", "go to language", "change to language",
                            
                            # Adding other phrases for "switching" or "using" a language
                            "switch to", "speak", "let's use", "use in", "language change", "language switch", "switch over to", "speak now",
                            "talk now", "language preference", "can we talk in", "let’s speak", "let’s change the language to",
                            "start talking in", "switch over to", "switch over",  "let's change it to", "switch language to",
                            "speak using", "start using", "can you talk in", "can you speak in", "talk now in", "let's go to the language",
                            "speak in the language", "switch language"
                        ]

                )
            ):
                return lang_map[lang]
    return None
