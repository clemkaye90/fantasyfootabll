"""Draft assistant tab: chat UI wired to the deployed Lyzr RAG agent."""

import uuid

import streamlit as st

from nfl_fantasy_app.data.lyzr_client import ask_draft_assistant, get_credentials

SESSION_KEY = "draft_assistant_session_id"
MESSAGES_KEY = "draft_assistant_messages"


def render_draft_assistant_tab() -> None:
    st.caption(
        "Ask about player rankings, injuries, news, or draft strategy -- answers are "
        "grounded in the corpus uploaded to the Lyzr knowledge base, not general knowledge."
    )

    if get_credentials() is None:
        st.info(
            "Not configured yet. Add `lyzr_api_key`, `lyzr_agent_id`, and `lyzr_user_id` "
            "to `.streamlit/secrets.toml` (see secrets.toml.example) to enable this tab."
        )
        return

    if SESSION_KEY not in st.session_state:
        st.session_state[SESSION_KEY] = f"streamlit-{uuid.uuid4().hex[:12]}"
    if MESSAGES_KEY not in st.session_state:
        st.session_state[MESSAGES_KEY] = []

    for role, text in st.session_state[MESSAGES_KEY]:
        with st.chat_message(role):
            st.markdown(text)

    prompt = st.chat_input("e.g. Should I draft Lamar Jackson before Kyler Murray?")
    if prompt:
        st.session_state[MESSAGES_KEY].append(("user", prompt))
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                reply = ask_draft_assistant(prompt, st.session_state[SESSION_KEY])
            st.markdown(reply)
        st.session_state[MESSAGES_KEY].append(("assistant", reply))
