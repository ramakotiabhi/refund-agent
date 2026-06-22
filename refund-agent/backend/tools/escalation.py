"""
Escalation tool: hands a case off to manual human review.

This is the agent's "I'm not deciding this" path -- used for fraud
signals (Rule 5), ambiguous cases (Rule 12), or anything the policy
engine couldn't cleanly resolve. Escalating is a first-class outcome,
not a failure state.
"""
import json
import os
import uuid
from datetime import datetime

ESCALATIONS_PATH = os.path.join(os.path.dirname(__file__), "..", "logs", "escalations.json")


def escalate_to_human(customer_id: str, order_id: str, reason: str) -> dict:
    """
    File a case for manual human review and return a case ID.
    """
    case = {
        "case_id": f"ESC-{uuid.uuid4().hex[:8].upper()}",
        "customer_id": customer_id,
        "order_id": order_id,
        "reason": reason,
        "status": "pending_review",
        "created_at": datetime.utcnow().isoformat() + "Z",
    }

    existing = []
    if os.path.exists(ESCALATIONS_PATH):
        with open(ESCALATIONS_PATH) as f:
            try:
                existing = json.load(f)
            except json.JSONDecodeError:
                existing = []

    existing.append(case)
    os.makedirs(os.path.dirname(ESCALATIONS_PATH), exist_ok=True)
    with open(ESCALATIONS_PATH, "w") as f:
        json.dump(existing, f, indent=2)

    return {
        "escalated": True,
        "case_id": case["case_id"],
        "message": (
            f"This case has been escalated to manual review under case "
            f"{case['case_id']}. A specialist will follow up within 1-2 "
            "business days."
        ),
    }
