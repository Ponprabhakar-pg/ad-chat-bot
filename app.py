from core.log_config import setup_logging
setup_logging()

import json
import logging
import streamlit as st
from core.mcp_client import list_tools, to_groq_tool
from core.groq_client import chat
from core.memory import load_messages, save_messages, clear_messages

logger = logging.getLogger(__name__)

st.set_page_config(page_title="Adzymic AI", page_icon="🎯", layout="centered")


def get_api_key() -> str:
    if "GROQ_API_KEY" in st.secrets:
        return st.secrets["GROQ_API_KEY"]
    import os
    return os.environ.get("GROQ_API_KEY", "")



@st.cache_resource
def get_groq_tools() -> list:
    return [to_groq_tool(t) for t in list_tools()]



def _inject_js(script: str) -> None:
    st.iframe(f"<html><body><script>{script}</script></body></html>", height=1)


def _js_save_email(email: str) -> None:
    _inject_js(f"""
        try {{
            localStorage.setItem('adzymic_email', {json.dumps(email)});
        }} catch(e) {{}}
    """)


def _js_clear_email() -> None:
    _inject_js("try { localStorage.removeItem('adzymic_email'); } catch(e) {}")


def _js_check_and_redirect() -> None:
    _inject_js("""
        try {
            const email = localStorage.getItem('adzymic_email');
            if (email) {
                const url = new URL(window.parent.location.href);
                if (!url.searchParams.get('email')) {
                    url.searchParams.set('email', email);
                    window.parent.location.href = url.toString();
                }
            }
        } catch(e) {}
    """)


if st.session_state.pop("_save_email_storage", None) is not None:
    email_to_persist = st.session_state.get("email", "")
    if email_to_persist:
        _js_save_email(email_to_persist)
        logger.info("[app] Saved email to localStorage — user=%s", email_to_persist)

if st.session_state.pop("_clear_email_storage", False):
    _js_clear_email()
    logger.info("[app] Cleared email from localStorage")



if "email" not in st.session_state:

    email_from_params = st.query_params.get("email", "").strip().lower()
    if email_from_params:
        st.session_state.email = email_from_params
        st.session_state.messages = load_messages(email_from_params)
        logger.info("[app] Auto-login from localStorage — user=%s", email_from_params)
        st.rerun()

    _js_check_and_redirect()

    st.title("Adzymic Ad Chat")
    st.markdown("Please enter your email to start chatting.")
    with st.form("email_form"):
        email_input = st.text_input("Email address", placeholder="you@example.com")
        if st.form_submit_button("Continue"):
            email_input = email_input.strip().lower()
            if "@" in email_input and "." in email_input:
                st.session_state.email = email_input
                st.session_state.messages = load_messages(email_input)
                # Set query param so URL reflects the session
                st.query_params["email"] = email_input
                # Flag to save to localStorage on next render (after rerun)
                st.session_state["_save_email_storage"] = True
                logger.info("[app] Email gate passed — user=%s", email_input)
                st.rerun()
            else:
                logger.warning("[app] Invalid email submitted: %r", email_input)
                st.error("Please enter a valid email address.")
    st.stop()



email: str = st.session_state.email

st.title("Adzymic Ad Chat")
st.caption(f"Signed in as **{email}**  ·  Ask about ad creative formats or request a preview.")

with st.sidebar:
    st.header("Session")
    st.write(f"**User:** {email}")

    if st.button("🗑️ Clear Memory", use_container_width=True):
        logger.info("[app] Clear Memory requested — user=%s", email)
        clear_messages(email)
        st.session_state.messages = []
        st.rerun()
    st.caption("Clears your saved conversation history.")

    st.divider()

    if st.button("🚪 Logout", use_container_width=True):
        logger.info("[app] Logout requested — user=%s", email)
        st.session_state.pop("email", None)
        st.session_state.pop("messages", None)
        st.query_params.clear()
        st.session_state["_clear_email_storage"] = True
        st.rerun()

if "messages" not in st.session_state:
    st.session_state.messages = load_messages(email)

groq_tools = get_groq_tools()


def render_preview(preview: dict) -> None:
    label = preview.get("format_id", "Ad Preview")
    w = int(preview["width"])
    h = int(preview["height"])
    st.caption(f"Preview · {label} · {w}×{h}px")
    st.iframe(preview["preview_html"], width=w, height=h)



for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        for preview in msg.get("previews", []):
            render_preview(preview)


if prompt := st.chat_input("Ask me about ad creatives..."):
    api_key = get_api_key()
    if not api_key:
        logger.error("[app] GROQ_API_KEY is not set — cannot proceed")
        st.error("GROQ_API_KEY is not set.")
        st.stop()

    logger.info("[app] User message received — user=%s prompt_len=%d", email, len(prompt))
    st.session_state.messages.append({"role": "user", "content": prompt, "previews": []})
    with st.chat_message("user"):
        st.markdown(prompt)

    context_window = st.session_state.messages[-10:]
    logger.info("[app] Sending context_window=%d messages to LLM", len(context_window))

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            reply, previews = chat(context_window, groq_tools, api_key)
        logger.info("[app] Assistant reply — reply_len=%d previews=%d", len(reply or ""), len(previews))
        st.markdown(reply)
        for preview in previews:
            logger.info("[app] Rendering preview — format=%s size=%dx%d",
                        preview.get("format_id"), preview.get("width"), preview.get("height"))
            render_preview(preview)

    st.session_state.messages.append({"role": "assistant", "content": reply, "previews": previews})
    save_messages(email, st.session_state.messages)
