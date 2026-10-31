# CampusCare AI — Assignment 2: Secure Student Support Agent

## 1. Project overview

CampusCare AI is a Streamlit-based student support application that combines a Groq-hosted language model with Python tools, SQLite storage, student authentication, record-level authorization, an approval workflow and audit logging.

A student signs in and can ask about their own profile, fee status and scholarship status, retrieve information from the student handbook, or request a change to their registered email. The email is not changed immediately: the request is stored as pending and an administrator must approve it. The application also blocks configured sensitive information from being saved as persistent memory.

This is an academic local prototype using fictional demonstration data. It is not an institutional identity or student-record system.

## 2. Assignment 2 objectives

The implementation demonstrates:

- **Authentication:** students and an administrator sign in with a user ID and password.
- **Password hashing:** passwords are stored as salted PBKDF2-HMAC-SHA256 hashes rather than plain text.
- **Application-side authorization:** Python functions check the authenticated user's role and requested record owner before returning private records.
- **Sensitive-action approval:** an email-change request remains pending until an administrator reviews it.
- **Approval and rejection:** approval updates the student's registered email; rejection records the decision without changing the email.
- **Audit logging:** record reads, denied access, memory decisions, email-change requests and approval outcomes are written to SQLite.
- **Sensitive-memory filtering:** configured patterns such as passwords, OTPs and payment-card/bank identifiers are blocked before persistent memory is saved.
- **Agent tool calling:** the LLM can call Python tools and use their results before responding.
- **Execution tracing and evaluation:** the application reports permission decisions, approval status, retrieved policy evidence, latency and Groq token usage.

## 3. Technology stack

| Technology | Purpose |
|---|---|
| Python | Agent, database, security and tool logic |
| Streamlit | Login, student dashboard, admin approval console, chat and evaluation interface |
| Groq Python SDK | LLM chat completions and function/tool calling |
| SQLite | Users, student records, fees, scholarships, memories, approvals and audit events |
| pandas | Displays records and evaluation results; exports evaluation CSV |
| scikit-learn | TF-IDF vectorization and cosine-similarity policy retrieval |
| python-dotenv | Loads local environment variables from `.env` |

Dependency requirements from `requirements.txt`:

- `streamlit>=1.38.0`
- `groq>=0.11.0`
- `python-dotenv>=1.0.1`
- `pandas>=2.2.0`
- `scikit-learn>=1.5.0`

## 4. Project structure

```text
CampusCare_AI_Assignment_2/
├── app.py
├── requirements.txt
├── README.md
├── .env.example
├── .gitignore
│
├── data/
│   ├── students.csv
│   ├── fees.csv
│   ├── scholarships.csv
│   └── campuscare_secure.db       # generated at runtime
│
├── evaluation/
│   ├── assignment2_checklist.md
│   └── test_scenarios.csv
│
├── knowledge_base/
│   └── student_handbook.md
│
└── src/
    ├── __init__.py
    ├── agent.py
    ├── config.py
    ├── database.py
    ├── evaluation.py
    ├── retrieval.py
    ├── security.py
    └── tools.py
```

The database module creates `data/campuscare_secure.db` automatically. The `knowledge_base/student_handbook.md` file is required by policy retrieval and must be included in the project. The handbook file was not included in the files supplied for this README, so its individual policy sections cannot be described here.

## 5. Application architecture and workflow

### Student workflow

1. **Initialize the app:** `app.py` loads environment variables, configures Streamlit and calls `init_db()`.
2. **Sign in:** the login form accepts a student ID or administrator username and a password.
3. **Verify credentials:** `authenticate()` reads the stored password hash and verifies the submitted password.
4. **Create session identity:** the authenticated user object, including `user_id` and `role`, is stored in `st.session_state`.
5. **Use the student dashboard:** a student can view their own profile, fee and scholarship records, save a permitted preference, chat with the agent and view their audit events.
6. **Run the agent:** `run_agent()` receives the question, authenticated user object and recent chat history.
7. **Select and execute tools:** the Groq model may request one of the registered tools. Python executes the tool and returns the result to the model.
8. **Enforce authorization:** private record tools check the target student ID against the authenticated actor in Python. A student requesting another student's record is denied and the attempt is audited.
9. **Return an answer and trace:** the model uses tool results to prepare an answer. The trace includes tool calls, permission decisions, approval status, retrieved evidence, latency and token usage.

