"""
Generates orders.json with delivery dates relative to TODAY.

Why this exists: refund-window logic depends on "days since delivery."
If we hardcode dates, the dataset silently goes stale and demo scenarios
that are supposed to be edge cases (e.g. "5 days past the window") stop
being edge cases a month from now. Running this script regenerates the
dataset against the current date.

Run: python3 generate_orders.py
"""
import json
from datetime import date, timedelta

TODAY = date.today()


def days_ago(n: int) -> str:
    return (TODAY - timedelta(days=n)).isoformat()


ORDERS = [
    # CUST001 -- clean, standard approval. Delivered 10 days ago, well within 30-day window.
    {
        "order_id": "ORD1001",
        "customer_id": "CUST001",
        "product_name": "Wireless Mechanical Keyboard",
        "category": "electronics",
        "amount": 89.99,
        "purchase_date": days_ago(12),
        "delivery_date": days_ago(10),
        "delivery_status": "delivered",
        "is_final_sale": False,
        "is_digital": False,
    },
    # CUST002 -- first-time refund, within window
    {
        "order_id": "ORD1002",
        "customer_id": "CUST002",
        "product_name": "Ceramic Coffee Mug Set",
        "category": "home",
        "amount": 24.50,
        "purchase_date": days_ago(15),
        "delivery_date": days_ago(13),
        "delivery_status": "delivered",
        "is_final_sale": False,
        "is_digital": False,
    },
    # CUST003 -- gold member, normal valid refund
    {
        "order_id": "ORD1003",
        "customer_id": "CUST003",
        "product_name": "Running Shoes - Size 9",
        "category": "apparel",
        "amount": 64.00,
        "purchase_date": days_ago(8),
        "delivery_date": days_ago(6),
        "delivery_status": "delivered",
        "is_final_sale": False,
        "is_digital": False,
    },
    # CUST004 -- fraud signal case (3 refunds in 30 days), this order itself is technically valid
    {
        "order_id": "ORD1004",
        "customer_id": "CUST004",
        "product_name": "Bluetooth Speaker",
        "category": "electronics",
        "amount": 45.00,
        "purchase_date": days_ago(9),
        "delivery_date": days_ago(7),
        "delivery_status": "delivered",
        "is_final_sale": False,
        "is_digital": False,
    },
    # CUST005 -- EDGE CASE: delivered 35 days ago, request is past the 30-day window
    {
        "order_id": "ORD1005",
        "customer_id": "CUST005",
        "product_name": "Yoga Mat",
        "category": "fitness",
        "amount": 32.00,
        "purchase_date": days_ago(37),
        "delivery_date": days_ago(35),
        "delivery_status": "delivered",
        "is_final_sale": False,
        "is_digital": False,
    },
    # CUST006 -- VIP/platinum but delivered 40 days ago. Tests that tier does NOT override hard window.
    {
        "order_id": "ORD1006",
        "customer_id": "CUST006",
        "product_name": "Leather Office Chair",
        "category": "furniture",
        "amount": 310.00,
        "purchase_date": days_ago(42),
        "delivery_date": days_ago(40),
        "delivery_status": "delivered",
        "is_final_sale": False,
        "is_digital": False,
    },
    # CUST007 -- damaged item, within 60-day defective window
    {
        "order_id": "ORD1007",
        "customer_id": "CUST007",
        "product_name": "Glass Dining Table",
        "category": "furniture",
        "amount": 220.00,
        "purchase_date": days_ago(45),
        "delivery_date": days_ago(43),
        "delivery_status": "delivered",
        "is_final_sale": False,
        "is_digital": False,
    },
    # CUST008 -- digital download, non-refundable once activated
    {
        "order_id": "ORD1008",
        "customer_id": "CUST008",
        "product_name": "Pro Photo Editing Software License",
        "category": "software",
        "amount": 59.99,
        "purchase_date": days_ago(3),
        "delivery_date": days_ago(3),
        "delivery_status": "delivered",
        "is_final_sale": False,
        "is_digital": True,
    },
    # CUST009 -- normal gold customer, recent valid refund
    {
        "order_id": "ORD1009",
        "customer_id": "CUST009",
        "product_name": "Wool Winter Jacket",
        "category": "apparel",
        "amount": 140.00,
        "purchase_date": days_ago(14),
        "delivery_date": days_ago(12),
        "delivery_status": "delivered",
        "is_final_sale": False,
        "is_digital": False,
    },
    # CUST010 -- final sale / clearance item, non-refundable
    {
        "order_id": "ORD1010",
        "customer_id": "CUST010",
        "product_name": "Clearance Desk Lamp",
        "category": "home",
        "amount": 15.00,
        "purchase_date": days_ago(6),
        "delivery_date": days_ago(4),
        "delivery_status": "delivered",
        "is_final_sale": True,
        "is_digital": False,
    },
    # CUST011 -- standard valid refund
    {
        "order_id": "ORD1011",
        "customer_id": "CUST011",
        "product_name": "Stainless Steel Water Bottle",
        "category": "home",
        "amount": 18.99,
        "purchase_date": days_ago(11),
        "delivery_date": days_ago(9),
        "delivery_status": "delivered",
        "is_final_sale": False,
        "is_digital": False,
    },
    # CUST012 -- high fraud signal, order itself looks valid (within window)
    {
        "order_id": "ORD1012",
        "customer_id": "CUST012",
        "product_name": "Noise Cancelling Headphones",
        "category": "electronics",
        "amount": 130.00,
        "purchase_date": days_ago(7),
        "delivery_date": days_ago(5),
        "delivery_status": "delivered",
        "is_final_sale": False,
        "is_digital": False,
    },
    # CUST013 -- BOUNDARY TEST: delivered exactly 30 days ago (last valid day)
    {
        "order_id": "ORD1013",
        "customer_id": "CUST013",
        "product_name": "Espresso Machine",
        "category": "home",
        "amount": 175.00,
        "purchase_date": days_ago(32),
        "delivery_date": days_ago(30),
        "delivery_status": "delivered",
        "is_final_sale": False,
        "is_digital": False,
    },
    # CUST014 -- never delivered (lost in transit), separate policy rule
    {
        "order_id": "ORD1014",
        "customer_id": "CUST014",
        "product_name": "Portable Projector",
        "category": "electronics",
        "amount": 210.00,
        "purchase_date": days_ago(20),
        "delivery_date": None,
        "delivery_status": "lost_in_transit",
        "is_final_sale": False,
        "is_digital": False,
    },
    # CUST015 -- wrong item received, separate policy rule (seller error)
    {
        "order_id": "ORD1015",
        "customer_id": "CUST015",
        "product_name": "Cast Iron Skillet",
        "category": "home",
        "amount": 38.00,
        "purchase_date": days_ago(16),
        "delivery_date": days_ago(14),
        "delivery_status": "delivered_wrong_item",
        "is_final_sale": False,
        "is_digital": False,
    },
]

if __name__ == "__main__":
    with open("data/orders.json", "w") as f:
        json.dump(ORDERS, f, indent=2)
    print(f"Generated {len(ORDERS)} orders relative to {TODAY.isoformat()} -> data/orders.json")
