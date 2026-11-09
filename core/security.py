import streamlit as st

def get_api_key(provider: str):
    if provider == "Groq":
        try:
            return st.secrets.get("GROQ_API_KEY", "")
        except Exception:
            return ""
    if provider == "Gemini":
        try:
            return st.secrets.get("GEMINI_API_KEY", "")
        except Exception:
            return ""
    return ""