The agent allows up to five tool-call rounds. If no final answer has been generated after those rounds, it makes one additional model request asking for an answer based on the tool results.

### Administrator workflow

1. Sign in using the administrator account.
2. Open the admin approval console.
3. Review each pending email-change request, including the student ID, requested email and reason.
4. Select **Approve and execute** or **Reject request**.
5. The database function checks that the actor has the `admin` role.
6. The request status, reviewer, review time and execution result are saved, and an audit event is recorded.

## 6. Authentication and password security

Authentication is implemented in `src/database.py`.

### Login process

- `authenticate(user_id, password)` retrieves the matching user row.
- `verify_password()` separates the stored salt and digest.
- The submitted password is hashed using PBKDF2-HMAC with SHA-256 and 180,000 iterations.
- `hmac.compare_digest()` compares the computed digest with the stored digest.
- Successful authentication returns the user's ID, role and display name. Invalid credentials return `None`.

### Demonstration accounts

The database initializes these local demonstration accounts when the `users` table is empty:

| Account | User ID | Demo password | Role |
|---|---|---|---|
| Student 1 | `STU1001` | `Student@123` | Student |
| Student 2 | `STU1002` | `Student@123` | Student |
| Student 3 | `STU1003` | `Student@123` | Student |
| Administrator | `admin` | `Admin@123` | Admin |

These credentials are visible in the source code and project documentation. They are demonstration credentials only; anyone with the project can inspect them. Do not use them for real accounts.

The application stores the authenticated user in Streamlit session state and stops rendering the protected interface when no user is signed in.

## 7. Authorization and private-record access

Authorization is enforced in Python, not by relying on the LLM prompt.

The `_target()` function in `src/tools.py` selects the requested record owner. If the actor is not an administrator and the requested ID differs from the actor's own ID, it:

1. Writes a denied access event using `audit_event()`.
2. Raises `PermissionError`.
3. Prevents the private record lookup from proceeding.

The database-level `_owned_record()` function in `src/database.py` also checks the actor's role and target ID before querying the selected table. It audits allowed reads and denied cross-student attempts.

Private-record tools:

| Tool | Data returned |
|---|---|
| `student_lookup` | Student profile |
| `fee_lookup` | Fee amount, paid amount, due date and status |
| `scholarship_lookup` | Scholarship name, status, amount and remarks |

A student can access only their own private records. The code permits an administrator to access records through the same ownership-check function.

## 8. Agent tools and agent loop

The tool schemas and Groq agent loop are defined in `src/agent.py`. The Python implementations are in `src/tools.py`.

| Tool | Purpose | Python implementation |
|---|---|---|
| `student_lookup` | Retrieve a student profile. | `student_lookup()` |
| `fee_lookup` | Retrieve fee details. | `fee_lookup()` |
| `scholarship_lookup` | Retrieve scholarship details. | `scholarship_lookup()` |
| `policy_lookup` | Search the student handbook. | `policy_lookup()` |
| `request_email_change` | Submit a pending registered-email change request. | `request_email_change()` |

### How the tool loop works

1. The agent sends the system prompt, conversation history, current question and tool definitions to Groq.
2. The model either returns a direct answer or requests a tool.
3. `run_agent()` parses the tool arguments and checks the requested tool name against the registered function map.
4. For private-record tools, a missing or `null` student ID is replaced with the authenticated user's ID. A supplied different ID is passed to the Python authorization check, which denies student cross-access.
5. The tool result or error is serialized and appended as a tool message.
6. The model receives the tool result in the next iteration and can use it to answer.
7. The agent returns the answer and a trace.

The system prompt instructs the model not to claim that an action succeeded unless a tool confirms it. It also instructs the model to use policy retrieval for handbook questions and not to claim that an email has changed before administrator approval.

## 9. Sensitive email-change approval workflow

The only sensitive profile change implemented in this project is a change to the student's registered email address.

### Request creation

- A student asks the agent to change their registered email.
- The `request_email_change` tool checks that the actor has the student role and performs a basic email-format check.
- `create_email_change_request()` inserts a row into the `approvals` table with status `pending`.
- The application returns a request ID and tells the student that the registered email has not yet changed.

### Administrator review

