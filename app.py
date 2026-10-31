
import streamlit as st
import pandas as pd
from dotenv import load_dotenv

from src.database import (
    init_db,
    authenticate,
    get_student,
    get_fee,
    get_scholarship,
    list_pending_approvals,
    review_approval,
    list_audit
)

from src.agent import run_agent
from src.security import save_safe_memory, get_memories
from src.evaluation import run_evaluation


# --------------------------------------------------
# 1. APPLICATION CONFIGURATION
# --------------------------------------------------

load_dotenv()

st.set_page_config(
    page_title="CampusCare AI – Secure",
    page_icon="🎓",
    layout="wide"
)

init_db()


# --------------------------------------------------
# 2. CUSTOM CSS
# --------------------------------------------------

st.markdown("""
<style>

.block-container {
    max-width: 1180px;
    padding-top: 1.5rem;
}

.hero {
    background: linear-gradient(120deg, #14213d, #315c91);
    padding: 1.25rem 1.5rem;
    border-radius: 16px;
    color: white;
    margin-bottom: 1rem;
}

.hero h1 {
    color: white;
    margin: 0;
}

.hero p {
    color: #e5edf8;
    margin: .35rem 0 0;
}

</style>
""", unsafe_allow_html=True)


# --------------------------------------------------
# 3. APPLICATION HEADER
# --------------------------------------------------

st.markdown("""
<div class="hero">
    <h1>🎓 CampusCare AI – Secure Student Support</h1>
    <p>Privacy · Permission control · Human approval · Auditability</p>
</div>
""", unsafe_allow_html=True)


# --------------------------------------------------
# 4. SESSION INITIALIZATION
# --------------------------------------------------

if "user" not in st.session_state:
    st.session_state.user = None

if "messages" not in st.session_state:
    st.session_state.messages = []


# --------------------------------------------------
# 5. LOGIN SYSTEM
# --------------------------------------------------

if not st.session_state.user:

    st.subheader("Sign in")

    st.caption(
        "Enter your student ID or administrator username and password."
    )

    with st.form("login_form"):

        username = st.text_input(
            "Student ID or username"
        )

        password = st.text_input(
            "Password",
            type="password"
        )

        submitted = st.form_submit_button(
            "Sign in",
            type="primary",
            use_container_width=True
        )

    if submitted:

        if not username.strip() or not password:
            st.error("Please enter both username and password.")

        else:
            logged_in_user = authenticate(
                username.strip(),
                password
            )

            if logged_in_user:

                st.session_state.user = logged_in_user
                st.session_state.messages = []

                st.success("Login successful!")

                st.rerun()

            else:
                st.error("Invalid username or password.")

    # IMPORTANT:
    # Stop execution while the user is not logged in.
    st.stop()


# --------------------------------------------------
# 6. GET AUTHENTICATED USER
# --------------------------------------------------

user = st.session_state.user

if not user:
    st.session_state.user = None
    st.stop()


# --------------------------------------------------
# 7. SIDEBAR
# --------------------------------------------------

with st.sidebar:

    st.success(
        f"Signed in: {user['display_name']}"
    )

    st.caption(
        f"Role: {user['role'].title()} · ID: {user['user_id']}"
    )

    if st.button("Sign out", use_container_width=True):

        st.session_state.user = None
        st.session_state.messages = []

        st.rerun()

    st.divider()

    # Student sidebar
    if user["role"] == "student":

        st.subheader("Your profile")

        profile = get_student(user["user_id"])

        if profile:

            st.write(
                f"**Programme:** {profile['programme']}"
            )

            st.write(
                f"**Year:** {profile['year']}"
            )

        st.divider()

        # Safe persistent memory
        st.subheader("Safe memory")

        memory = st.text_input(
            "Save a non-sensitive preference",
            placeholder="I prefer morning study sessions"
        )

        if st.button("Save preference"):

            result = save_safe_memory(
                user["user_id"],
                memory
            )

            if result["saved"]:
                st.success("Preference saved.")

            else:
                st.error(result["message"])

        saved = get_memories(user["user_id"])

        if saved:

            with st.expander("Your saved preferences"):

                for item in saved:
                    st.write("• " + item)

    else:

        st.caption(
            "Admin can review sensitive change requests."
        )


