import sqlite3, hashlib, hmac, secrets
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DB=ROOT/"data"/"campuscare_secure.db"

def conn():
    DB.parent.mkdir(exist_ok=True)
    c=sqlite3.connect(DB)
    c.row_factory=sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    return c

def hash_password(password, salt=None):
    salt=salt or secrets.token_hex(16)
    digest=hashlib.pbkdf2_hmac("sha256",password.encode(),salt.encode(),180000).hex()
    return salt+":"+digest

def verify_password(password, stored):
    try:
        salt,digest=stored.split(":",1)
        check=hashlib.pbkdf2_hmac("sha256",password.encode(),salt.encode(),180000).hex()
        return hmac.compare_digest(check,digest)
    except Exception:
        return False

def init_db():
    with conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users(user_id TEXT PRIMARY KEY,password_hash TEXT NOT NULL,role TEXT NOT NULL,display_name TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS students(student_id TEXT PRIMARY KEY,full_name TEXT,programme TEXT,year TEXT,email TEXT,department TEXT);
        CREATE TABLE IF NOT EXISTS fees(student_id TEXT PRIMARY KEY,total_fee REAL,paid_amount REAL,due_date TEXT,status TEXT);
        CREATE TABLE IF NOT EXISTS scholarships(student_id TEXT PRIMARY KEY,scholarship_name TEXT,status TEXT,amount REAL,remarks TEXT);
        CREATE TABLE IF NOT EXISTS memories(memory_id INTEGER PRIMARY KEY AUTOINCREMENT,student_id TEXT,memory_text TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS approvals(request_id INTEGER PRIMARY KEY AUTOINCREMENT,student_id TEXT,action_type TEXT,requested_value TEXT,reason TEXT,status TEXT DEFAULT 'pending',requested_at TEXT DEFAULT CURRENT_TIMESTAMP,reviewed_by TEXT,reviewed_at TEXT,result TEXT);
        CREATE TABLE IF NOT EXISTS audit(audit_id INTEGER PRIMARY KEY AUTOINCREMENT,actor_id TEXT,actor_role TEXT,action TEXT,target_id TEXT,permission TEXT,approval_status TEXT,result TEXT,details TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        """)
        if c.execute("SELECT COUNT(*) FROM users").fetchone()[0]==0:
            users=[
             ("STU1001",hash_password("Student@123"),"student","Aarav Shah"),
             ("STU1002",hash_password("Student@123"),"student","Diya Patel"),
             ("STU1003",hash_password("Student@123"),"student","Kabir Mehta"),
             ("admin",hash_password("Admin@123"),"admin","CampusCare Admin")]
            c.executemany("INSERT INTO users VALUES(?,?,?,?)",users)
        if c.execute("SELECT COUNT(*) FROM students").fetchone()[0]==0:
            students=[
             ("STU1001","Aarav Shah","PGDM Business Analytics","1","aarav@example.edu","Management"),
             ("STU1002","Diya Patel","PGDM AI and Data Science","1","diya@example.edu","Data Science"),
             ("STU1003","Kabir Mehta","PGDM Business Analytics","2","kabir@example.edu","Management")]
            c.executemany("INSERT INTO students VALUES(?,?,?,?,?,?)",students)
            c.executemany("INSERT INTO fees VALUES(?,?,?,?,?)",[
             ("STU1001",240000,180000,"2026-11-15","Partially Paid"),
             ("STU1002",250000,250000,"2026-11-15","Paid"),
             ("STU1003",235000,235000,"2026-09-30","Paid")])
            c.executemany("INSERT INTO scholarships VALUES(?,?,?,?,?)",[
             ("STU1001","Merit Scholarship","Approved",25000,"Approved for demo year"),
             ("STU1002","Institute Need-Based Grant","Under Review",30000,"Documents under review"),
             ("STU1003","Merit Scholarship","Approved",20000,"Approved for demo year")])

def authenticate(user_id,password):
    with conn() as c:
        row=c.execute("SELECT * FROM users WHERE user_id=?",(user_id,)).fetchone()
    if row and verify_password(password,row["password_hash"]):
        return {"user_id":row["user_id"],"role":row["role"],"display_name":row["display_name"]}
    return None

def _owned_record(table,user_id,actor):
    if actor["role"]!="admin" and user_id!=actor["user_id"]:
        audit_event(actor,"READ_"+table,user_id,"DENIED","not_required","blocked","Cross-student access attempt")
        raise PermissionError("Access denied: you can only access your own private record.")
    with conn() as c:
        row=c.execute(f"SELECT * FROM {table} WHERE student_id=?",(user_id,)).fetchone()
    audit_event(actor,"READ_"+table,user_id,"ALLOWED","not_required","success","Private record read")
    return dict(row) if row else None

def get_student(user_id,actor=None):
    actor=actor or {"user_id":user_id,"role":"student"}
    return _owned_record("students",user_id,actor)
def get_fee(user_id,actor=None):
    actor=actor or {"user_id":user_id,"role":"student"}
    return _owned_record("fees",user_id,actor)
def get_scholarship(user_id,actor=None):
    actor=actor or {"user_id":user_id,"role":"student"}
    return _owned_record("scholarships",user_id,actor)

def audit_event(actor,action,target_id,permission,approval_status,result,details=""):
    with conn() as c:
        c.execute("INSERT INTO audit(actor_id,actor_role,action,target_id,permission,approval_status,result,details) VALUES(?,?,?,?,?,?,?,?)",
        (actor.get("user_id","unknown"),actor.get("role","unknown"),action,str(target_id),permission,approval_status,result,details[:700]))

def create_email_change_request(actor,new_email,reason):
    if actor["role"]!="student":
        raise PermissionError("Only a signed-in student can request this change.")
    with conn() as c:
        cur=c.execute("INSERT INTO approvals(student_id,action_type,requested_value,reason,status) VALUES(?,?,?,?, 'pending')",
        (actor["user_id"],"CHANGE_REGISTERED_EMAIL",new_email,reason[:400]))
        request_id=cur.lastrowid
    audit_event(actor,"REQUEST_EMAIL_CHANGE",actor["user_id"],"ALLOWED","pending","awaiting_approval",f"Request #{request_id}; new email={new_email}")
    return {"request_id":request_id,"status":"pending","message":"Your request is waiting for admin approval. Your registered email has not been changed."}

def list_pending_approvals():
    with conn() as c:
        return [dict(x) for x in c.execute("SELECT * FROM approvals WHERE status='pending' ORDER BY request_id")]
def review_approval(request_id,admin,decision):
    if admin.get("role")!="admin":
        audit_event(admin,"REVIEW_APPROVAL",request_id,"DENIED","not_allowed","blocked","Non-admin approval attempt")
        raise PermissionError("Only an admin can review approval requests.")
    with conn() as c:
        req=c.execute("SELECT * FROM approvals WHERE request_id=?",(request_id,)).fetchone()
        if not req or req["status"]!="pending":
            return {"message":"Request not found or already reviewed."}
        if decision=="approved":
            c.execute("UPDATE students SET email=? WHERE student_id=?",(req["requested_value"],req["student_id"]))
            result="executed"
        else:
            result="not_executed"
        c.execute("UPDATE approvals SET status=?,reviewed_by=?,reviewed_at=CURRENT_TIMESTAMP,result=? WHERE request_id=?",
                  (decision,admin["user_id"],result,request_id))
    audit_event(admin,"REVIEW_EMAIL_CHANGE",req["student_id"],"ALLOWED",decision,result,f"Request #{request_id}")
    return {"message":f"Request {decision}. Change {result.replace('_',' ')}."}

def list_audit(actor_id=None):
    with conn() as c:
        if actor_id:
            rows=c.execute("SELECT * FROM audit WHERE actor_id=? OR target_id=? ORDER BY audit_id DESC LIMIT 100",(actor_id,actor_id))
        else:
            rows=c.execute("SELECT * FROM audit ORDER BY audit_id DESC LIMIT 200")
        return [dict(x) for x in rows]
def get_memories_db(student_id):
    with conn() as c:
        return [x["memory_text"] for x in c.execute("SELECT memory_text FROM memories WHERE student_id=? ORDER BY memory_id DESC LIMIT 10",(student_id,))]
def save_memory_db(student_id,text):
    with conn() as c:
        c.execute("INSERT INTO memories(student_id,memory_text) VALUES(?,?)",(student_id,text))
