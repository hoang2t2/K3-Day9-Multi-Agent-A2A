import os
from langchain_google_genai import ChatGoogleGenerativeAI
from src.config import MODEL_NAME, MAX_RETRIES

def get_llm():
    return ChatGoogleGenerativeAI(
        model=MODEL_NAME,
        temperature=0.0,
        max_retries=MAX_RETRIES,
        timeout=30.0, # Timeout
    )
