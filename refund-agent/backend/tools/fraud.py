"""
Fraud signal tool: deterministic risk scoring against Rule 5.

Like policy.py, this is plain logic, not an LLM call. A "fraud agent"
implemented as a separate LLM call would be slower, more expensive, and
harder to test for something that is fundamentally: "is refund_count >
threshold." We keep it as a function and reserve the LLM for conversation
and judgment calls that actually require language understanding.
"""

FRAUD_THRESHOLD_30D = 2  # Rule 5: more than 2 refunds in 30 days -> escalate


def check_fraud_signals(customer: dict) -> dict:
    """
    Evaluate a customer's refund history for fraud/abuse signals.

    Returns:
        {
          "risk_level": "low" | "medium" | "high",
          "flag": bool,
          "rule_applied": "RULE_5" | None,
          "explanation": "..."
        }
    """
    recent = customer.get("refund_count_last_30_days", 0)
    lifetime = customer.get("refund_count_lifetime", 0)

    if recent > FRAUD_THRESHOLD_30D:
        return {
            "risk_level": "high",
            "flag": True,
            "rule_applied": "RULE_5",
            "explanation": (
                f"{recent} refund requests in the last 30 days exceeds the "
                f"threshold of {FRAUD_THRESHOLD_30D}. Per Rule 5, this "
                "request must be escalated to manual human review "
                "regardless of whether the order itself is otherwise "
                "eligible."
            ),
        }

    if recent == FRAUD_THRESHOLD_30D:
        return {
            "risk_level": "medium",
            "flag": False,
            "rule_applied": None,
            "explanation": (
                f"{recent} refund requests in the last 30 days is at the "
                "threshold but does not yet exceed it. Proceeding "
                "normally, but worth noting for context."
            ),
        }

    return {
        "risk_level": "low",
        "flag": False,
        "rule_applied": None,
        "explanation": (
            f"{recent} refund requests in the last 30 days, {lifetime} "
            "lifetime. No fraud signal."
        ),
    }
