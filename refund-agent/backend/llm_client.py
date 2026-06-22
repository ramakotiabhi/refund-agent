"""
LLM client wrapper.

Supports three modes, auto-detected from environment variables:
  1. ANTHROPIC_API_KEY set -> real Claude calls (claude-sonnet-4-6)
  2. OPENAI_API_KEY set (and no Anthropic key) -> real GPT calls (gpt-4o)
  3. Neither set -> deterministic mock LLM (no cost, no key needed)

All three implement the same tool-calling interface, so agent.py never
needs to know which one is active. Add a real key to backend/.env (copy
from .env.example) and the exact same code path calls the real model --
no rewiring needed.

SECURITY: never paste a real API key into a chat window, ticket, or any
other place it could be logged. If a key is ever exposed that way, treat
it as compromised and revoke/rotate it immediately at the provider's
dashboard before using it anywhere.
"""
import os
import re

from dotenv import load_dotenv

load_dotenv()  # picks up backend/.env if present; no-op if it doesn't exist

ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY")
OPENAI_KEY = os.environ.get("OPENAI_API_KEY")

USE_ANTHROPIC = bool(ANTHROPIC_KEY)
USE_OPENAI = bool(OPENAI_KEY) and not USE_ANTHROPIC
USE_REAL_LLM = USE_ANTHROPIC or USE_OPENAI

if USE_ANTHROPIC:
    import anthropic
    _client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    MODEL = "claude-sonnet-4-6"

if USE_OPENAI:
    from openai import OpenAI
    _openai_client = OpenAI(api_key=OPENAI_KEY)
    OPENAI_MODEL = "gpt-4o"


def call_llm_real(messages: list, tools: list, system: str) -> dict:
    """Real Claude call with tool-calling enabled."""
    response = _client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=system,
        messages=messages,
        tools=tools,
    )
    return {
        "stop_reason": response.stop_reason,
        "content": [block.model_dump() for block in response.content],
    }


def call_llm_openai(messages: list, tools: list, system: str) -> dict:
    """
    Real GPT call. Translates between Anthropic's message/tool-call shape
    (used throughout agent.py) and OpenAI's chat-completions shape, so
    agent.py and reasoning_log.py never need to know which provider is
    actually running underneath.
    """
    import json as _json

    openai_tools = [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"],
            },
        }
        for t in tools
    ]

    openai_messages = [{"role": "system", "content": system}]
    for m in messages:
        if m["role"] == "user" and isinstance(m["content"], str):
            openai_messages.append({"role": "user", "content": m["content"]})
        elif m["role"] == "assistant" and isinstance(m["content"], list):
            tool_calls = [
                {
                    "id": b["id"],
                    "type": "function",
                    "function": {"name": b["name"], "arguments": _json.dumps(b["input"])},
                }
                for b in m["content"] if b.get("type") == "tool_use"
            ]
            text_blocks = [b["text"] for b in m["content"] if b.get("type") == "text"]
            entry = {"role": "assistant", "content": " ".join(text_blocks) or None}
            if tool_calls:
                entry["tool_calls"] = tool_calls
            openai_messages.append(entry)
        elif m["role"] == "user" and isinstance(m["content"], list):
            for b in m["content"]:
                if b.get("type") == "tool_result":
                    openai_messages.append({
                        "role": "tool",
                        "tool_call_id": b["tool_use_id"],
                        "content": _json.dumps(b["content"]),
                    })

    response = _openai_client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=openai_messages,
        tools=openai_tools if openai_tools else None,
    )
    choice = response.choices[0]
    msg = choice.message

    content_blocks = []
    if msg.content:
        content_blocks.append({"type": "text", "text": msg.content})
    if msg.tool_calls:
        for tc in msg.tool_calls:
            content_blocks.append({
                "type": "tool_use",
                "id": tc.id,
                "name": tc.function.name,
                "input": _json.loads(tc.function.arguments),
            })

    stop_reason = "tool_use" if msg.tool_calls else "end_turn"
    return {"stop_reason": stop_reason, "content": content_blocks}


