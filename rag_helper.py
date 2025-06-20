import cohere
import google.generativeai as genai
from google.api_core.exceptions import GoogleAPICallError
import os

# --- Load API keys ---
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") or "your_google_api_key"
COHERE_API_KEY = os.getenv("COHERE_API_KEY") or "your_cohere_api_key"

# --- Initialize Gemini ---
genai.configure(api_key=GOOGLE_API_KEY)

# NOTE: Replace with "models/gemini-1.5-pro" if you have access to Gemini 1.5
gemini_model = genai.GenerativeModel("gemini-pro")

# --- Initialize Cohere ---
co = cohere.Client(COHERE_API_KEY)


def ask_study_buddy(question):
    """
    Uses Gemini first, falls back to Cohere if Gemini fails.
    Returns generated content as a string.
    """
    full_prompt = f"You are an intelligent and friendly AI study buddy. Answer the question clearly:\n\n{question}"

    # Try Gemini
    try:
        gemini_response = gemini_model.generate_content(full_prompt)
        if hasattr(gemini_response, 'text'):
            return gemini_response.text.strip()
        else:
            return "Gemini responded, but no text was returned."
    
    except GoogleAPICallError as e:
        print("[ERROR] Gemini API failed:", e.message)
    except Exception as e:
        print("[ERROR] Unexpected error from Gemini:", e)

    # Fallback to Cohere
    try:
        cohere_response = co.generate(
            model="command-r-plus",  # Or "command-r" if you don't have access
            prompt=full_prompt,
            max_tokens=300,
            temperature=0.7
        )
        return cohere_response.generations[0].text.strip()

    except Exception as co_e:
        print("[ERROR] Cohere API also failed:", co_e)
        return "Sorry, both Gemini and Cohere failed to respond. Please try again later."
