# Adzymic AdCP Agentic Platform

A conversational AI platform built with Streamlit, MCP, and Groq LLM that lets users discover ad creative formats and generate live previews — powered by the Ad Context Protocol (AdCP).

---

## Workflow Structure

```
User (Streamlit UI)
      │
      ▼
  Groq LLM (llama-3.3-70b-versatile)
  - Receives user message + conversation history
  - Decides which tool to call based on natural language
      │
      ▼
  MCP Client (stdio transport)
  - Spawns `python -m ad_mcp` subprocess per call
  - Communicates over stdin/stdout using MCP protocol
      │
      ▼
  MCP Server (FastMCP)
  - list_creatives   → AdCP list_creative_formats
  - preview_creative → AdCP preview_creative
      │
      ▼
  AdCP Creative Agent (creative.adcontextprotocol.org)
```

**Tool registration**: MCP tools are fetched once at startup via `st.cache_resource` and registered dynamically with the Groq LLM as function-calling tools.

**Conversation flow**:
1. User logs in via email (persisted in `localStorage` — auto-login on return visits)
2. Last 3 conversation pairs (6 messages) are sent to the LLM as context
3. LLM calls the appropriate MCP tool if needed
4. Tool result is returned to LLM (preview HTML stripped — only success/failure sent back)
5. LLM generates a reply; preview HTML is rendered in the UI via `st.iframe`
6. Full conversation (including preview HTML) is persisted to `data/conversations.json` keyed by user email

---

## Design Rationale

### Context Handling
- **Email-based identity**: Users identify via email at login. Email is stored in browser `localStorage` so returning users are automatically logged in without re-entering their email. A logout button clears both the session and `localStorage`.
- **Sliding context window**: Only the last 3 conversation pairs are sent to the LLM per request to minimise token usage and avoid daily rate limits.
- **Preview HTML excluded from LLM context**: Preview HTML blobs (can be 10–50KB) are collected separately and never sent back to the LLM — only a short success message is returned as the tool result. This saves significant tokens per request.
- **Conversation persistence**: Full conversations including preview HTML are saved to `data/conversations.json` per user and reloaded on login.

### MCP Architecture
- **stdio transport**: each tool call spawns a fresh `python -m ad_mcp` subprocess, communicates over stdin/stdout using the MCP protocol, and exits cleanly. No ports, no persistent background threads, no state leakage between calls. Logs are directed to stderr to keep stdout clean for the MCP JSONRPC protocol.
- **Dynamic tool registration**: tools are fetched from the MCP server at startup and converted to Groq function-calling format automatically — adding a new `@AD_MCP.tool()` requires no changes to the Streamlit layer.

### Error Recovery
- **Tool errors never shown to users**: the LLM is instructed to translate any tool failure into a friendly message. Raw errors, JSON, and tool names are never exposed in the UI.
- **Timeouts**: `preview_creative` enforces a 30-second timeout via `anyio.fail_after` to prevent indefinite hangs on slow creative agent responses.
- **Network errors**: `ConnectError` from the creative agent is caught explicitly and surfaces a friendly retry message.
- **Pydantic validation**: creative manifests are validated against the adcp SDK's `PreviewCreativeSingleRequest` model before the API call, catching malformed inputs early.
- **Logging**: all MCP calls (tool name, args, elapsed time, success/failure) are logged to stderr with structured timestamps throughout every layer — MCP client, MCP server tools, Groq client, memory, and UI.

---

## Project Structure

```
ad-chat-bot/
├── streamlit_app.py        # Entry point for Streamlit Community Cloud
├── app.py                  # Main Streamlit UI (email gate, localStorage, chat, previews)
├── ad_mcp/
│   ├── server.py           # FastMCP server instance
│   ├── __main__.py         # MCP subprocess entry point (python -m ad_mcp)
│   └── tools/
│       ├── list_creatives.py    # list_creative_formats tool (with filter params)
│       └── preview_creative.py  # preview_creative tool (Pydantic-validated manifest)
├── core/
│   ├── groq_client.py      # Groq LLM tool-calling loop + system prompt
│   ├── mcp_client.py       # MCP stdio client (list_tools, call_tool)
│   ├── memory.py           # Conversation persistence (data/conversations.json)
│   └── log_config.py       # Centralised logging setup (stderr output)
├── data/
│   └── conversations.json  # Per-user conversation history (runtime-generated)
└── requirements.txt
```

---

## Setup

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Set your Groq API key in `app.py` or via `st.secrets["GROQ_API_KEY"]`.

---

## Test URL

*To be added after deployment to Streamlit Community Cloud.*