def call_llm_mock(messages: list, tools: list, system: str) -> dict:
    """
    Deterministic mock LLM. Inspects the latest user message and the
    conversation so far to decide which tool to call next, mimicking how
    a real tool-calling model would sequence: identify customer -> get
    order -> check policy -> check fraud -> (maybe escalate) -> respond.

    This is intentionally simple pattern-matching, not a real model -- it
    exists to exercise the full pipeline end-to-end before a real key is
    plugged in.
    """
    last_user_msg = ""
    for m in reversed(messages):
        if m["role"] == "user" and isinstance(m["content"], str):
            last_user_msg = m["content"]
            break

    tool_results_so_far = {
        m_content["tool_use_id"]: m_content
        for m in messages
        if m["role"] == "user" and isinstance(m["content"], list)
        for m_content in m["content"]
        if m_content.get("type") == "tool_result"
    }
    called_tools = [
        block["name"]
        for m in messages
        if m["role"] == "assistant" and isinstance(m["content"], list)
        for block in m["content"]
        if block.get("type") == "tool_use"
    ]

    order_id_match = re.search(r"ORD\d+", last_user_msg.upper())
    customer_id_match = re.search(r"CUST\d+", last_user_msg.upper())
    email_match = re.search(r"[\w\.-]+@[\w\.-]+", last_user_msg)

    # Step 1: no tools called yet -> look up the customer
    if "lookup_customer" not in called_tools:
        identifier = (
            customer_id_match.group(0) if customer_id_match
            else email_match.group(0) if email_match
            else "CUST001"  # fallback for mock demo purposes
        )
        return _tool_call_response("lookup_customer", {"identifier": identifier})

    # Step 2: look up the order
    if "lookup_order" not in called_tools:
        order_id = order_id_match.group(0) if order_id_match else "ORD1001"
        return _tool_call_response("lookup_order", {"order_id": order_id})

    # Step 3: check policy
    if "check_refund_policy" not in called_tools:
        order_id = order_id_match.group(0) if order_id_match else "ORD1001"
        return _tool_call_response(
            "check_refund_policy", {"order_id": order_id, "reason": last_user_msg}
        )

    # Step 4: check fraud signals
    if "check_fraud_signals" not in called_tools:
        identifier = (
            customer_id_match.group(0) if customer_id_match
            else email_match.group(0) if email_match
            else "CUST001"
        )
        return _tool_call_response("check_fraud_signals", {"customer_id": identifier})

    # Step 5: if policy/fraud says escalate, call escalate_to_human
    policy_result = next(
        (r["content"] for r in tool_results_so_far.values()
         if isinstance(r.get("content"), dict) and "decision" in r.get("content", {})),
        None,
    )
    fraud_result = next(
        (r["content"] for r in tool_results_so_far.values()
         if isinstance(r.get("content"), dict) and "flag" in r.get("content", {})),
        None,
    )

    should_escalate = (fraud_result and fraud_result.get("flag")) or (
        policy_result and policy_result.get("decision") == "escalate"
    )

    if should_escalate and "escalate_to_human" not in called_tools:
        order_id = order_id_match.group(0) if order_id_match else "ORD1001"
        customer_id = customer_id_match.group(0) if customer_id_match else "CUST001"
        return _tool_call_response(
            "escalate_to_human",
            {"customer_id": customer_id, "order_id": order_id, "reason": last_user_msg},
        )

    # Final step: synthesize a natural-language answer from gathered tool results
    final_text = _synthesize_final_answer(tool_results_so_far)
    return {"stop_reason": "end_turn", "content": [{"type": "text", "text": final_text}]}


def _tool_call_response(tool_name: str, tool_input: dict) -> dict:
    return {
        "stop_reason": "tool_use",
        "content": [
            {
                "type": "tool_use",
                "id": f"mock_{tool_name}_{os.urandom(4).hex()}",
                "name": tool_name,
                "input": tool_input,
            }
        ],
    }


def _synthesize_final_answer(tool_results_so_far: dict) -> str:
    decision = None
    explanation = None
    escalation_msg = None

    for r in tool_results_so_far.values():
        content = r.get("content")
        if isinstance(content, dict):
            if "decision" in content and content["decision"] in ("approve", "deny", "escalate"):
                decision = content["decision"]
                explanation = content.get("explanation")
            if content.get("escalated"):
                escalation_msg = content.get("message")

    if escalation_msg:
        return (
            f"Thanks for the details. {escalation_msg} "
            f"Reason: {explanation or 'flagged for additional review.'}"
        )

    if decision == "approve":
        return f"Good news — your refund has been approved. {explanation}"
    if decision == "deny":
        return f"I'm sorry, but I can't approve this refund. {explanation}"

    return (
        "I've reviewed your request but need a bit more information to "
        "make a determination. Could you clarify the order ID and the "
        "reason for the refund?"
    )


def call_llm(messages: list, tools: list, system: str) -> dict:
    if USE_ANTHROPIC:
        return call_llm_real(messages, tools, system)
    if USE_OPENAI:
        return call_llm_openai(messages, tools, system)
    return call_llm_mock(messages, tools, system)
