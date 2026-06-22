"""
Reasoning log: records every step of the agent loop (tool calls, retries,
failures, final decisions) as structured events, and broadcasts them to
any connected WebSocket clients (the admin dashboard) in real time.

This is the single piece of infrastructure that satisfies both the
"reasoning logs" and "show retries/failures" requirements -- every event
that happens inside agent.py gets written here, and the admin dashboard
is just a live tail of this log.

IMPORTANT IMPLEMENTATION NOTE: log_event() is called from inside
run_agent_turn(), which FastAPI's /api/chat route calls from a
*synchronous* request handler. FastAPI runs sync handlers in a worker
thread, not on the main asyncio event loop. asyncio.get_event_loop()
called from that worker thread does NOT reliably return the loop the
WebSocket connections are actually running on -- in practice this
silently no-ops the broadcast (the exact bug that made the admin
dashboard appear to "not work live" despite events being logged
correctly to disk). The fix: main.py captures a reference to the real
running loop once at startup (via a FastAPI startup event) and stores
it here; log_event() then uses asyncio.run_coroutine_threadsafe(), the
correct cross-thread-to-event-loop primitive, instead of
asyncio.create_task() (which only works when already running on that
same loop).
"""
import asyncio
import json
import os
from datetime import datetime
from typing import Optional

LOG_PATH = os.path.join(os.path.dirname(__file__), "logs", "agent_trace.jsonl")

# Connected WebSocket clients (admin dashboard tabs), populated by main.py
_subscribers: list = []

# The main asyncio event loop, captured once at FastAPI startup by main.py.
# Needed so log_event() (called from sync request-handler worker threads)
# can correctly schedule a broadcast onto the loop the WebSocket
# connections actually live on.
_main_loop = None


def set_main_loop(loop):
    global _main_loop
    _main_loop = loop


def register_subscriber(ws):
    _subscribers.append(ws)


def unregister_subscriber(ws):
    if ws in _subscribers:
        _subscribers.remove(ws)


async def _broadcast(event: dict):
    dead = []
    for ws in _subscribers:
        try:
            await ws.send_json(event)
        except Exception:
            dead.append(ws)
    for ws in dead:
        unregister_subscriber(ws)


def log_event(
    session_id: str,
    step_type: str,
    name: str,
    input_data: Optional[dict] = None,
    output_data: Optional[dict] = None,
    status: str = "success",
    latency_ms: Optional[int] = None,
):
    """
    Record one event in the agent's reasoning trace.

    step_type: "tool_call" | "retry" | "llm_call" | "decision" | "error"
    name: tool/function name, or "final_decision"
    status: "success" | "failed" | "retrying"
    """
    event = {
        "session_id": session_id,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "step_type": step_type,
        "name": name,
        "input": input_data,
        "output": output_data,
        "status": status,
        "latency_ms": latency_ms,
    }

    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(event) + "\n")

    # Broadcast to any connected admin dashboards. Works correctly whether
    # log_event() is called from the main event loop (e.g. inside an async
    # route) or from a worker thread (e.g. inside a sync route, which is
    # how /api/chat actually runs) -- run_coroutine_threadsafe is the
    # primitive designed for exactly this cross-thread case.
    if _main_loop is not None and _subscribers:
        try:
            asyncio.run_coroutine_threadsafe(_broadcast(event), _main_loop)
        except Exception:
            pass  # don't let a broadcast failure break the actual agent logic

    return event


def get_all_events(session_id: Optional[str] = None) -> list:
    if not os.path.exists(LOG_PATH):
        return []
    events = []
    with open(LOG_PATH) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            event = json.loads(line)
            if session_id is None or event.get("session_id") == session_id:
                events.append(event)
    return events
