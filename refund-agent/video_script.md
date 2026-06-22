# Refund Agent — Explainer Video Script
### Target length: 2:30–3:00 minutes

This script is written to be read aloud at a natural, slightly brisk pace
(~150 words/minute). Each block lists: the TIME marker, what's ON SCREEN,
and the NARRATION to read or feed into a TTS tool.

If using a TTS tool (ElevenLabs, etc.): copy just the text inside the
NARRATION quotes for each scene into the tool, generate each clip
separately, then lay them over the matching screen recording in your
video editor. Leave ~1 second of silence between scenes for breathing
room when you stitch clips together.

If recording live: read directly off this script, glance at "ON SCREEN"
cues to know when to click/type.

---

## SCENE 1 — Open on vision (0:00–0:25)

**ON SCREEN:** Title card or just the README open, or your face on camera.
Keep it simple — text doesn't need to move yet.

**NARRATION:**
"Every e-commerce company faces the same problem: refund requests come
in by the thousands, and every single one needs a consistent, defensible
decision. Too lenient, and you bleed margin to abuse. Too strict, and
you lose loyal customers over a five-day technicality.

This is a refund support agent that solves that problem — not by asking
an AI to 'use its judgment,' but by giving it a strict, deterministic
policy engine to enforce, and just enough language understanding to
explain that decision like a human would."

---

## SCENE 2 — The architecture decision, in one sentence (0:25–0:50)

**ON SCREEN:** Switch to the architecture diagram in the README, or the
`agent.py` file open in your editor, scrolled to the top where the
SYSTEM_PROMPT and tool list are visible.

**NARRATION:**
"Here's the core design decision: this is one agent, not seven. The
language model's only job is to understand the customer, decide which
tool to call, and explain the outcome. It never decides eligibility
itself. That decision comes from plain, testable Python functions —
a policy engine and a fraud-scoring function — so the rules can't drift
or get talked around, no matter how the conversation goes."

---

## SCENE 3 — Live demo: standard approval (0:50–1:15)

**ON SCREEN:** `frontend/index.html` open in browser. Type and send:
"Hi, order ORD1001, customer CUST001, I changed my mind and want a
refund" — let the reply render on screen.

**NARRATION:**
"Let's see it work. A standard request, well within the thirty-day
window — clean approval, and the agent cites the exact rule it applied."

*(Let on-screen text "Good news — your refund has been approved...
Eligible per Rule 1" be visible/readable for at least 3 seconds before
cutting.)*

---

## SCENE 4 — Live demo: holding the line (1:15–1:50)

**ON SCREEN:** Same chat window. Type: "Hi, order ORD1005, customer
CUST005, I changed my mind and want a refund" — show the denial. Then
type a pushback line: "I've been a loyal customer for years, please
make an exception!" — show that the agent holds the same answer.

**NARRATION:**
"Now the harder case — a request five days past the window. The agent
denies it and names the specific rule. Watch what happens when the
customer pushes back emotionally..."

*(pause while the pushback message sends and reply renders)*

"...it holds the line. Because the decision isn't coming from the
model's mood in the moment — it's coming from the same deterministic
check, every time. That consistency is the entire point."

---

## SCENE 5 — The admin dashboard / reasoning trace (1:50–2:15)

**ON SCREEN:** Switch to `frontend/admin.html` in a second tab/window.
Point out the live trace: tool_call, retry, decision rows.

**NARRATION:**
"Every one of those decisions is fully auditable. This is the admin
dashboard — every tool call the agent makes, including a simulated
retry when a lookup fails transiently, streamed live. Nothing the agent
decides is a black box; a support team can see exactly why any refund
was approved, denied, or escalated."

---

## SCENE 6 — Where this goes next / why it matters at Amazon-scale (2:15–2:50)

**ON SCREEN:** Back to README or a simple text slide listing: "Voice •
Evidence/image analysis • Multi-language • Fraud model upgrade."

**NARRATION:**
"Right now this runs on fifteen mock customers and a documented policy
— deliberately scoped, so the core logic is provable end to end. But the
shape is built to extend. Voice is already wired as a transport layer
into the same agent loop — speech in, speech out, no change to the
decision logic. Image and video evidence review is scaffolded the same
way, ready to plug into a real vision model.

At Amazon's scale, this pattern is exactly what matters: thousands of
refund decisions an hour, each one needing to be consistent, explainable
to a regulator or an unhappy customer, and fast to update when policy
changes — without retraining a model or hoping an LLM interprets a
new rule the same way twice. Separating 'the policy' from 'the
conversation' is what makes that possible."

---

## SCENE 7 — Close (2:50–3:00)

**ON SCREEN:** GitHub repo URL on screen, or just fade to a simple end
card with the repo link.

**NARRATION:**
"That's the project — one agent, a strict policy engine underneath it,
and a fully auditable trail for every decision it makes. Repo link is
below."

---

## Notes on delivery

- Total spoken word count above is ~430 words, which at 150 wpm is
  about 2:50 — right in your target window. If it runs long, Scene 6
  is the safest one to trim.
- If recording live, do a full dry run with the backend already running
  (`uvicorn main:app --reload --port 8000`) and `logs/agent_trace.jsonl`
  cleared, so the demo looks fresh and the admin dashboard isn't
  cluttered with old test data.
- Keep your cursor movements slow and deliberate during Scenes 3-5 —
  fast clicking reads as rushed even with calm narration over it.
