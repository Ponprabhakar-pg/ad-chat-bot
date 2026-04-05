import json
import logging
from groq import Groq
from core.mcp_client import call_tool

logger = logging.getLogger(__name__)

MODEL = "llama-3.3-70b-versatile"
_MAX_TOOL_RESULT_CHARS = 4000

SYSTEM_PROMPT = (
    "You are a friendly AI assistant for Adzymic, an ad creative platform. "
    "You help users discover ad creative formats and generate live previews of those formats. "

    # ── Workflow ──────────────────────────────────────────────────────────────
    "WORKFLOW: "
    "1. When the user asks about available formats, call list_creatives (with optional filters) "
    "and present the results clearly — show format_id, dimensions, and required asset types in a readable list. "
    "2. When the user wants a preview, you MUST use a valid format_id from list_creatives. "
    "If no format has been listed yet in this conversation, call list_creatives first, "
    "then immediately call preview_creative with a chosen format. "

    # ── Building the creative_manifest ────────────────────────────────────────
    "BUILDING PREVIEWS: "
    "preview_creative accepts a creative_manifest with two fields: "
    "(a) format_id: {\"id\": \"<format_id_string>\"} — use the exact id from list_creatives. "
    "(b) assets: a dict keyed by asset_id (shown in list_creatives results) mapped to asset objects. "
    "Asset object shapes by type: "
    "- text / generative: {\"content\": \"your text or prompt\"} "
    "- image: {\"url\": \"https://...\", \"width\": <int>, \"height\": <int>} "
    "- video: {\"url\": \"https://...\", \"width\": <int>, \"height\": <int>} "
    "- audio: {\"url\": \"https://...\"} "
    "- url (click/tracker): {\"url\": \"https://...\", \"url_type\": \"clickthrough\"} "
    "Example for a generative format: "
    "{\"format_id\": {\"id\": \"display_300x250_generative\"}, "
    "\"assets\": {\"generation_prompt\": {\"content\": \"A coffee brand ad\"}}}. "

    # ── Missing assets ────────────────────────────────────────────────────────
    "MISSING ASSETS: "
    "If preview_creative returns result='missing_asset', politely tell the user which asset "
    "is required (e.g. a hosted image URL, video URL, or click URL) and ask them to provide it. "
    "Do not say 'try again' — be specific about what is needed. "

    # ── Tool discipline ───────────────────────────────────────────────────────
    "TOOL DISCIPLINE: "
    "Only call tools ONCE per user message, responding only to what the user just asked. "
    "Never repeat tool calls for requests already handled in the conversation history. "

    # ── Error handling ────────────────────────────────────────────────────────
    "ERROR HANDLING: "
    "If a tool returns an error, never show raw errors, JSON, or technical details. "
    "Respond with a short, friendly message such as 'Sorry, I wasn't able to do that right now. Please try again.' "
    "Never mention tool names, function calls, JSON, or internal error messages in your response."
)

_FALLBACK = "Sorry, I'm having a technical issue right now. Please try again in a moment."


def _truncate(text: str) -> str:
    if len(text) <= _MAX_TOOL_RESULT_CHARS:
        return text
    trimmed = text[:_MAX_TOOL_RESULT_CHARS]
    logger.debug("[groq_client] Tool result truncated from %d to %d chars", len(text), _MAX_TOOL_RESULT_CHARS)
    return trimmed + f"\n... [truncated, {len(text)} chars total]"


def chat(messages: list, groq_tools: list, api_key: str) -> tuple[str, list[dict]]:
    logger.info("[groq_client] chat() called — history_len=%d tools=%d",
                len(messages), len(groq_tools))
    try:
        reply, previews = _chat(messages, groq_tools, api_key)
        logger.info("[groq_client] chat() done — reply_len=%d previews=%d",
                    len(reply or ""), len(previews))
        return reply, previews
    except Exception as e:
        logger.exception("[groq_client] Unhandled exception in _chat(): %s", e)
        return _FALLBACK, []


def _chat(messages: list, groq_tools: list, api_key: str) -> tuple[str, list[dict]]:
    client = Groq(api_key=api_key)
    api_messages = [{"role": m["role"], "content": m["content"]} for m in messages]
    full_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + api_messages
    previews: list[dict] = []
    iteration = 0

    while True:
        iteration += 1
        logger.info("[groq_client] LLM request #%d — model=%s messages=%d",
                    iteration, MODEL, len(full_messages))

        response = client.chat.completions.create(
            model=MODEL,
            messages=full_messages,
            tools=groq_tools,
            tool_choice="auto",
        )
        message = response.choices[0].message
        usage = response.usage
        logger.info("[groq_client] LLM response #%d — finish_reason=%s "
                    "prompt_tokens=%s completion_tokens=%s total_tokens=%s",
                    iteration,
                    response.choices[0].finish_reason,
                    usage.prompt_tokens if usage else "?",
                    usage.completion_tokens if usage else "?",
                    usage.total_tokens if usage else "?")

        if not message.tool_calls:
            logger.info("[groq_client] No tool calls — returning final reply")
            return message.content, previews

        logger.info("[groq_client] %d tool call(s) requested", len(message.tool_calls))
        full_messages.append(message)

        for tool_call in message.tool_calls:
            name = tool_call.function.name
            args = json.loads(tool_call.function.arguments or "{}")
            logger.info("[groq_client] → dispatching tool=%s args=%s", name, args)

            raw_result = call_tool(name, args)

            try:
                parsed = json.loads(raw_result)
                status = parsed.get("result", "unknown")
                if status == "success":
                    logger.info("[groq_client] ← tool=%s SUCCESS", name)
                else:
                    logger.warning("[groq_client] ← tool=%s result=%s error=%s",
                                   name, status, parsed.get("error", ""))
            except json.JSONDecodeError:
                logger.warning("[groq_client] ← tool=%s returned non-JSON result", name)
                parsed = {}

            if name == "preview_creative" and parsed.get("result") == "success" and parsed.get("preview_html"):
                previews.append({
                    "preview_html": parsed["preview_html"],
                    "width": parsed.get("width", 300),
                    "height": parsed.get("height", 250),
                    "format_id": parsed.get("format_id", ""),
                })
                logger.info("[groq_client] Preview collected — format=%s size=%dx%d",
                            parsed.get("format_id"), parsed.get("width"), parsed.get("height"))

            if name == "preview_creative" and parsed.get("result") == "success":
                tool_content = json.dumps({
                    "result": "success",
                    "format_id": parsed.get("format_id", ""),
                    "width": parsed.get("width"),
                    "height": parsed.get("height"),
                    "message": "Preview HTML generated and is being displayed to the user.",
                })
            else:
                tool_content = _truncate(raw_result)

            full_messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": tool_content,
            })
