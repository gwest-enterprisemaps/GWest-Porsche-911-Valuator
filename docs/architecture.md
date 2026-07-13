# Architecture notes

## Design goals

1. **Showcase MCP properly.** Most demos are either an MCP server *or* an MCP client. This repo is both: `mcp_server/` is a real FastMCP server that also works standalone in Claude Desktop, and `app/agent.py` is a real MCP client (`mcp.ClientSession` over stdio) that discovers the server's tools at startup and bridges them into Claude's tool-use loop. Nothing is hard-coded — add a tool to the server and the agent picks it up automatically.

2. **Stateless.** No database, no file storage, no sessions. Photos arrive as multipart form data, are base64-encoded in memory, sent to Claude as vision blocks, and garbage-collected when the request ends. This makes local dev, containerization, and horizontal scaling trivial.

3. **Claude does the reasoning; tools supply the facts.** The MCP tools return domain knowledge (generation traits, baseline ranges, mileage heuristics, value drivers). Server-side web search supplies live comps. Claude reconciles everything and its answer is captured through a schema-enforced tool call, so the frontend never parses free text.

## The agentic loop (app/agent.py)

```
user photos + specs
        │
        ▼
┌──────────────────────────────────────────────┐
│  messages.create(model, system*, tools*, …)  │  * = prompt-cached
└──────────────────────────────────────────────┘
        │
        ├── tool_use: get_generation_info / get_trim_baseline / …
        │        → forwarded to MCP server via session.call_tool()
        │        → result appended as tool_result, loop continues
        │
        ├── server_tool_use: web_search
        │        → executed by Anthropic inside the request; nothing to do
        │
        └── tool_use: finalize_valuation
                 → schema-validated JSON report; loop exits
```

A hard cap (`MAX_AGENT_TURNS = 12`) bounds cost, and a one-time nudge handles the rare case where the model answers in prose instead of calling the report tool.

## Why stdio MCP (vs. HTTP/SSE)?

The MCP server ships in the same repo and runs on the same host, so stdio is the simplest, most portable transport: the FastAPI lifespan hook spawns it as a subprocess and keeps one session for the process lifetime. Swapping to a remote MCP server later only changes the transport setup in `ValuationAgent.start()` — the loop is transport-agnostic.

## Security & privacy

- Upload validation: content-type allowlist, 5 photo / 5 MB caps, form field range checks.
- No persistence of user data anywhere.
- The API key stays server-side; the browser never talks to Anthropic directly.
- All user HTML rendering goes through `escapeHtml()` in the frontend.

## Extension ideas

- Streaming the agent's progress to the UI (SSE) so users see "checking comps…" live.
- A `get_option_codes` MCP tool that decodes Porsche option codes from a build sheet photo.
- Batch mode: value a whole collection from a CSV.
- Citations: surface the web-search result URLs used for comps in the report.