# --------------------------------------------------
# 8. STUDENT DASHBOARD
# --------------------------------------------------

if user["role"] == "student":

    tabs = st.tabs([
        "💬 Secure chat",
        "📋 My records",
        "🧾 My requests & audit",
        "📊 Evaluation",
        "ℹ️ Architecture"
    ])


    # ----------------------------------------------
    # TAB 1: SECURE CHAT
    # ----------------------------------------------

    with tabs[0]:

        st.subheader("Ask CampusCare")

        st.caption(
            "You are signed in as one student. "
            "The agent can access only your private records."
        )

        suggestions = [

            "Show my student details.",

            "What is my current fee payment status?",

            "What is my scholarship status?",

            "I want to change my registered email to "
            "newemail@example.com. Please submit this request "
            "for approval.",

            "Show me student STU1002's fee details."

        ]

        with st.expander("Sample questions"):

            cols = st.columns(2)

            for i, q in enumerate(suggestions):

                if cols[i % 2].button(
                    q,
                    key=f"s{i}",
                    use_container_width=True
                ):

                    st.session_state.pending_q = q


        # Display chat history

        for msg in st.session_state.messages:

            with st.chat_message(msg["role"]):

                st.markdown(msg["content"])

                if msg.get("trace"):

                    with st.expander(
                        "Run trace / permission evidence"
                    ):

                        st.json(msg["trace"])


        # User input

        prompt = st.chat_input(
            "Ask about your own student account…"
        )

        if "pending_q" in st.session_state:

            prompt = st.session_state.pop("pending_q")


        if prompt:

            st.session_state.messages.append({
                "role": "user",
                "content": prompt
            })

            with st.chat_message("user"):
                st.markdown(prompt)


            with st.chat_message("assistant"):

                try:

                    result = run_agent(
                        prompt,
                        user,
                        st.session_state.messages[-7:-1]
                    )

                    st.markdown(result["answer"])

                    with st.expander(
                        "Run trace / permission evidence"
                    ):

                        st.json(result["trace"])


                except Exception as e:

                    result = {
                        "answer": f"Application error: {e}",
                        "trace": {"error": str(e)}
                    }

                    st.error(result["answer"])


            st.session_state.messages.append({

                "role": "assistant",

                "content": result["answer"],

                "trace": result["trace"]

            })

            st.rerun()


    # ----------------------------------------------
    # TAB 2: STUDENT RECORDS
    # ----------------------------------------------

    with tabs[1]:

        st.subheader("Your private records")

        st.caption(
            "Records are filtered by your authenticated identity."
        )

        st.write("**Student profile**")

        student = get_student(user["user_id"])

        if student:

            st.dataframe(
                pd.DataFrame([student]),
                use_container_width=True,
                hide_index=True
            )

        c1, c2 = st.columns(2)

        with c1:

            st.write("**Fee record**")

            fee = get_fee(user["user_id"])

            if fee:

                st.dataframe(
                    pd.DataFrame([fee]),
                    use_container_width=True,
                    hide_index=True
                )

        with c2:

            st.write("**Scholarship record**")

            scholarship = get_scholarship(
                user["user_id"]
            )

            if scholarship:

                st.dataframe(
                    pd.DataFrame([scholarship]),
                    use_container_width=True,
                    hide_index=True
                )


    # ----------------------------------------------
    # TAB 3: REQUESTS AND AUDIT
    # ----------------------------------------------

    with tabs[2]:

        st.subheader("Your requests and audit events")

        audit_data = list_audit(
            actor_id=user["user_id"]
        )

        st.dataframe(
            pd.DataFrame(audit_data),
            use_container_width=True,
            hide_index=True
        )


    # ----------------------------------------------
    # TAB 4: EVALUATION
    # ----------------------------------------------

    with tabs[3]:

        st.subheader("Final evaluation")

        st.write(
            "Tests normal support, privacy denial, "
            "approval workflow, latency and token usage."
        )

        if st.button(
            "Run evaluation suite",
            type="primary"
        ):

            with st.spinner(
                "Running evaluation using Groq..."
            ):

                try:

                    st.session_state.eval = run_evaluation(user)

                except Exception as e:

                    st.error(
                        f"Evaluation failed: {e}"
                    )


        if "eval" in st.session_state:

            report = st.session_state.eval

            a, b, c = st.columns(3)

            a.metric(
                "Passed checks",
                f"{report['passed']}/{report['total']}"
            )

            b.metric(
                "Pass rate",
                f"{report['accuracy']:.0%}"
            )

            c.metric(
                "Average latency",
                f"{report['avg_latency']:.2f}s"
            )

            df = pd.DataFrame(report["rows"])

            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True
            )

            st.download_button(
                "Download evaluation CSV",
                df.to_csv(index=False).encode(),
                "assignment2_evaluation.csv",
                "text/csv"
            )


    # ----------------------------------------------
    # TAB 5: ARCHITECTURE
    # ----------------------------------------------

    with tabs[4]:

        st.subheader(
            "How the secure agent works"
        )

        st.markdown("""

        - **Authentication:** Login verifies a password hash
          and establishes the signed-in student identity.

        - **Authorization:** Python tool functions compare
          the requested record owner with the authenticated user.

        - **Approval:** Changing a registered email creates
          a pending request. The database is not changed
          until an admin approves it.

        - **Rejection:** Rejected requests remain unapplied.

        - **Memory safety:** Password, OTP and other sensitive
          patterns are blocked from persistent memory.

        - **Audit:** Access attempts, permission decisions,
          approval outcomes and results are recorded.

        - **Tracing/evaluation:** Tool calls, decision records,
          latency and Groq token usage are shown.

        """)


