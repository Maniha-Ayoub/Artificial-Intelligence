import os
import pypdf
import io
import json
import google.generativeai as genai
from dotenv import load_dotenv

# Re-implement the logic here for debugging
def debug_pdf_gen(pdf_path):
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    print(f"API Key found: {'Yes' if api_key else 'No'}")
    if not api_key:
        return "No API Key"
    
    genai.configure(api_key=api_key)
    
    try:
        with open(pdf_path, 'rb') as f:
            pdf_reader = pypdf.PdfReader(f)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
        
        print(f"Extracted text length: {len(text)} characters")
        if not text.strip():
            return "No text extracted"
            
        context_text = text[:30000]
        prompt = f"""
        Generate 5 MCQs from this text in JSON format:
        {context_text}
        """
        
        model = genai.GenerativeModel('gemini-2.0-flash')
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                response_mime_type="application/json"
            )
        )
        
        print("AI Response received.")
        print(f"Raw text: {response.text}")
        questions = json.loads(response.text)
        print(f"Successfully parsed {len(questions)} questions.")
        return "Success"
        
    except Exception as e:
        print(f"DEBUG ERROR: {type(e).__name__}: {str(e)}")
        if hasattr(e, 'response'):
            print(f"Response error details: {e.response}")
        return str(e)

if __name__ == "__main__":
    # Test with sample.pdf if it exists
    if os.path.exists("sample.pdf"):
        debug_pdf_gen("sample.pdf")
    else:
        print("sample.pdf not found. Please provide a PDF to test.")
