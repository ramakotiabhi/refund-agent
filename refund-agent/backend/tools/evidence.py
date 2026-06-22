"""
Evidence tool: analyzes a customer-submitted image for damage claims.

STATUS: MOCKED. This is the optional "evidence verification" feature
from the original design. It is intentionally NOT load-bearing for the
core approve/deny/escalate flow -- check_refund_policy() already handles
defect claims via Rule 2 without requiring this tool to succeed. This
tool adds *advisory* signal on top, exactly as Rule 11 specifies
("Evidence review is advisory; final eligibility is still governed by
Rules 1-4").

Why mocked: real evidence analysis needs a vision-capable LLM call
(Claude supports image input directly) and real uploaded images. Rather
than fake those out with a second LLM provider, we stub the *response
shape* now so the rest of the system (logging, UI, decision flow) is
fully wired. Swapping in a real call is a ~15 line change -- see
analyze_evidence_real() below for the drop-in version once ANTHROPIC_API_KEY
is set and real images are available.
"""
import random

MOCK_RESPONSES = [
    {
        "damage_detected": True,
        "confidence": 0.91,
        "description": (
            "Image shows a visible crack along the housing and a "
            "discolored panel consistent with the customer's damage claim."
        ),
    },
    {
        "damage_detected": True,
        "confidence": 0.74,
        "description": (
            "Image shows wear consistent with use, but visual evidence of "
            "the specific defect described is inconclusive."
        ),
    },
    {
        "damage_detected": False,
        "confidence": 0.85,
        "description": (
            "No visible damage detected in the submitted image. Item "
            "appears to be in normal condition."
        ),
    },
]


def analyze_evidence(image_url_or_description: str) -> dict:
    """
    MOCKED. Analyzes a piece of customer-submitted evidence (image,
    description) for a damage/defect claim.

    In production, this would be:
        response = anthropic_client.messages.create(
            model="claude-sonnet-4-6",
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {...}},
                {"type": "text", "text": "Does this image show product damage consistent with the customer's claim? Respond with confidence and description."}
            ]}]
        )
    For this build, we return a deterministic-but-varied mock so the
    admin dashboard and decision flow can display and log a realistic
    result without requiring an uploaded file or API key.
    """
    result = random.choice(MOCK_RESPONSES)
    return {
        "mocked": True,
        "input_received": image_url_or_description,
        **result,
        "note": "This is a MOCKED response. Real vision analysis requires ANTHROPIC_API_KEY and an uploaded image.",
    }


def analyze_evidence_real(image_base64: str, media_type: str, claim_description: str, anthropic_client) -> dict:
    """
    DROP-IN REPLACEMENT once you have a real API key and real images.
    Not called anywhere yet -- wire this in to evidence routes when ready.
    """
    response = anthropic_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": media_type, "data": image_base64},
                    },
                    {
                        "type": "text",
                        "text": (
                            f"The customer claims: '{claim_description}'. Does this image show "
                            "product damage/defect consistent with that claim? Respond in JSON: "
                            '{"damage_detected": bool, "confidence": float, "description": str}'
                        ),
                    },
                ],
            }
        ],
    )
    return {"mocked": False, "raw_response": response.content[0].text}