# --------------------------------------------------
# 9. ADMIN APPROVAL DASHBOARD
# --------------------------------------------------

else:

    st.subheader("Admin approval console")

    st.warning(
        "Review each pending request carefully. "
        "Approval applies the requested change; "
        "rejection leaves the student record unchanged."
    )

    pending = list_pending_approvals()

    if not pending:

        st.success(
            "No pending approval requests."
        )


    for req in pending:

        with st.container(border=True):

            st.write(
                f"**Request #{req['request_id']} — "
                f"{req['student_id']}**"
            )

            st.write(
                f"Action: {req['action_type']}"
            )

            st.write(
                f"Requested change: {req['requested_value']}"
            )

            st.write(
                f"Reason: {req['reason']}"
            )

            c1, c2 = st.columns(2)


            # Approve request

            with c1:

                if st.button(
                    "Approve and execute",
                    key=f"approve{req['request_id']}",
                    type="primary"
                ):

                    try:

                        outcome = review_approval(
                            req["request_id"],
                            user["user_id"],
                            "approved"
                        )

                        st.success(
                            outcome["message"]
                        )

                        st.rerun()

                    except Exception as e:

                        st.error(str(e))


            # Reject request

            with c2:

                if st.button(
                    "Reject request",
                    key=f"reject{req['request_id']}"
                ):

                    try:

                        outcome = review_approval(
                            req["request_id"],
                            user["user_id"],
                            "rejected"
                        )

                        st.warning(
                            outcome["message"]
                        )

                        st.rerun()

                    except Exception as e:

                        st.error(str(e))


    # Admin audit log

    st.subheader("Audit log")

    audit_data = list_audit()

    st.dataframe(
        pd.DataFrame(audit_data),
        use_container_width=True,
        hide_index=True
    )
