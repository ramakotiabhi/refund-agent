"""
CRM tools: customer and order lookups.

These are plain data-access functions. No LLM is involved in retrieving
or interpreting this data -- it's a lookup, not a reasoning task. Keeping
this deterministic means the agent's "facts" are always grounded in the
actual mock DB, never hallucinated.
"""
import json
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

with open(os.path.join(DATA_DIR, "customers.json")) as f:
    _CUSTOMERS = {c["customer_id"]: c for c in json.load(f)}
    _CUSTOMERS_BY_EMAIL = {c["email"].lower(): c for c in _CUSTOMERS.values()}

with open(os.path.join(DATA_DIR, "orders.json")) as f:
    _ORDERS = {o["order_id"]: o for o in json.load(f)}


def lookup_customer(identifier: str) -> dict:
    """
    Look up a customer by customer_id or email.
    Returns the customer record, or an error dict if not found.
    """
    identifier = identifier.strip()
    if identifier in _CUSTOMERS:
        return {"found": True, "customer": _CUSTOMERS[identifier]}

    by_email = _CUSTOMERS_BY_EMAIL.get(identifier.lower())
    if by_email:
        return {"found": True, "customer": by_email}

    return {"found": False, "error": f"No customer found matching '{identifier}'."}


def lookup_order(order_id: str) -> dict:
    """
    Look up an order by order_id. Returns the order record, or an error
    dict if not found.
    """
    order_id = order_id.strip().upper()
    order = _ORDERS.get(order_id)
    if not order:
        return {"found": False, "error": f"No order found with ID '{order_id}'."}
    return {"found": True, "order": order}


def lookup_orders_for_customer(customer_id: str) -> dict:
    """
    Return all orders belonging to a given customer_id. Useful when a
    customer references "my recent order" without giving an order ID.
    """
    matches = [o for o in _ORDERS.values() if o["customer_id"] == customer_id]
    return {"found": bool(matches), "orders": matches}
