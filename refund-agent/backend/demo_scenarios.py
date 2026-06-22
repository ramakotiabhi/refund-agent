"""
Runs every key demo scenario through the agent loop end-to-end and prints
the result. Useful for:
  - Verifying the whole system works after setup (no server needed)
  - Quick reference for which customer/order IDs map to which scenario
  - Re-checking nothing broke after editing policy.py or fraud.py

Run: python3 demo_scenarios.py
"""
from agent import run_agent_turn, new_session_id

SCENARIOS = [
    ("Standard approval", "Hi, order ORD1001, customer CUST001, I changed my mind and want a refund"),
    ("EDGE CASE: past the 30-day window", "Hi, order ORD1005, customer CUST005, I changed my mind and want a refund"),
    ("EDGE CASE: fraud signal (3 refunds/30d)", "Hi, order ORD1004, customer CUST004, item arrived damaged"),
    ("EDGE CASE: VIP tier does not override window", "Hi, order ORD1006, customer CUST006, I changed my mind and want a refund"),
    ("Digital good -- non-refundable", "Hi, order ORD1008, customer CUST008, I want a refund on this software license"),
    ("Final sale / clearance item", "Hi, order ORD1010, customer CUST010, I want a refund, changed my mind"),
    ("Lost in transit -- approve regardless of window", "Hi, order ORD1014, customer CUST014, my order never arrived"),
    ("Wrong item delivered -- approve regardless of window", "Hi, order ORD1015, customer CUST015, I got sent the wrong item"),
    ("Defective item within 60-day window", "Hi, order ORD1007, customer CUST007, the item arrived defective and damaged"),
    ("Boundary test: exactly day 30", "Hi, order ORD1013, customer CUST013, I changed my mind and want a refund"),
]


def main():
    print("=" * 78)
    print("REFUND AGENT -- DEMO SCENARIO RUN")
    print("=" * 78)

    for label, message in SCENARIOS:
        session = new_session_id()
        result = run_agent_turn(session, [], message)
        print(f"\n--- {label} ---")
        print(f"  Input:  {message}")
        print(f"  Reply:  {result['reply']}")

    print("\n" + "=" * 78)
    print("Done. Full structured trace for every step above is in logs/agent_trace.jsonl")
    print("=" * 78)


if __name__ == "__main__":
    main()
