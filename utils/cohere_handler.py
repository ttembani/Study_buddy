import os
from dotenv import load_dotenv # type: ignore
import cohere # type: ignore

load_dotenv()  # Load environment variables

COHERE_API_KEY = os.getenv("COHERE_API_KEY")
if not COHERE_API_KEY:
    raise ValueError("Missing COHERE_API_KEY environment variable")

co = cohere.Client(COHERE_API_KEY)

def generate_answer(query, context=None):
    response = co.chat(message=query, documents=context)
    return response.text