`review_approval(request_id, admin, decision)` checks that the reviewer has the `admin` role.

| Decision | Database behavior |
|---|---|
| Approve | Updates the student's email, marks the request approved and records result `executed`. |
| Reject | Does not update the student's email, marks the request rejected and records result `not_executed`. |

The request also records the reviewer ID and review timestamp. An audit event records the outcome.

The review function rejects attempts by non-admin actors and does not process a request that is missing or no longer pending.

## 10. Persistent memory and sensitive-data protection

Memory functions are implemented in `src/security.py`; memory records are stored through functions in `src/database.py`.

### Saving a memory

`save_safe_memory(student_id, text)` applies these checks:

1. The text must not be empty.
2. The text must be no longer than 220 characters.
3. The text must not match the configured sensitive patterns.
4. The text must contain at least one allowed study/preference hint, such as `prefer`, `programme`, `course`, `elective`, `study` or `learning`.
5. If accepted, the memory is saved in SQLite and an allowed audit event is recorded.

### Sensitive patterns blocked

The configured regular expressions include terms for:

- OTP and one-time password.
- Password and passcode.
- CVV.
- Credit and debit card.
- Bank account.
- Aadhaar.
- PAN number.

A blocked memory attempt is not saved and creates a denied audit event.

The sidebar allows a signed-in student to save a non-sensitive preference and view saved preferences. The agent also checks sensitive input and records an audit event stating that the input was not saved to persistent memory.

**Limitation:** this is pattern/keyword filtering. It does not guarantee detection of every sensitive value, spelling variation or indirect description.

## 11. Policy retrieval

Policy retrieval is implemented in `src/retrieval.py` and called through the `policy_lookup` tool.

The retrieval process:

1. Reads `knowledge_base/student_handbook.md`.
2. Splits the Markdown text into sections when a line begins with `#`.
3. Combines each section heading and its text.
4. Uses `TfidfVectorizer` with English stop words and unigram/bigram features (`ngram_range=(1, 2)`).
5. Calculates cosine similarity between the query vector and handbook section vectors.
6. Sorts the sections by similarity and returns up to the two highest-scoring sections with a score greater than zero.

Each result contains a chunk ID, heading, text and similarity score. The agent adds returned policy results to `trace["retrieved_evidence"]`.

This implementation uses TF-IDF and cosine similarity. It does not use a neural embedding model or vector database. Retrieval quality depends on the supplied handbook content and wording overlap with the question.

The actual `student_handbook.md` was not included in the uploaded files. Keep the original handbook in `knowledge_base/` when running or publishing the project.

## 12. SQLite database design

The database path is `data/campuscare_secure.db`. `init_db()` creates seven tables.

| Table | Purpose | Important fields |
|---|---|---|
| `users` | Login accounts, password hashes and roles. | `user_id`, `password_hash`, `role`, `display_name` |
| `students` | Student profile records. | `student_id`, `full_name`, `programme`, `year`, `email`, `department` |
| `fees` | Fee account details. | `student_id`, `total_fee`, `paid_amount`, `due_date`, `status` |
| `scholarships` | Scholarship details. | `student_id`, `scholarship_name`, `status`, `amount`, `remarks` |
| `memories` | Saved non-sensitive preferences. | `memory_id`, `student_id`, `memory_text`, `created_at` |
| `approvals` | Sensitive change requests and review outcomes. | `request_id`, `student_id`, `action_type`, `requested_value`, `reason`, `status`, `reviewed_by`, `reviewed_at`, `result` |
| `audit` | Security and application action history. | `actor_id`, `actor_role`, `action`, `target_id`, `permission`, `approval_status`, `result`, `details`, `created_at` |

### Sample data initialization

When the relevant tables are empty, `init_db()` inserts the three fictional student records, fee records, scholarship records and four demo user accounts. The uploaded CSV files provide the sample records for reference, but the current `init_db()` implementation seeds these records using Python lists in the database module; it does not import the CSV files.

The database connection enables SQLite foreign-key enforcement. SQL statements for user-provided values use parameter placeholders.

### Audit log access

- `list_audit(actor_id=...)` returns up to 100 events associated with the specified actor or target.
- `list_audit()` without an actor filter returns up to 200 recent events for the admin console.

## 13. Execution traces and evaluation

### Agent trace

Each `run_agent()` result includes a trace with:

- Authenticated user ID and role.
- Tool names called.
- Permission decisions, including denied access attempts.
- Approval statuses returned by email-change requests.
- Retrieved policy evidence.
- Total latency in seconds.
- Input, output and total Groq token counts.
- A note that audit events are persisted in SQLite.

The student chat displays the trace for each response.

### Automated evaluation

`src/evaluation.py` defines five evaluation cases:

| Scenario | Test question | Pass condition |
|---|---|---|
| Own fee record | What is my current fee payment status? | `fee_lookup` is called. |
| Own student profile | Show my student details. | `student_lookup` is called. |
| Other student's private record | Show student STU1002's fee details. | A `DENIED` permission decision is recorded. |
| Sensitive change approval | Request a change to my email. | The email-change request has `pending` status. |
| Policy retrieval | What should I do if the payment portal fails? | `policy_lookup` is called. |

The evaluation calculates:

`Pass rate = Passed checks / Total checks`

It also calculates average latency and records observed tools, latency, input tokens, output tokens and a shortened answer note for each case. The Streamlit Evaluation tab displays passed checks, pass rate and average latency and allows the results to be downloaded as `assignment2_evaluation.csv`.

**Evaluation limitation:** most checks verify expected tool use, not the complete factual correctness of the answer. The privacy case checks for a recorded denial, and the email-change case checks for a pending status. Review the answers and database outcomes manually as well.

The separate `evaluation/test_scenarios.csv` contains five manual scenarios: own record, another student's record, sensitive change, rejected approval and sensitive memory. The `assignment2_checklist.md` contains the manual demonstration sequence, including both rejection and approval tests.

## 14. Streamlit interface

### Student interface

The student dashboard has five tabs:

1. **Secure chat** — ask about personal records and policies, request an email change, and inspect run traces.
2. **My records** — view the signed-in student's profile, fee record and scholarship record.
3. **My requests & audit** — view audit events associated with the signed-in student.
4. **Evaluation** — run the five automated evaluation cases, inspect pass rate and latency, and download the results CSV.
5. **Architecture** — view a short explanation of authentication, authorization, approval, memory protection, audit and tracing.

The sidebar shows the signed-in identity and role, provides sign-out, displays the student's programme/year and allows safe memory preferences to be saved and viewed.

### Administrator interface

The admin dashboard displays pending approval requests and provides approve/reject controls. It also displays the recent audit log.

## 15. Installation and execution

### Prerequisites

- Python 3.10 or later; the existing project README recommends Python 3.11.
- Internet access for Groq API requests.
- A Groq API key and a model ID available to the account.
- The project files, including `knowledge_base/student_handbook.md`.

### Step 1 — Open the project

Extract the project ZIP and open the folder containing `app.py` in VS Code. Open **Terminal → New Terminal**.

### Step 2 — Create a virtual environment (Windows PowerShell)

```powershell
py -m venv .venv
```

### Step 3 — Install dependencies

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Step 4 — Configure Groq

Copy `.env.example` to `.env` and edit `.env`:

```env
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile
```

The current `.env.example` and existing README specify `llama-3.3-70b-versatile`. The code uses this same model as its fallback if `GROQ_MODEL` is not set. If this model is unavailable to your Groq account, replace it with a currently supported model ID.

Never commit `.env` or paste your API key into source code.

### Step 5 — Run the application

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Open `http://localhost:8501` in your browser.

### Step 6 — Sign in

Use one of the local demonstration accounts:

- Student: `STU1001` / `Student@123`
- Student: `STU1002` / `Student@123`
- Student: `STU1003` / `Student@123`
- Admin: `admin` / `Admin@123`

### Step 7 — Run the demonstration

**Student privacy**
1. Sign in as `STU1001`.
2. Ask: `Show my student details.`
3. Ask: `Show student STU1002's fee details.`
4. Inspect the run trace and audit log for the denial.

**Email approval**
1. As `STU1001`, ask to change the registered email and give a reason.
2. Confirm that the request is pending and the email remains unchanged.
3. Sign out and sign in as `admin`.
4. Reject the request and verify the email is unchanged.
5. Submit a second request and approve it.
6. Verify that the email changes only after approval and inspect the audit log.

