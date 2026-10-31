from src.database import get_student,get_fee,get_scholarship,create_email_change_request,audit_event
from src.retrieval import search_policy

def _target(requested_id,actor,action):
    target=requested_id or actor["user_id"]
    if actor["role"]!="admin" and target!=actor["user_id"]:
        audit_event(actor,action,target,"DENIED","not_required","blocked","Attempt to access another student's private record.")
        raise PermissionError("Access denied. You may only access your own private records.")
    return target

def student_lookup(actor,student_id=None):
    target=_target(student_id,actor,"STUDENT_LOOKUP")
    return get_student(target,actor)
def fee_lookup(actor,student_id=None):
    target=_target(student_id,actor,"FEE_LOOKUP")
    return get_fee(target,actor)
def scholarship_lookup(actor,student_id=None):
    target=_target(student_id,actor,"SCHOLARSHIP_LOOKUP")
    return get_scholarship(target,actor)
def policy_lookup(query):
    return search_policy(query)
def request_email_change(actor,new_email,reason):
    if actor["role"]!="student":
        raise PermissionError("Only students can request their own email change.")
    if "@" not in new_email or "." not in new_email:
        return {"created":False,"message":"Please provide a valid email address."}
    return create_email_change_request(actor,new_email,reason)
