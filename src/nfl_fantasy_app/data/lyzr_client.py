"""Thin client for the deployed Lyzr draft-assistant agent (Week 2 RAG chatbot).

Calls the agent's REST endpoint from Lyzr's "Deploy" tab. Requires
lyzr_api_key, lyzr_agent_id, and lyzr_user_id in st.secrets -- see
.streamlit/secrets.toml.example. Get these from Lyzr Studio's Deploy tab
(Agent API panel), not from this app.
"""

import requests
import streamlit as st

API_URL = "https://agent-prod.studio.lyzr.ai/v3/inference/chat/"
# The agent has been observed taking 30+ seconds to respond (see the Lyzr
# build plan's own latency goal, which this exceeds) -- 30s was cutting it
# too close and causing spurious timeouts. Raised for headroom; the real
# fix is investigating why the agent itself is this slow (see below).
TIMEOUT_SECONDS = 60

# Lyzr's response field name wasn't confirmed against a live call yet -- try
# the common candidates in order and fall back to showing the raw payload,
# so a schema mismatch is visible in the chat instead of silently wrong.
RESPONSE_KEY_CANDIDATES = ("response", "message", "output", "text", "result")


def get_credentials() -> tuple[str, str, str] | None:
    try:
        return (
            st.secrets["lyzr_api_key"],
            st.secrets["lyzr_agent_id"],
            st.secrets["lyzr_user_id"],
        )
    except (KeyError, FileNotFoundError):
        return None


def ask_draft_assistant(message: str, session_id: str) -> str:
    """Send one chat turn to the Lyzr agent, return its reply text.

    Never raises -- returns a user-facing error string on failure, since
    this runs inline in the chat UI and a stack trace there is worse than
    a plain-language "unavailable" message.
    """
    credentials = get_credentials()
    if credentials is None:
        return (
            "Draft assistant isn't configured yet -- missing lyzr_api_key / "
            "lyzr_agent_id / lyzr_user_id in .streamlit/secrets.toml."
        )
    api_key, agent_id, user_id = credentials

    try:
        resp = requests.post(
            API_URL,
            headers={"Content-Type": "application/json", "x-api-key": api_key},
            json={
                "user_id": user_id,
                "agent_id": agent_id,
                "session_id": session_id,
                "message": message,
            },
            timeout=TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        return f"Draft assistant is unavailable right now ({e})."

    data = resp.json()
    for key in RESPONSE_KEY_CANDIDATES:
        value = data.get(key)
        if isinstance(value, str) and value:
            return value
    return f"(Unrecognized response shape from Lyzr -- raw payload: {data})"
