import re
from src.database import save_memory_db,get_memories_db,audit_event

SENSITIVE_PATTERNS=[
    r"\botp\b",r"\bone[- ]time password\b",r"\bpassword\b",r"\bpasscode\b",
    r"\bcvv\b",r"\bcredit card\b",r"\bdebit card\b",r"\bbank account\b",
    r"\baadhaar\b",r"\bpan number\b"
]
def contains_sensitive(text):
    return any(re.search(p,text or "",re.I) for p in SENSITIVE_PATTERNS)

def save_safe_memory(student_id,text):
    text=(text or "").strip()
    actor={"user_id":student_id,"role":"student"}
    if not text:
        return {"saved":False,"message":"Enter a preference first."}
    if len(text)>220:
        return {"saved":False,"message":"Keep the preference under 220 characters."}
    if contains_sensitive(text):
        audit_event(actor,"SAVE_MEMORY","self","DENIED","not_required","blocked","Sensitive content was blocked from persistent memory.")
        return {"saved":False,"message":"Blocked: passwords, OTPs and sensitive information cannot be saved in memory."}
    if not any(k in text.lower() for k in ["prefer","preference","programme","program","course","elective","study","learning"]):
        return {"saved":False,"message":"Only non-sensitive study, programme, course or learning preferences can be saved."}
    save_memory_db(student_id,text)
    audit_event(actor,"SAVE_MEMORY","self","ALLOWED","not_required","success","Non-sensitive preference saved.")
    return {"saved":True,"message":"Saved."}
def get_memories(student_id):
    return get_memories_db(student_id)
