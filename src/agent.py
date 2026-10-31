
import json
import os
import time

from groq import Groq

from src.config import api_key
from src.tools import (
    student_lookup,
    fee_lookup,
    scholarship_lookup,
    policy_lookup,
    request_email_change,
)
from src.security import contains_sensitive
from src.database import audit_event


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "student_lookup",
            "description": (
                "Retrieve the signed-in student's profile. "
                "For another student's record, pass their ID so "
                "the security layer can deny and audit the request."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "student_id": {
                        "type": ["string", "null"],
                        "description": "Optional student ID. Use null for the signed-in student."
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fee_lookup",
            "description": (
                "Retrieve fee status. Access is restricted to "
                "the signed-in student's own record."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "student_id": {
                        "type": ["string", "null"],
                        "description": "Optional student ID. Use null for the signed-in student."
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scholarship_lookup",
            "description": (
                "Retrieve scholarship status. Access is restricted "
                "to the signed-in student's own record."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "student_id": {
                        "type": ["string", "null"],
                        "description": "Optional student ID. Use null for the signed-in student."
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "policy_lookup",
            "description": "Search the student handbook for policy information.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "request_email_change",
            "description": (
                "Create a pending request to change the signed-in "
                "student's registered email. An admin must approve it."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "new_email": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["new_email", "reason"],
            },
        },
    },
]


FUNCS = {
    "student_lookup": student_lookup,
    "fee_lookup": fee_lookup,
    "scholarship_lookup": scholarship_lookup,
    "policy_lookup": policy_lookup,
    "request_email_change": request_email_change,
}


def run_agent(question, user, history=None):
    key = api_key()

    if not key:
        raise RuntimeError("Groq API key missing. Configure .env.")

    start = time.perf_counter()

    if contains_sensitive(question):
        audit_event(
            user,
            "CHAT_SENSITIVE_INPUT",
            "self",
            "ALLOWED",
            "not_required",
            "memory_not_saved",
            "Sensitive input detected; it is not stored in persistent memory.",
        )

    system = f"""
You are CampusCare AI, a secure student support assistant.

Authenticated user: {user['user_id']} (role {user['role']}).

Never claim that an action happened unless a tool result confirms it.
The application enforces authorization in Python.
A student may read only their own private record.

If a student asks for another student's private data, call
the relevant lookup tool with that requested ID.
The application will deny and audit the request.

Never reveal private data from chat history.

Changing a registered email is sensitive.
Call request_email_change only to submit a pending request.
Explain that the email is unchanged until admin approval.
Never claim to approve your own request.

Use policy_lookup for handbook questions.
Do not invent policy.
Never save or repeat passwords or OTPs.
Be concise.
All data is fictional demonstration data.
"""

    msgs = [{"role": "system", "content": system}]

    for m in (history or []):
        if m.get("role") in ("user", "assistant"):
            msgs.append({
                "role": m["role"],
                "content": m.get("content", ""),
            })

    msgs.append({"role": "user", "content": question})

    client = Groq(api_key=key)

    model = os.getenv(
        "GROQ_MODEL",
        "llama-3.3-70b-versatile"
    )

    trace = {
        "authenticated_user": user["user_id"],
        "role": user["role"],
        "tool_calls": [],
        "permission_decisions": [],
        "approval_status": [],
        "retrieved_evidence": [],
    }

    in_tok = 0
    out_tok = 0
    answer = ""

    for _ in range(5):
        response = client.chat.completions.create(
            model=model,
            messages=msgs,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0.2,
            max_completion_tokens=800,
        )

        if response.usage:
            in_tok += getattr(response.usage, "prompt_tokens", 0) or 0
            out_tok += getattr(response.usage, "completion_tokens", 0) or 0

        msg = response.choices[0].message

        if not msg.tool_calls:
            answer = msg.content or "I could not complete that request."
            break

        msgs.append({
            "role": "assistant",
            "content": msg.content,
            "tool_calls": [
                t.model_dump(exclude_none=True)
                for t in msg.tool_calls
            ],
        })

        for call in msg.tool_calls:
            name = call.function.name

            try:
                args = json.loads(call.function.arguments or "{}")

                if name not in FUNCS:
                    result = {"error": "Unknown tool"}

                elif name in (
                    "student_lookup",
                    "fee_lookup",
                    "scholarship_lookup",
                ):
                    # Fix: use the authenticated student's ID
                    # when the model sends null or omits student_id.
                    if args.get("student_id") is None:
                        args["student_id"] = user["user_id"]

                    result = FUNCS[name](user, **args)

                elif name == "request_email_change":
                    result = FUNCS[name](user, **args)

                else:
                    result = FUNCS[name](**args)

                trace["tool_calls"].append(name)

                if name in (
                    "student_lookup",
                    "fee_lookup",
                    "scholarship_lookup",
                ):
                    trace["permission_decisions"].append({
                        "tool": name,
                        "decision": "allowed" if result else "not_found",
                        "target": args.get("student_id") or user["user_id"],
                    })

                if name == "policy_lookup":
                    trace["retrieved_evidence"].extend(result)

                if name == "request_email_change":
                    trace["approval_status"].append(
                        result.get("status", "unknown")
                    )

            except PermissionError as e:
                result = {
                    "allowed": False,
                    "error": str(e),
                }

                trace["tool_calls"].append(name)

                trace["permission_decisions"].append({
                    "tool": name,
                    "decision": "DENIED",
                    "reason": str(e),
                })

            except Exception as e:
                result = {"error": str(e)}

            msgs.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": json.dumps(
                    result,
                    ensure_ascii=False,
                    default=str,
                ),
            })

    if not answer:
        response = client.chat.completions.create(
            model=model,
            messages=msgs + [{
                "role": "system",
                "content": "Answer now based only on tool results.",
            }],
            temperature=0.2,
            max_completion_tokens=600,
        )

        if response.usage:
            in_tok += getattr(response.usage, "prompt_tokens", 0) or 0
            out_tok += getattr(response.usage, "completion_tokens", 0) or 0

        answer = (
            response.choices[0].message.content
            or "Unable to answer."
        )

    latency = round(time.perf_counter() - start, 3)

    trace["latency_seconds"] = latency

    trace["token_usage"] = {
        "input": in_tok,
        "output": out_tok,
        "total": in_tok + out_tok,
    }

    trace["audit_events"] = (
        "Audit events are persisted in SQLite and can be viewed in the audit tab."
    )

    return {
        "answer": answer,
        "trace": trace,
    }
