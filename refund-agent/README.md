# Refund Agent

An AI customer support agent that approves, denies, or escalates
e-commerce refund requests against a strict, deterministic policy —
built as a single tool-calling agent loop, not a chain of LLM agents.

This was built for a take-home assessment. The sections below explain
not just *what* this does, but *why* it's built this way — the
architecture decisions are the actual point of the exercise.

---

## TL;DR — run it in under 2 minutes

```bash
cd backend
pip install -r requirements.txt --break-system-packages
python3 generate_orders.py        # regenerates order dates relative to today
uvicorn main:app --reload --port 8000
```

Then open `http://localhost:8000/` in a browser for the customer chat,
and `http://localhost:8000/admin` in another tab for the live reasoning
trace. Same app, same port, no separate frontend server needed. No
build step, no API key required — it runs in **mock LLM mode** by
default (see [Mock mode vs. real Claude](#mock-mode-vs-real-claude)
below).

To sanity-check the whole system without even opening a browser:

```bash
cd backend
python3 demo_scenarios.py
```

This runs 10 scenarios (approvals, denials, escalations, edge cases)
straight through the real agent loop and prints each exchange.

---

## The core design decision: one agent, not seven

The original brief (and most "production" reference designs for this
kind of system) suggests a multi-agent architecture: a CRM agent, a
policy agent, a fraud agent, a memory agent, an evidence agent, a
decision agent, all orchestrated by something like LangGraph.

**This repo deliberately does not do that**, and that's worth explaining
rather than glossing over.

Most of those "agents" don't need an LLM at all:

| Task | Does it need judgment/language understanding? | Implementation here |
|---|---|---|
| Look up a customer or order | No — it's a DB read | Plain Python function |
| Check refund eligibility | No — it's rule evaluation | Plain Python function (`tools/policy.py`) |
| Score fraud risk | No — it's threshold math | Plain Python function (`tools/fraud.py`) |
| Decide what to say to the customer, in what order to gather info | **Yes** | The one LLM call in the loop |

Wrapping deterministic logic in an LLM call (or a LangGraph node) adds
latency, cost, and a new way for things to silently drift or hallucinate
— for zero benefit, since the underlying operation is already a pure
function. It also makes the policy **less** strict, not more: an LLM
"interpreting" a policy document on every request is a policy that can
be talked around. A Python `if` statement cannot.

So this system has **one agent** (a Claude tool-calling loop in
`backend/agent.py`) that:
1. Understands the customer's request,
2. Decides which tools to call and in what order,
3. Never makes the actual approve/deny/escalate decision itself — that
   comes back from `check_refund_policy()` and `check_fraud_signals()`,
   which are deterministic,
4. Explains the outcome to the customer in natural language, citing the
   specific policy rule that applied.

This is also why there's no LangGraph/CrewAI dependency: the loop is
~80 lines in `agent.py` and is easier to read, debug, and demo in a
code walkthrough than a multi-node graph would be.

If this were scoped for an actual production rollout with a much larger
product catalog, a real fraud team, and genuinely ambiguous evidence
review, several of these *would* become worth their own model calls
(image/video evidence analysis is the clearest candidate — see below).
For 15 mock customers and a documented rule set, that complexity isn't
earned yet.

---

## Architecture

```
Customer (chat or, in future, voice)
        │
        ▼
┌──────────────────────────────┐
│   Agent loop (Claude)        │   <- the ONLY LLM call
│   backend/agent.py           │
└──────────────────────────────┘
        │
        ├──► lookup_customer(id/email)         tools/crm.py
        ├──► lookup_order(order_id)             tools/crm.py
        ├──► check_refund_policy(order, reason) tools/policy.py   (deterministic rule engine)
        ├──► check_fraud_signals(customer)      tools/fraud.py    (deterministic scoring)
        ├──► analyze_evidence(image)             tools/evidence.py (mocked, advisory only)
        └──► escalate_to_human(reason)          tools/escalation.py
        │
        ▼
Every tool call + input + output + latency + retries
        │
        ▼
reasoning_log.py ──► logs/agent_trace.jsonl ──► WebSocket ──► Admin dashboard (live)
```

### Repository structure

```
refund-agent/
├── backend/
│   ├── agent.py              # the tool-calling loop (the core of the project)
│   ├── llm_client.py         # real Claude call OR deterministic mock, same interface
│   ├── reasoning_log.py      # structured event logging + WebSocket broadcast
│   ├── voice_pipeline.py     # mocked STT/TTS, wired to the same agent loop
│   ├── main.py                # FastAPI app: /api/chat, /ws/admin, etc.
│   ├── demo_scenarios.py     # run all key scenarios end-to-end, no server needed
│   ├── generate_orders.py    # regenerates orders.json with dates relative to today
│   ├── tools/
│   │   ├── crm.py            # customer/order lookups (pure data access)
│   │   ├── policy.py          # the refund policy as actual code -- the strict part
│   │   ├── fraud.py           # fraud/abuse signal scoring
│   │   ├── escalation.py      # manual review hand-off
│   │   └── evidence.py        # MOCKED image/evidence analysis
│   ├── data/
│   │   ├── customers.json     # 15 mock customers, edge cases by design
│   │   ├── orders.json        # generated -- see generate_orders.py
│   │   └── refund_policy.txt  # the human-readable policy; policy.py implements it
│   ├── logs/                   # generated at runtime, gitignored
│   ├── .env.example
│   └── requirements.txt
├── frontend/
│   ├── index.html             # customer chat interface
│   └── admin.html             # live reasoning-trace dashboard
├── render.yaml                 # one-click backend deploy config (see Deploying section)
├── .gitignore
└── README.md
```

---

## Mock mode vs. real Claude

This repo ships with **no API key required**. `backend/llm_client.py`
checks for `ANTHROPIC_API_KEY`:

- **Not set (default):** falls back to a deterministic mock LLM that
  simulates real tool-calling behavior — it inspects the conversation
  and calls tools in the same sequence a real model would (lookup
  customer → lookup order → check policy → check fraud → escalate if
  needed → respond). This exercises 100% of the pipeline — tool
  orchestration, retries, logging, the dashboard — with zero API cost.
- **Set:** the exact same code path calls the real Claude API
  (`claude-sonnet-4-6`) with tool-calling enabled. No other code changes
  needed.

To switch on real Claude:

```bash
cd backend
cp .env.example .env
# edit .env and paste your key into ANTHROPIC_API_KEY=
```

**On API key hygiene:** never paste a real key into a chat tool, issue
tracker, commit message, or anywhere else it could be logged. `.env` is
gitignored in this repo specifically so a real key never accidentally
gets committed. If a key is ever exposed in plaintext somewhere it
shouldn't be, rotate it immediately in the Anthropic Console rather than
assuming it's fine.

---

## The refund policy

`backend/data/refund_policy.txt` is the human-readable source of truth
(12 rules). `backend/tools/policy.py` implements those exact rules as
code. Keep the two in sync if you edit one.

Summary of what's covered:
- Standard 30-day refund window from delivery date
- 60-day window for defective/damaged items (evidence required/advisory)
- Digital goods: non-refundable once activated (escalate if technical
  fault claimed)
- Final sale/clearance: non-refundable, overrides the window
- Fraud signal: >2 refunds in 30 days → escalate, never auto-decide
- Lost in transit / wrong item delivered: approve regardless of window
  (seller/fulfillment error, not a customer-initiated return)
- Membership tier never overrides a time-window rule
- Anything ambiguous → escalate rather than guess

## Mock data — the 15 customers

`backend/data/customers.json` and `orders.json` are deliberately built
to cover every rule above, not just happy-path cases. Notable IDs for a
demo:

| Customer / Order | Scenario |
|---|---|
| `CUST001` / `ORD1001` | Clean standard approval |
| `CUST005` / `ORD1005` | **Edge case:** 5 days past the 30-day window — denial |
| `CUST006` / `ORD1006` | **Edge case:** platinum-tier customer, still denied (tier ≠ exception) |
| `CUST004` / `ORD1004` | **Edge case:** 3 refunds in 30 days → fraud escalation |
| `CUST012` / `ORD1012` | **Edge case:** heavy refund history → escalation |
| `CUST008` / `ORD1008` | Digital good — denied |
| `CUST010` / `ORD1010` | Final sale item — denied |
| `CUST013` / `ORD1013` | Boundary test: exactly day 30 — approved |
| `CUST014` / `ORD1014` | Lost in transit — approved regardless of time |
| `CUST015` / `ORD1015` | Wrong item delivered — approved regardless of time |
| `CUST007` / `ORD1007` | Defective item within 60-day window — approved |

**Note:** order dates are generated relative to *today* by
`generate_orders.py` (not hardcoded), so the "5 days past the window"
edge case stays a genuine edge case no matter when you run this. Re-run
`python3 generate_orders.py` if you've cloned this more than a day or
two after it was last generated.

---

## Reasoning logs & retry handling

Every tool call — input, output, latency, and outcome — is written to
`backend/logs/agent_trace.jsonl` and streamed live over WebSocket
(`/ws/admin`) to the admin dashboard.

To make retry handling visible without waiting for a real flaky
dependency, `agent.py` deliberately simulates **one transient failure**
on `lookup_order` per session (a `ConnectionError`, as if a downstream
DB timed out). The agent retries automatically once; if the retry also
fails, it surfaces the error as a tool result rather than crashing, and
the LLM can choose to escalate. This is called out in the code comments
— it's a deliberate demo aid, not a hidden bug, and the retry/backoff
pattern (`tools/escalation.py` + `_call_tool_with_retry` in `agent.py`)
is exactly what you'd keep in production, just against a real flaky
dependency instead of a scripted one.

The admin dashboard (`frontend/admin.html`) color-codes event types
(tool call / retry / error / decision) and also shows a live escalation
queue pulled from `/api/escalations`.

---

## What's mocked, and why

Being upfront about this is part of the point of the exercise — a take-home
assessment rewards correct scoping more than feature count.

| Feature | Status | Why |
|---|---|---|
| Core agent loop, tool calling | **Real**, fully functional | This is the graded core |
| Refund policy enforcement | **Real**, deterministic | The "strict policy" requirement |
| Fraud signal scoring | **Real**, deterministic | Simple threshold logic, no LLM needed |
| Reasoning logs / admin dashboard | **Real**, live via WebSocket | Directly graded |
| Retry-on-failure handling | **Real**, demonstrated via one simulated transient failure | Directly graded |
| LLM conversation (mock mode) | **Simulated** — deterministic pattern-matching | No API key needed to review the system |
| LLM conversation (real mode) | **Real** Claude calls, same code path | Drop in `ANTHROPIC_API_KEY` to activate |
| Evidence/image analysis | **Mocked** response shape (`tools/evidence.py`) | Not in the original requirements; advisory-only by design (Rule 11) — built to show the integration point, not faked as a load-bearing feature |
| Voice (STT/TTS) | **Scaffolded**, mocked transcription/synthesis (`voice_pipeline.py`) | Bonus requirement; shown as a transport layer into the *same* agent loop, since that's the architecturally correct way to add it — not built against a live voice API for this submission |

If extending this further, the next real increment would be wiring
`tools/evidence.py`'s `analyze_evidence_real()` (already stubbed) to an
actual Claude vision call with uploaded images, and `voice_pipeline.py`
to OpenAI Realtime or ElevenLabs — both are designed so that wiring them
in doesn't touch `agent.py` at all.

---

## Deploying this publicly

This repo isn't deployed by default — it's designed to run locally for
review. If you want a live public link (e.g. to share alongside the
Loom video), this is now a **single deployment, one platform, one URL**
— the FastAPI backend serves the frontend directly, so there's no
separate static host to wire up.

**Render (one service, free tier, supports WebSockets)**
1. Push this repo to GitHub.
2. On [render.com](https://render.com): **New +** → **Blueprint** (not
   "Web Service" — the Blueprint option is what actually reads
   `render.yaml`). Connect the repo.
3. Render auto-detects `render.yaml` and pre-fills: root directory
   `backend`, build command `pip install -r requirements.txt`, start
   command `uvicorn main:app --host 0.0.0.0 --port $PORT`.
4. Optionally set `ANTHROPIC_API_KEY` (or `OPENAI_API_KEY`) in the
   Render dashboard's Environment tab to enable real LLM calls. Leave
   both unset to run in mock mode — works fine either way.
5. Render gives you one URL, e.g. `https://refund-agent.onrender.com`.
   - The customer chat is at the root: `https://refund-agent.onrender.com/`
   - The admin dashboard is at: `https://refund-agent.onrender.com/admin`

That's it — no Netlify, no `?api=` query params, no cross-origin
wiring. One service serves both the UI and the API, which also means
the admin dashboard's WebSocket connection is automatically same-origin
and can't hit the CORS/protocol mismatches a two-service split invites.

**Note on Render's free tier:** free web services spin down after
inactivity and take ~30-50 seconds to wake on the next request. If
you're demoing live, hit `/api/health` a minute beforehand to warm it
up.

---



| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/chat` | Send a customer message, get the agent's reply + session ID |
| `GET` | `/api/sessions/{id}/log` | Full reasoning trace for one session |
| `WS` | `/ws/admin` | Live stream of all reasoning events |
| `GET` | `/api/escalations` | Current manual-review queue |
| `GET` | `/api/customers` | Mock CRM data |
| `GET` | `/api/orders` | Mock order data |
| `GET` | `/api/health` | Health check |

---

## Known limitations (intentional, given scope)

- **In-memory session store.** Conversation history lives in a Python
  dict in `main.py`, not a database. Fine for a demo; a restart clears
  active sessions. Swapping for Redis/Postgres would be a small change
  if this needed to survive restarts or scale past one process.
- **No auth.** There's no login/auth layer on either the chat or admin
  endpoints. Not in scope for this assessment; would be required before
  any real deployment.
- **CORS is wide open** (`allow_origins=["*"]`) for local demo
  convenience — tighten this before deploying anywhere real.
- **Static HTML frontend, not Next.js.** Chosen deliberately: zero build
  step means anyone reviewing this can open the two HTML files directly
  in a browser with nothing to install. The API is plain REST +
  WebSocket, so porting to Next.js later is straightforward if needed.



## Future Enhancements

**If I had more time, there are several directions I would take this project:**

1. Image-based damage verification using vision models to compare customer-uploaded photos with warehouse and delivery images for more accurate claim validation.
2. Real-time voice support by integrating speech-to-text and text-to-speech services, allowing customers to interact with the agent over phone calls.
3. Multi-language support so customers can communicate in their preferred language while keeping the same policy engine underneath.
4. Advanced fraud detection using additional signals such as account history, device fingerprints, and behavioral patterns.
5. CRM and e-commerce integrations with platforms like Shopify, Salesforce, or custom databases instead of the current demo dataset.
6. Human-in-the-loop workflows where support agents can review and act on escalated cases directly from the admin dashboard.
7. Automated evaluation and testing to continuously validate agent decisions against policy rules and ensure consistent behavior.

The current architecture was intentionally designed with modular tools, making these enhancements possible without major changes to the core agent workflow.
