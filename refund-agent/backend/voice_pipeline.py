"""
Voice pipeline integration point.

STATUS: MOCKED / SCAFFOLDED. This demonstrates the intended integration
shape for voice without requiring a live ElevenLabs/OpenAI Realtime key
for this submission.

Design principle (the same one used for evidence.py): voice is just a
different TRANSPORT into the exact same agent loop in agent.py. The
agent's reasoning, tool calls, and policy logic do not change based on
whether the input arrived as typed text or transcribed speech. This is
why voice integration doesn't touch agent.py at all -- it only needs to:
  1. Convert speech -> text  (transcribe_audio)
  2. Call run_agent_turn() exactly as the chat endpoint does
  3. Convert the text reply -> speech (synthesize_speech)

Real implementation path (not built here, to avoid needing a live key
for this submission):
  - STT: OpenAI Realtime API (WebSocket, streaming) or Whisper API
  - TTS: ElevenLabs API, or OpenAI's text-to-speech endpoint
  - Both would be called from a new /api/voice WebSocket route in main.py
    that pipes audio in, calls run_agent_turn(), and pipes audio back --
    main.py's existing session/log infrastructure needs no changes.
"""


def transcribe_audio(audio_bytes: bytes) -> str:
    """
    MOCKED. In production: stream audio_bytes to OpenAI Realtime API or
    Whisper and return the transcript. Here we just acknowledge receipt
    so the integration shape is visible without a live key.
    """
    return "[mocked transcription] I'd like to request a refund for my recent order."


def synthesize_speech(text: str) -> bytes:
    """
    MOCKED. In production: send `text` to ElevenLabs or OpenAI TTS and
    return audio bytes (e.g. mp3/pcm) to stream back to the caller.
    Here we return an empty placeholder.
    """
    return b""  # placeholder -- no audio bytes generated in mock mode


def handle_voice_turn(session_id: str, conversation_history: list, audio_bytes: bytes) -> dict:
    """
    The full voice round-trip: audio in -> agent loop -> audio out.
    Reuses run_agent_turn() unchanged -- this is the point of the design.
    """
    from agent import run_agent_turn

    transcript = transcribe_audio(audio_bytes)
    result = run_agent_turn(session_id, conversation_history, transcript)
    audio_reply = synthesize_speech(result["reply"])

    return {
        "transcript": transcript,
        "reply_text": result["reply"],
        "reply_audio": audio_reply,
        "history": result["history"],
    }
