import os,streamlit as st
def api_key():
    key=os.getenv("GROQ_API_KEY","").strip()
    if not key:
        try:key=str(st.secrets.get("GROQ_API_KEY","")).strip()
        except Exception:key=""
    return key