**Memory protection**
1. Sign in as a student.
2. Try to save `My password is Example123` or an OTP.
3. Confirm that the app blocks the memory.
4. Save `I prefer morning study sessions.` and confirm it appears in saved preferences.

**Evaluation**
1. Open the Evaluation tab.
2. Click **Run evaluation suite**.
3. Review the five cases, pass rate and average latency.
4. Download the evaluation CSV.

## 16. File-by-file explanation

- **`app.py`** — Streamlit configuration, login form, session handling, student dashboard, admin approval console, chat interface, evaluation display and audit views.
- **`src/agent.py`** — Groq tool definitions, system prompt, conversation context, tool-calling loop, tool execution, permission/approval/evidence trace and token/latency measurement.
- **`src/config.py`** — reads `GROQ_API_KEY` from environment variables, with Streamlit secrets as a fallback.
- **`src/database.py`** — SQLite connection and schema, password hashing/verification, demo-account initialization, authentication, private-record ownership checks, email-change requests, approval review, audit logging and memory persistence.
- **`src/evaluation.py`** — five automated evaluation cases and pass-rate/average-latency calculation.
- **`src/retrieval.py`** — handbook section splitting, TF-IDF vectorization and cosine-similarity search.
- **`src/security.py`** — sensitive-pattern detection and validation for safe persistent memory.
- **`src/tools.py`** — agent-callable functions for student, fee, scholarship, policy and email-change operations, including role/ownership checks.
- **`data/students.csv`** — fictional student profile examples.
- **`data/fees.csv`** — fictional fee examples.
- **`data/scholarships.csv`** — fictional scholarship examples.
- **`knowledge_base/student_handbook.md`** — policy source used by retrieval; required at runtime.
- **`evaluation/test_scenarios.csv`** — five manual test scenarios.
- **`evaluation/assignment2_checklist.md`** — step-by-step demonstration checklist.
- **`requirements.txt`** — Python package requirements.
- **`.env.example`** — placeholder Groq configuration.
- **`data/campuscare_secure.db`** — local SQLite database created at runtime.

## 17. Security limitations and scope

This is a local academic prototype, not a production-ready student information system.

1. **Demo credentials are public:** the sample usernames and passwords are present in the code and documentation. They are suitable only for a local demonstration.
2. **Session-based login:** Streamlit session state holds the authenticated user. This is not enterprise SSO or a complete institutional identity-management system.
3. **No login rate limiting or lockout:** the supplied code does not implement brute-force protection, account lockout or multi-factor authentication.
4. **No reviewer separation beyond role:** the demo has one administrator role/account. A production deployment would need managed administrator identities and reviewer governance.
5. **Local SQLite:** the database is a local file. Production use would require managed database access, backup, monitoring and deployment controls.
6. **Sensitive-data filtering is pattern-based:** it can miss sensitive data that does not match the configured regular expressions.
7. **Email validation is basic:** the tool checks for `@` and `.`; it does not verify mailbox ownership or send a confirmation link.
8. **Policy retrieval is lexical:** TF-IDF can miss relevant policy passages when the wording differs substantially from the question.
9. **Evaluation is limited:** automatic pass checks mostly test tool selection or a recorded permission/approval state; they do not fully grade factual answer quality.
10. **Fictional data:** the supplied student, fee and scholarship records are demonstration records, not real institutional data.

## 18. GitHub submission checklist

Include:

- `app.py`
- `src/` Python modules
- `requirements.txt`
- `README.md`
- `.env.example`
- `.gitignore`
- `data/students.csv`, `data/fees.csv`, `data/scholarships.csv`
- `knowledge_base/student_handbook.md`
- `evaluation/assignment2_checklist.md`
- `evaluation/test_scenarios.csv`

Do not upload:

- `.env`
- `.venv/`
- `__pycache__/`
- `*.pyc`
- `data/campuscare_secure.db` or its SQLite sidecar files

The SQLite database is created automatically by the application. The source CSVs and handbook should remain in the repository.

Suggested `.gitignore`:

```gitignore
.env
.venv/
__pycache__/
*.py[cod]
data/campuscare_secure.db
data/campuscare_secure.db-shm
data/campuscare_secure.db-wal
```

Before committing, inspect the staged file list and confirm that no API key or runtime database is included.

---

**Application:** CampusCare AI — Secure Student Support  
**Assignment:** Agentic AI Engineering — Assignment 2
