import os
import json
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

API_KEY = os.getenv("GROQ_API_KEY")

if API_KEY:
    client = Groq(api_key=API_KEY)
else:
    print("Warning: GROQ_API_KEY is not set properly in .env")
    client = None

MODEL_NAME = "llama-3.3-70b-versatile" # "llama3-8b-8192" or "mixtral-8x7b-32768" can also be used

def generate_personalized_feedback(score, total, category, details=""):
    if not client:
        return "AI feedback is currently unavailable. Please configure the Groq API key."
        
    prompt = f"""
    You are an expert AI tutor for a platform called Quizora.
    A student just took a quiz in the category '{category}'.
    They scored {score} out of {total}.
    Performance details: {details}
    
    Please provide a detailed, encouraging performance analysis.
    Include:
    1. A summary of their overall level.
    2. Specific strong areas (based on difficulty levels they passed).
    3. Specific weak areas or concepts they should review.
    4. A clear "Next Step" suggestion (e.g., "Revise the last 3 pages of your document" or "Try a Hard level quiz").
    
    Make it sound supportive and professional. Maximum 5-6 sentences.
    """
    
    try:
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=MODEL_NAME,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error generating AI feedback: {e}")
        return "Great effort! Keep practicing to improve your skills further."

def generate_dynamic_question(category, difficulty, asked_questions):
    """
    Uses Groq API to generate a new, non-repeating multiple-choice question.
    """
    if not client:
        return None
        
    asked_str = ", ".join(asked_questions) if asked_questions else "None"
    
    prompt = f"""
    You are an expert quiz question generator. Your sole purpose is to generate highly accurate and relevant questions.
    The user has requested a quiz on the exact topic of: '{category}'.
    
    CRITICAL INSTRUCTION: You MUST generate a question that is strictly and exclusively about '{category}'.
    Do NOT generate general programming, Python, or AI questions unless the category explicitly asks for them.
    Generate ONE multiple-choice question at a '{difficulty}' difficulty level.
    
    CRITICAL: Do NOT generate any of the following questions that have already been asked:
    [{asked_str}]
    
    You MUST respond with pure JSON format only, structured exactly like this:
    {{
        "question": "The question text here",
        "option_a": "First option",
        "option_b": "Second option",
        "option_c": "Third option",
        "option_d": "Fourth option",
        "correct_answer": "A"
    }}
    """
    
    try:
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=MODEL_NAME,
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"Error generating dynamic question: {e}")
        return None

def determine_next_difficulty(current_difficulty, is_correct):
    levels = ["Easy", "Medium", "Hard"]
    try:
        idx = levels.index(current_difficulty)
    except ValueError:
        idx = 0
        
    if is_correct:
        next_idx = min(idx + 1, len(levels) - 1)
    else:
        next_idx = max(idx - 1, 0)
        
    return levels[next_idx]

def generate_batch_questions(category, count=10):
    if not client:
        return []
        
    prompt = f"""
    You are an expert quiz question generator. Your sole purpose is to generate highly accurate and relevant questions.
    The user has requested a quiz on the exact topic of: '{category}'.
    
    CRITICAL INSTRUCTION: You MUST generate {count} unique multiple-choice questions that are strictly and exclusively about '{category}'.
    Do NOT generate general programming, Python, or AI questions unless the category explicitly asks for them.
    Generate a mix of difficulty levels (Easy, Medium, Hard).
    
    You MUST respond with pure JSON format only. The response must be a valid JSON object with a single key "questions" containing an array of objects, structured exactly like this:
    {{
        "questions": [
            {{
                "question": "The question text here",
                "option_a": "First option",
                "option_b": "Second option",
                "option_c": "Third option",
                "option_d": "Fourth option",
                "correct_answer": "A",
                "difficulty": "Easy"
            }}
        ]
    }}
    """
    
    try:
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=MODEL_NAME,
            response_format={"type": "json_object"}
        )
        data = json.loads(response.choices[0].message.content)
        if 'questions' in data and isinstance(data['questions'], list):
            return data['questions']
        else:
            return []
    except Exception as e:
        print(f"Error generating batch questions: {e}")
        return []

def generate_questions_from_text(text, count=10):
    if not client:
        return []
        
    context_text = text[:15000] 
    
    prompt = f"""
    You are an expert educator and quiz generator. 
    Below is the content extracted from a document/book:
    
    --- START OF CONTENT ---
    {context_text}
    --- END OF CONTENT ---
    
    Based on the provided content above, generate {count} unique multiple-choice questions.
    Each question should test the student's understanding of the key concepts in the text.
    
    Requirements:
    1. Generate {count} questions.
    2. Provide 4 options for each question (A, B, C, D).
    3. Specify the correct answer letter.
    4. Assign a difficulty level (Easy, Medium, or Hard) to each question.
    
    You MUST respond with pure JSON format only. The response must be a valid JSON object with a single key "questions" containing an array of objects, structured exactly like this:
    {{
        "questions": [
            {{
                "question": "The question text here",
                "option_a": "First option",
                "option_b": "Second option",
                "option_c": "Third option",
                "option_d": "Fourth option",
                "correct_answer": "A",
                "difficulty": "Easy"
            }}
        ]
    }}
    """
    
    import time
    max_retries = 2
    for attempt in range(max_retries + 1):
        try:
            response = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=MODEL_NAME,
                response_format={"type": "json_object"}
            )
            data = json.loads(response.choices[0].message.content)
            if 'questions' in data and isinstance(data['questions'], list):
                return data['questions']
            else:
                return []
        except Exception as e:
            if "429" in str(e) or "rate" in str(e).lower():
                if attempt < max_retries:
                    time.sleep(5)
                    continue
                else:
                    return {"error": "AI Rate Limit Exceeded."}
            return {"error": str(e)}
    return {"error": "Unknown AI Error"}

def generate_hint(question_text, options, context_text=""):
    if not client:
        return "Think carefully about the core concepts."
        
    prompt = f"""
    You are an AI Tutor. A student is stuck on this multiple-choice question:
    "{question_text}"
    Options: {options}
    
    Context from the document:
    {context_text[:5000]}
    
    Provide a subtle, helpful hint that guides the student toward the correct answer without directly stating which option is correct.
    Keep it to 1-2 sentences.
    """
    
    try:
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=MODEL_NAME,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error generating hint: {e}")
        return "Try to recall the key definitions from the material."

def generate_explanation(question_text, correct_answer, selected_answer, options_map):
    if not client:
        return "The correct answer is " + correct_answer
        
    prompt = f"""
    You are an AI Tutor. Explain this quiz question to a student.
    Question: "{question_text}"
    Correct Answer: {correct_answer} ({options_map.get(correct_answer)})
    Student's Answer: {selected_answer} ({options_map.get(selected_answer)})
    
    Provide a 2-3 sentence explanation of why the correct answer is right. 
    If the student was wrong, briefly explain the misconception.
    Make it educational and encouraging.
    """
    
    try:
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=MODEL_NAME,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error generating explanation: {e}")
        return f"The correct answer is {correct_answer} because it best fits the criteria defined in the text."

