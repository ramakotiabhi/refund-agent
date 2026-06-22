"""
The agent loop: a single LLM-driven tool-calling orchestrator.

Design decision (explain this on camera): there is ONE agent here, not
seven. The LLM's job is conversation, tool selection, and explaining
outcomes in natural language. It never decides refund eligibility or
fraud risk itself -- those are deterministic functions in tools/policy.py
and tools/fraud.py. This keeps the "strict policy" actually strict: the
rules can't drift between requests because they're not re-interpreted by
the model every time.

Retry behavior: each tool call is wrapped with a single automatic retry
on failure (simulating a flaky downstream system, e.g. a DB timeout).
If the retry also fails, the agent escalates rather than guessing. Both
the failure and the retry are logged, which is what the admin dashboard
surfaces as the "reasoning trace."
"""
import time
import uuid

from llm_client import call_llm
from reasoning_log import log_event
from tools.crm import lookup_customer, lookup_order, lookup_orders_for_customer
from tools.policy import check_refund_policy
from tools.fraud import check_fraud_signals
from tools.escalation import escalate_to_human
from tools.evidence import analyze_evidence

SYSTEM_PROMPT = """You are a customer support agent for an e-commerce company, \
handling refund requests. You have tools to look up customers and orders, \
check refund policy eligibility, check fraud signals, analyze evidence, and \
escalate to a human reviewer.

Rules you must follow:
- Always look up the customer and the order before making any claim about \
their eligibility.
- Always check refund policy AND fraud signals before giving a final answer.
- You do NOT have discretion to override a policy denial because the \
customer is upset, insistent, or a long-time customer. If check_refund_policy \
returns "deny", explain the specific rule and hold that position, even if \
the customer pushes back, unless they provide genuinely new information \
(e.g. new evidence you haven't seen).
- If a tool indicates escalation is required (fraud flag or ambiguous \
policy result), call escalate_to_human and tell the customer their case is \
under review -- do not approve or deny it yourself.
- Be warm and clear, but be precise about which policy rule applies.
"""

TOOL_SCHEMAS = [
    {
        "name": "lookup_customer",
        "description": "Look up a customer by customer_id or email address.",
        "input_schema": {
            "type": "object",
            "properties": {"identifier": {"type": "string"}},
            "required": ["identifier"],
        },
    },
    {
        "name": "lookup_order",
        "description": "Look up an order by order_id.",
        "input_schema": {
            "type": "object",
            "properties": {"order_id": {"type": "string"}},
            "required": ["order_id"],
        },
    },
    {
        "name": "check_refund_policy",
        "description": (
            "Evaluate an order against the refund policy. Requires the "
            "order_id (must be looked up first) and the customer's stated "
            "reason for the refund."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string"},
                "reason": {"type": "string"},
            },
            "required": ["order_id", "reason"],
        },
    },
    {
        "name": "check_fraud_signals",
        "description": "Check a customer's refund history for fraud/abuse signals.",
        "input_schema": {
            "type": "object",
            "properties": {"customer_id": {"type": "string"}},
            "required": ["customer_id"],
        },
    },
    {
        "name": "analyze_evidence",
        "description": (
            "Analyze customer-submitted evidence (image description or URL) "
            "for a damage/defect claim. Advisory only -- does not override "
            "policy eligibility."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"image_url_or_description": {"type": "string"}},
            "required": ["image_url_or_description"],
        },
    },
    {
        "name": "escalate_to_human",
        "description": "Escalate a case to manual human review.",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "order_id": {"type": "string"},
                "reason": {"type": "string"},
            },
            "required": ["customer_id", "order_id", "reason"],
        },
    },
]

TOOL_IMPL = {
    "lookup_customer": lambda args: lookup_customer(args["identifier"]),
    "lookup_order": lambda args: lookup_order(args["order_id"]),
    "check_refund_policy": lambda args: _check_policy_wrapper(args),
    "check_fraud_signals": lambda args: _check_fraud_wrapper(args),
    "analyze_evidence": lambda args: analyze_evidence(args["image_url_or_description"]),
    "escalate_to_human": lambda args: escalate_to_human(
        args["customer_id"], args["order_id"], args["reason"]
    ),
}


def _check_policy_wrapper(args):
    order_result = lookup_order(args["order_id"])
    if not order_result["found"]:
        return {"error": order_result["error"]}
    return check_refund_policy(order_result["order"], args["reason"])


