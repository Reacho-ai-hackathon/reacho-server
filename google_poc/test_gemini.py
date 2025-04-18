import google.generativeai as genai
import os

def main():
    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key:
        print('GOOGLE_API_KEY not set in environment.')
        return
    genai.configure(api_key=api_key)
    try:
        model = genai.GenerativeModel('models/gemini-1.5-pro-latest')
        response = model.generate_content('Say hello from Gemini!')
        print('Gemini response:', response.text)
    except Exception as e:
        print('Error:', e)

if __name__ == '__main__':
    main()