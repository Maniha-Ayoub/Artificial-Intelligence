import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
print("API_KEY loaded:", API_KEY[:5] + "..." if API_KEY else None)

genai.configure(api_key=API_KEY)

try:
    model = genai.GenerativeModel('gemini-pro')
    response = model.generate_content("Hello")
    print("Success:", response.text)
except Exception as e:
    print("Error:", repr(e))
