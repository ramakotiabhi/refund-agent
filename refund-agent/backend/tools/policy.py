"""
Policy tool: the deterministic refund-eligibility engine.

This is the single most important file in the project. The refund policy
is implemented here as actual control flow -- not handed to an LLM to
"interpret" loosely. The LLM never decides eligibility; it calls
check_refund_policy() and receives a structured, ruleId-backed verdict
that it then explains to the customer in natural language.

This is what makes the policy "strict": the rules live in code, so they
can't drift, get talked around, or vary between requests.

Maps directly to backend/data/refund_policy.txt -- keep the two in sync.
"""
from datetime import date, datetime


def _days_since(date_str: str) -> int:
    d = datetime.strptime(date_str, "%Y-%m-%d").date()
    return (date.today() - d).days


def check_refund_policy(order: dict, reason: str) -> dict:
    """
    Evaluate a single order against the refund policy.

    Args:
        order: an order record (from crm.lookup_order), including
               delivery_status, delivery_date, is_final_sale, is_digital.
        reason: the customer's stated reason for the refund request,
                e.g. "defective", "changed my mind", "wrong item",
                "never arrived". Used only to route to the right rule --
                not free-text interpreted as policy itself.

    Returns:
        {
          "decision": "approve" | "deny" | "escalate",
          "rule_applied": "RULE_1",
          "explanation": "..."
        }
    """
    reason_lower = (reason or "").lower()

    # RULE 6 -- Lost in transit -> approve, no window applies
    if order.get("delivery_status") == "lost_in_transit":
        return {
            "decision": "approve",
            "rule_applied": "RULE_6",
            "explanation": (
                "Order was never delivered (lost in transit). Per Rule 6, "
                "the customer is eligible for a full refund regardless of "
                "elapsed time."
            ),
        }

    # RULE 7 -- Wrong item delivered -> approve, no window applies
    if order.get("delivery_status") == "delivered_wrong_item":
        return {
            "decision": "approve",
            "rule_applied": "RULE_7",
            "explanation": (
                "The wrong item was delivered. Per Rule 7, this is a "
                "fulfillment error and the customer is eligible for a "
                "full refund regardless of elapsed time."
            ),
        }

    # RULE 4 -- Final sale / clearance -> deny, overrides window
    if order.get("is_final_sale"):
        return {
            "decision": "deny",
            "rule_applied": "RULE_4",
            "explanation": (
                "This item was marked final sale / clearance at time of "
                "purchase. Per Rule 4, final sale items are non-refundable "
                "regardless of the time window."
            ),
        }

    # RULE 3 -- Digital goods -> deny, unless verified technical fault
    if order.get("is_digital"):
        if "technical" in reason_lower or "didn't activate" in reason_lower or "never activated" in reason_lower:
            return {
                "decision": "escalate",
                "rule_applied": "RULE_3",
                "explanation": (
                    "Digital product with a claimed activation/technical "
                    "fault. Per Rule 3, this requires manual verification "
                    "before a decision can be made -- escalating rather "
                    "than auto-denying."
                ),
            }
        return {
            "decision": "deny",
            "rule_applied": "RULE_3",
            "explanation": (
                "This is a digital product. Per Rule 3, digital goods are "
                "non-refundable once delivered/activated, regardless of "
                "the time window."
            ),
        }

    # Determine claimed defect/damage for Rule 2 window extension
    is_defect_claim = any(
        kw in reason_lower for kw in ["defect", "damage", "broken", "doesn't work", "not working"]
    )

    if not order.get("delivery_date"):
        return {
            "decision": "escalate",
            "rule_applied": "RULE_12",
            "explanation": (
                "Order has no delivery date on file and isn't flagged as "
                "lost/misdelivered. This scenario isn't cleanly covered "
                "by Rules 1-9, escalating per Rule 12."
            ),
        }

    days_elapsed = _days_since(order["delivery_date"])

    if is_defect_claim:
        # RULE 2 -- defective items get a 60-day window, evidence required
        if days_elapsed <= 60:
            return {
                "decision": "approve",
                "rule_applied": "RULE_2",
                "explanation": (
                    f"Customer reports a defect/damage claim, {days_elapsed} "
                    "days since delivery. Per Rule 2, defective items have "
                    "a 60-day window. Eligible, pending evidence review."
                ),
            }
        return {
            "decision": "deny",
            "rule_applied": "RULE_2",
            "explanation": (
                f"Customer reports a defect/damage claim, but {days_elapsed} "
                "days have passed since delivery -- beyond the 60-day "
                "defective-item window in Rule 2."
            ),
        }

    # RULE 1 -- standard 30-day window
    if days_elapsed <= 30:
        return {
            "decision": "approve",
            "rule_applied": "RULE_1",
            "explanation": (
                f"Request is within the standard 30-day window "
                f"({days_elapsed} days since delivery). Eligible per Rule 1."
            ),
        }

    return {
        "decision": "deny",
        "rule_applied": "RULE_1",
        "explanation": (
            f"Request is outside the standard 30-day refund window "
            f"({days_elapsed} days since delivery, {days_elapsed - 30} days "
            "over). Per Rule 1, this applies regardless of membership tier "
            "or order history (Rule 8)."
        ),
    }