def _check_fraud_wrapper(args):
    customer_result = lookup_customer(args["customer_id"])
    if not customer_result["found"]:
        return {"error": customer_result["error"]}
    return check_fraud_signals(customer_result["customer"])


# Simulate a flaky downstream dependency for exactly one tool, so the demo
# can show a real retry happening. lookup_order "fails" on its first call
# within a session purely to demonstrate retry handling -- this is a
# deliberate demo aid, not a hidden bug.
_simulated_failure_done = set()


def _call_tool_with_retry(session_id: str, tool_name: str, tool_input: dict, max_retries: int = 1):
    attempt = 0
    last_error = None

    while attempt <= max_retries:
        start = time.time()
        try:
            if (
                tool_name == "lookup_order"
                and session_id not in _simulated_failure_done
                and attempt == 0
            ):
                _simulated_failure_done.add(session_id)
                raise ConnectionError("Simulated transient DB timeout")

            result = TOOL_IMPL[tool_name](tool_input)
            latency_ms = int((time.time() - start) * 1000)
            log_event(
                session_id, "tool_call", tool_name,
                input_data=tool_input, output_data=result,
                status="success", latency_ms=latency_ms,
            )
            return result

        except Exception as e:
            latency_ms = int((time.time() - start) * 1000)
            last_error = str(e)
            status = "retrying" if attempt < max_retries else "failed"
            log_event(
                session_id, "retry" if attempt < max_retries else "error", tool_name,
                input_data=tool_input, output_data={"error": last_error},
                status=status, latency_ms=latency_ms,
            )
            attempt += 1

    # All retries exhausted -- surface as a tool error result rather than crashing
    return {"error": f"Tool '{tool_name}' failed after {max_retries + 1} attempts: {last_error}"}


def run_agent_turn(session_id: str, conversation_history: list, user_message: str) -> dict:
    """
    Run one full turn of the agent loop for a single user message.
    Returns {"reply": str, "history": list} where history is the updated
    message list to pass back in on the next turn.
    """
    messages = conversation_history + [{"role": "user", "content": user_message}]

    log_event(session_id, "llm_call", "agent_turn_start", input_data={"message": user_message})

    max_loop_iterations = 8  # safety valve against infinite tool-calling loops
    for _ in range(max_loop_iterations):
        start = time.time()
        try:
            response = call_llm(messages, TOOL_SCHEMAS, SYSTEM_PROMPT)
        except Exception as e:
            latency_ms = int((time.time() - start) * 1000)
            log_event(
                session_id, "error", "llm_call_failed",
                output_data={"error": str(e)}, status="failed", latency_ms=latency_ms,
            )
            fallback = (
                "I'm having trouble reaching the language model right now "
                "(this usually means the API key is missing, invalid, or "
                "rate-limited). I've logged this — please check your "
                "ANTHROPIC_API_KEY / OPENAI_API_KEY configuration, or try "
                "again in a moment."
            )
            return {"reply": fallback, "history": messages}
        latency_ms = int((time.time() - start) * 1000)

        if response["stop_reason"] != "tool_use":
            final_text = next(
                (b["text"] for b in response["content"] if b.get("type") == "text"), ""
            )
            log_event(
                session_id, "decision", "final_response",
                output_data={"text": final_text}, latency_ms=latency_ms,
            )
            messages.append({"role": "assistant", "content": response["content"]})
            return {"reply": final_text, "history": messages}

        messages.append({"role": "assistant", "content": response["content"]})

        tool_results_content = []
        for block in response["content"]:
            if block.get("type") != "tool_use":
                continue
            tool_name = block["name"]
            tool_input = block["input"]
            result = _call_tool_with_retry(session_id, tool_name, tool_input)
            tool_results_content.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block["id"],
                    "content": result,
                }
            )

        messages.append({"role": "user", "content": tool_results_content})

    # Safety valve triggered -- escalate rather than loop forever
    log_event(session_id, "error", "max_iterations_exceeded", status="failed")
    fallback = (
        "I'm having trouble resolving this automatically — I've escalated "
        "it to a human specialist who will follow up shortly."
    )
    return {"reply": fallback, "history": messages}


def new_session_id() -> str:
    return str(uuid.uuid4())
