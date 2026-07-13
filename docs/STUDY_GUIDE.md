# Building an AI Valuation App with Claude and MCP
## A Study Guide & Hands-On Workshop

**Repository:** https://github.com/gwest-enterprisemaps/GWest-Porsche-911-Valuator
**Level:** University / early-career engineer
**Time budget:** 8–12 hours across six modules
**Prerequisites:** Working Python (functions, async basics, decorators), basic HTTP/JSON, comfort with a terminal, a GitHub account

---

## Why this project exists

Most "AI app" tutorials teach you to send a string to a model and print the reply. That skips everything that makes production AI engineering interesting: giving the model *tools*, grounding it in *domain data*, handling *multimodal* input, forcing *structured* output a UI can trust, and deploying the result somewhere real people can use it.

This project — a Porsche 911 market valuator — was chosen because vehicle valuation naturally exercises all of those at once. A good valuation needs structured facts (year, trim, mileage), unstructured evidence (photos), curated domain knowledge (what an IMS bearing failure is and which generations it haunts), and *live* market data (what comparable cars actually sold for this month). No single technique covers all four. The architecture you are about to study is the answer to that problem.

By the end you will be able to explain — not just execute — every layer: the Model Context Protocol (MCP), the Claude agentic loop, vision input, server-side web search, structured output, stateless API design, and one-click cloud deployment on Render.

### Learning objectives

After completing this guide you should be able to:

1. Describe the MCP client/server architecture and implement both sides in Python.
2. Build a multi-turn tool-use ("agentic") loop against the Claude Messages API.
3. Pass images to Claude as in-memory base64 blocks and reason about what vision adds.
4. Force schema-valid JSON out of a language model using a tool definition, and explain why this beats parsing prose.
5. Justify stateless service design and identify what it buys you at deploy time.
6. Deploy a Dockerized FastAPI service to Render and operate it on a public onrender.com URL.
7. Diagnose the most common GitHub token-authentication failures.

---

# Module 1 — Architecture: reading the map before driving

### Background

The system has three zones. The **browser** runs a deliberately plain single-page UI (vanilla JS, no build step). The **FastAPI app** is the brain-stem: it validates input, holds photos in memory, and runs the `ValuationAgent`. The **Anthropic API** hosts Claude itself plus the server-side `web_search` tool. A fourth piece — the **MCP server** — runs as a child process of the FastAPI app and supplies Porsche domain knowledge.

```
Browser ──multipart──▶ FastAPI ──messages+tools──▶ Claude (Anthropic API)
                          │  ▲                        │      ▲
                          │  └──── tool_use ◀─────────┘      │
                          ▼                                  ▼
                    MCP server (stdio)                  web_search
                    5 domain tools                      (server-side)
```

### Why it is stateless

The app stores nothing: no database, no session store, no files on disk. Photos arrive as multipart form data, are base64-encoded in RAM, sent to Claude, and garbage-collected when the request completes.

This is a *decision*, not an accident, and it pays out three times. First, privacy: user photos never persist anywhere, which is the strongest possible answer to "what do you do with my data?" Second, operational simplicity: there is nothing to back up, migrate, or leak. Third, deployability: a stateless container can be killed, restarted, or horizontally replicated with zero coordination — which is exactly what free-tier cloud hosts do to your process, as you will see in Module 6.

The cost of statelessness is that nothing is remembered between requests — no valuation history, no user accounts. Engineering is trade-offs; know what you paid.

### Why the reasoning is split three ways

A core design idea worth internalizing: **Claude does the reasoning; tools supply the facts.**

- Curated, slow-changing knowledge (generation traits, known mechanical issues, baseline price anchors) lives in the **MCP server** — versioned in git, reviewable, testable.
- Fresh, volatile knowledge (what a 997.2 Carrera S sold for last week) comes from **web search** at request time.
- Judgment (does the interior wear match 42,000 miles? do the comps outweigh the baseline?) is **Claude's** job.

If you put the baselines in the prompt, they'd be unreviewable blobs of text. If you asked Claude to "remember" market prices, they'd be stale and hallucination-prone. If you tried to code the judgment, you'd be writing rules forever. Each kind of knowledge lives where it is cheapest to maintain and most reliable to use.

### Activity 1

1. Clone the repo and read `README.md` end to end, including the Mermaid diagram.
2. Without looking at code, sketch the request flow for "user submits a 2011 Carrera S with 3 photos" — every network hop, every process boundary.
3. Answer in writing: *what specifically would break if the app wrote uploaded photos to `/tmp` and processed them from disk?* (Hint: think about multiple replicas, and think about what "the same machine" means on a cloud host.)

**Checkpoint:** you can name all four runtime components and state one reason each exists.

---

# Module 2 — The MCP server: packaging domain knowledge as tools

**Files:** `mcp_server/server.py`, `mcp_server/data.py`

### Background: what MCP is and why it matters

The Model Context Protocol is an open standard for connecting AI applications to tools and data. Think of it as USB for AI capabilities: a tool server written once can be plugged into Claude Desktop, Claude Code, this web app, or any other MCP-aware host, without modification. Before MCP, every AI app invented its own plugin format; tool code was welded to one application. MCP separates *what a tool does* from *who is calling it*.

An MCP **server** exposes tools (and optionally resources and prompts) over a transport. An MCP **client** connects to a server, discovers its tools at runtime via `list_tools`, and invokes them via `call_tool`. Discovery is the point: the client hard-codes nothing.

### What our server exposes

`mcp_server/server.py` uses **FastMCP**, which turns plain Python functions into protocol-compliant tools. The `@mcp.tool()` decorator reads each function's *type hints* to generate the JSON schema and its *docstring* to produce the description Claude sees. This means your docstrings are now model-facing prompts — write them accordingly.

Five tools, each with a distinct pedagogical purpose:

| Tool | Kind of knowledge | Why a tool and not prompt text |
|---|---|---|
| `get_generation_info` | Lookup (964 → 992.2, known issues) | Reviewable data beats prose in a prompt |
| `get_trim_baseline` | Anchor value ranges | The model needs a numeric starting point it didn't hallucinate |
| `adjust_for_mileage` | Deterministic arithmetic | LLMs are unreliable at arithmetic; Python is not |
| `get_value_drivers` | Heuristics (manual gearbox ↑, accident ↓) | Encodes expert judgment as data |
| `list_supported_trims` | Introspection | Lets the model recover from unrecognized user input |

`adjust_for_mileage` deserves emphasis. It computes a value adjustment of ±1.5% per 5,000 miles of deviation from the ~5,000 mi/year 911 norm, capped at ±25%. You *never* want a language model doing this arithmetic token-by-token — you want it deciding *whether and how* to use the result. Delegating computation to code and judgment to the model is a pattern you will reuse in every AI system you build.

Note also what the server does **not** do: it never touches the internet. All of its data is static, in `data.py`, marked explicitly as illustrative. Live market truth comes from web search (Module 3), and the system prompt tells Claude that comps outrank baselines. Understand this division before proceeding.

### Transport: why stdio

MCP supports multiple transports. This server uses **stdio**: the host spawns it as a child process and speaks JSON-RPC over stdin/stdout. For a server that ships in the same repo and runs on the same machine, stdio is the simplest thing that works — no ports, no auth, no network config. If the server later moved to another machine, you would switch to the HTTP transport and change only the connection setup in the client; the tools themselves are transport-agnostic.

### Activity 2

1. Run the server standalone and poke it: `python -m mcp_server.server` (it will wait silently for JSON-RPC on stdin — that silence *is* the stdio transport).
2. Register it in Claude Desktop (config snippet is in the README) and ask Claude Desktop: *"What are the known issues on a 2005 911?"* Watch it call your tool.
3. Write and register a sixth tool, `estimate_annual_maintenance(model_year: int, trim: str) -> dict`, returning a rough annual cost range with a one-line basis. Restart the web app and confirm — without editing `agent.py` — that the agent discovered it. Explain *why* no agent change was needed.

**Checkpoint:** you can explain `list_tools`/`call_tool`, why docstrings matter, and what stdio transport means, without notes.

---

# Module 3 — The agent: Claude, tools, vision, and the loop

**File:** `app/agent.py` — read it top to bottom before continuing.

### Background: what "agentic" actually means

An agentic loop is disarmingly simple: call the model; if it asks to use a tool, run the tool and append the result to the conversation; repeat until it produces a final answer. The intelligence is in the model's *choices* — which tool, with what arguments, in what order — not in the loop.

Every Claude platform element in this file exists to solve a specific problem:

**1. Messages API.** The `anthropic` SDK's `AsyncAnthropic` client. Async matters because FastAPI is an async framework: while Claude is thinking (seconds), the event loop can serve other requests.

**2. Vision.** Photos are passed as base64 `image` content blocks in the user message. Claude grades paint, wheel, and seat condition; checks whether interior wear plausibly matches the odometer; spots modifications and damage; and verifies the car matches the claimed trim (a GT3's aero is hard to fake). None of this is possible from form fields alone — vision converts "trust the seller" into "verify the evidence."

**3. Tool use.** The request advertises three kinds of tools in one list: the five MCP-bridged tools, Anthropic's server-side `web_search`, and the local `finalize_valuation`. Claude neither knows nor cares which is which — a critical insight. The *agent* is the router: MCP names go to `session.call_tool()`, web search is handled inside Anthropic's infrastructure, and `finalize_valuation` terminates the loop.

**4. Server-side web search.** `{"type": "web_search_20250305", "name": "web_search", "max_uses": 4}`. Anthropic executes the search *within* the API call — your code never fetches a URL, parses HTML, or manages a search API key. `max_uses: 4` is a cost bound. This is how the app gets July-2026 market prices from a model with a fixed training cutoff.

**5. Structured output via a tool schema.** The single most transferable trick in the codebase. Instead of asking Claude to "reply in JSON" (and praying), we define `finalize_valuation` whose `input_schema` *is* the report format — value range, point estimate, confidence enum, condition-grade enum, value drivers, comps, caveats. Claude "calls" the tool; the arguments arrive schema-shaped; the frontend renders them directly. The prompt orders Claude to always finish this way, and the loop includes a one-shot nudge if it answers in prose instead. Contrast this with regex-parsing a chat reply and you will never go back.

**6. Prompt caching.** `cache_control: {"type": "ephemeral"}` on the system prompt and tool definitions. The loop makes several API calls per valuation, each resending the same ~2,000 tokens of preamble; caching makes the repeats dramatically cheaper and faster. Rule of thumb: cache anything long and identical across calls.

**7. The system prompt as methodology.** Reread the six-step method in `SYSTEM_PROMPT`. It is a *checklist*, not a personality: ground yourself (MCP) → anchor and adjust (MCP) → inspect photos (vision) → find comps (web search) → reconcile with an explicit conflict rule ("comps outrank baselines") → finalize (structured output). Each step maps one-to-one to a capability from Modules 2–3. When output quality disappoints, fix the checklist before reaching for a bigger model.

Also note the two safety rails: `MAX_AGENT_TURNS = 12` bounds cost if the model loops, and honest-uncertainty instructions ("widen the range and lower confidence when photos are missing") shape behavior in degraded cases.

### Activity 3

1. Trace `valuate()` line by line. Annotate each branch of the tool-dispatch code with which of the three tool kinds it handles.
2. Set `ANTHROPIC_API_KEY`, run the app locally, and submit a car you know *without* photos. Then resubmit *with* photos. Diff the two reports: what did vision change? Check `confidence` in both.
3. Experiment: remove step 4 (web search) from the system prompt and revalue the same car. How did the range and the `comparable_sales` array change? Restore the prompt.
4. Written question: why does `finalize_valuation` use enums (`"low" | "medium" | "high"`) for confidence instead of a free-text string? What downstream code does that protect?

**Checkpoint:** you can whiteboard the loop from memory, including all three tool routes and both exit conditions.

---

# Module 4 — The FastAPI backend: the unglamorous parts that matter

**File:** `app/main.py`

### Background

This layer looks boring next to the agent — that is precisely its virtue. Its job is to be predictable: validate everything, hold nothing, fail loudly.

**Lifespan management.** The `lifespan` context manager runs at startup: it fails fast if `ANTHROPIC_API_KEY` is missing (a deploy-time error should never look like a runtime mystery), then starts the agent, which spawns the MCP subprocess and performs tool discovery *once*. One MCP session serves the process's lifetime — per-request user data stays stateless, but the expensive plumbing is reused.

**Input validation.** Year bounded 1964–2027, mileage 0–500,000, at most 5 photos of 5 MB each, content-type allowlist (`jpeg/png/webp/gif`). Every rejection is a specific HTTP 422 with a human-readable message. Validation is cheapest at the boundary; everything behind it can then assume sane input.

**Rate limiting.** Each valuation costs real money (Claude tokens + web searches), so `/api/valuate` is limited per client IP via `slowapi` — default `5/minute;30/day`, configurable through the `RATE_LIMIT` env var. Two details are worth study: (a) the key function reads `X-Forwarded-For` because on Render your app sits behind a proxy and `request.client.host` would otherwise rate-limit *the proxy*, punishing all users collectively; (b) the limiter is in-memory, deliberately matching the stateless design — if you ever run multiple replicas, each replica counts separately, and the fix is pointing slowapi at Redis. Know your limits' limits.

**Error hygiene.** The agent call is wrapped so failures log the full traceback server-side but return only a generic 502 to the browser. Internals (prompts, stack traces, key names) never leak to clients.

### Activity 4

1. Start the app and hit `GET /api/health`. Explain each field it returns and why a deployment platform wants this endpoint (see Module 6's `healthCheckPath`).
2. Use `curl` to earn every distinct error: a 422 for year 3000, a 422 for a 6 MB photo, a 429 by exceeding the rate limit (`RATE_LIMIT=3/minute` makes this fast). Note the response shape differences — FastAPI's `detail` vs slowapi's `error`.
3. Written question: the frontend checks both `err.detail` and `err.error`. Find where, and explain how you would have discovered this mismatch if the study guide hadn't told you.

**Checkpoint:** you can list the four defensive layers (fail-fast startup, validation, rate limiting, error hygiene) and give the reason for each.

---

# Module 5 — The frontend: why vanilla JS was the right call

**Files:** `static/index.html`, `static/app.js`, `static/style.css`

### Background

No React, no bundler, no npm. For a portfolio project this is a feature: any reviewer can read three files top to bottom, and there is no build pipeline to rot. The lesson is judgment — frameworks earn their complexity on large apps; a one-form, one-report page is not one.

Three things to study:

1. **In-memory photo handling.** Selected files live in a JS array; thumbnails use `URL.createObjectURL` (revoked after load — a small idiomatic detail that prevents memory leaks). On submit, files go into `FormData` as `photos` entries. The statelessness story starts in the browser.
2. **Rendering a *schema*, not prose.** `renderReport()` consumes exactly the `finalize_valuation` schema from Module 3: the range and point estimate, confidence/condition badges, direction-arrowed value drivers, a comps table, caveats. Frontend and model are coupled through one contract. Change the schema, and you know precisely what UI to update.
3. **XSS discipline.** Every model- or user-originated string passes through `escapeHtml()` before touching `innerHTML`. LLM output is *untrusted input* — a comp description scraped from the web could contain markup. Treat model text with the same suspicion as user text.

### Activity 5

1. Add a "Copy report as JSON" button that puts the raw report object on the clipboard. (Touches: one button, one handler, ~10 lines.)
2. The 5 MB photo limit annoys real users. Implement client-side downscaling: draw each image to a `<canvas>` capped at 1600px on the long edge, export as JPEG quality 0.85, and upload the result instead. (~15 lines; this also cuts Claude vision token costs — explain why.)
3. Written question: find two places `escapeHtml()` is applied to *model* output. Construct a hypothetical malicious string that would execute without it.

**Checkpoint:** you can explain the schema-to-UI contract and demonstrate one working frontend modification.

---

# Module 6 — Shipping: GitHub, Docker, and Render

**Files:** `Dockerfile`, `render.yaml`, `.env.example`, `.gitignore`

### Background: the deployment chain

The path to production is: git repo → GitHub → Render builds the Dockerfile → public HTTPS URL on **onrender.com**. Because the app is stateless, this chain needs no database provisioning, no volumes, no migrations — the entire production footprint is one container and one secret.

**The Dockerfile** is intentionally minimal: `python:3.12-slim` base, install requirements, copy `app/`, `mcp_server/`, `static/`, run uvicorn on port 8000. No multi-stage builds or optimizations that would obscure the teaching value. The MCP server needs no separate container — it is a child process, so it ships inside the same image.

**`render.yaml`** is Infrastructure-as-Code: it declares a Docker web service on the free plan, sets `healthCheckPath: /api/health` (Render probes this to decide the deploy succeeded — Module 4's endpoint suddenly matters), pins `RATE_LIMIT`, and declares `ANTHROPIC_API_KEY` with `sync: false`, which means *prompt the human at deploy time and never store the value in the repo*. The "Deploy to Render" button in the README reads this file.

**Secrets discipline.** `.env` is gitignored; `.env.example` documents the shape without the values; the API key exists only in Render's environment. At no point does a secret enter git history. Check `git log -p -- .env.example` and confirm.

### Deploying — and living with — onrender.com

Deploy steps (about five minutes of human time):

1. Open the repo → click **Deploy to Render**.
2. Sign in to Render (GitHub SSO is fine; free tier requires no card).
3. When prompted, paste an **Anthropic API key** — obtained from **console.anthropic.com** → API Keys. Important context: the Console is a *separate product* from a claude.ai/Claude Desktop subscription. API usage bills per token from Console credits ($5–10 covers extensive testing; a valuation costs a few cents, dominated by image tokens and web search).
4. Deploy. First Docker build takes ~3–5 minutes. Your app appears at `https://porsche-911-valuator-XXXX.onrender.com`.

Operational realities of the free tier — learn them before they surprise you:

- **Cold starts.** Idle services are spun down; the next request waits ~30 seconds while the container boots (watch `/api/health` recover). This is statelessness in action: Render can kill your process at will *because* nothing is lost when it does.
- **Auto-deploy.** Every push to `main` triggers a rebuild and rolling deploy. Your git history is now your release history — commit messages are release notes.
- **Logs.** The Render dashboard streams stdout; the app's `logging` calls (and the MCP tool list logged at startup) are your production debugging surface.

### Case study: the GitHub token saga (read this — it will happen to you)

Deploying this very repo produced a textbook authentication troubleshooting sequence, preserved here as a case study:

1. A fine-grained PAT authenticated but got **403 on push**. Diagnosis: fine-grained tokens default to *Public repositories (read-only)* — reads succeed, writes fail, and the error message doesn't say why.
2. A second fine-grained token failed identically — the permission edit hadn't actually granted *Contents: Read and write* on the target repo.
3. A classic token *also* 403'd — generated without the `repo` scope checked. Key insight: a classic token with **zero scopes still authenticates**; it just can't do anything. The `401 vs 403` distinction was the diagnostic: 401 = "who are you?", 403 = "I know who you are; no."
4. A classic token *with* `repo` scope pushed successfully.

The debugging method matters more than the answer: probe read and write paths independently (`info/refs?service=git-upload-pack` vs `git-receive-pack`), test a deliberately bogus credential to calibrate what failure looks like, and change one variable at a time. Also: any token pasted into a chat, ticket, or log is *burned* — revoke it once its job is done, use short expirations, and scrub tokens from `git remote -v` after use.

### Activity 6

1. Fork the repo to your own GitHub account and deploy your fork to Render end to end. Record your onrender.com URL.
2. Time a cold start: let the service idle 20+ minutes, then curl `/api/health` with `time`. Report the number.
3. Push a trivial change (edit the page title) and watch the auto-deploy pipeline run.
4. Written exercise: your token pushes fine to repo A but 403s on repo B. Using the case study, list the three most likely causes in the order you would test them.

**Checkpoint:** a working public URL you deployed yourself, plus a one-paragraph postmortem of anything that went wrong.

---

# Capstone — make it yours

Complete at least one; each extends a different module:

1. **Live-data MCP tool** (Module 2): add a tool that fetches real listing data from a pricing API, making the MCP server do its own network I/O. Discuss how this changes the "comps outrank baselines" rule.
2. **Streaming progress** (Modules 3–5): stream agent progress to the browser via Server-Sent Events so users see "checking comps…" live instead of a spinner.
3. **Cited comps** (Module 3): surface the web-search source URLs in `comparable_sales` and render them as links, with `rel="noopener"` and your Module 5 XSS discipline intact.
4. **A different domain** (everything): rebuild the pattern for another valuation domain — watches, guitars, real estate comps. Keep the architecture; replace `data.py`, the system prompt, and the report schema. If the swap is clean, you truly understood the separation of concerns.

---

# Appendix A — Glossary

- **MCP (Model Context Protocol):** open standard for connecting AI hosts to tool/data servers; client discovers tools at runtime.
- **FastMCP:** Python helper that turns typed, docstringed functions into MCP tools.
- **stdio transport:** MCP over a child process's stdin/stdout; simplest same-machine transport.
- **Agentic loop:** call model → execute requested tools → feed results back → repeat until a final answer.
- **Server-side tool:** a tool (e.g., `web_search`) executed inside Anthropic's infrastructure during the API call.
- **Structured output via tool schema:** defining a "final answer" tool whose input schema is your desired output format.
- **Prompt caching:** `cache_control` markers that let repeated prompt prefixes be served cheaply from cache.
- **Stateless service:** no data survives a request; enables free scaling/restarts at the cost of no memory.
- **PAT (Personal Access Token):** GitHub credential; *fine-grained* (per-repo, per-permission) vs *classic* (scope checkboxes).
- **Cold start:** delay while an idled free-tier container boots to serve the first request.

# Appendix B — Cost model (order of magnitude)

Per valuation: 1 request with up to 5 images (image tokens dominate input), 3–6 loop turns (prompt caching blunts the repeats), up to 4 web searches. Expect a few cents per valuation on Sonnet-class models. Controls in place: `MAX_AGENT_TURNS`, `max_uses` on search, per-IP rate limits, photo count/size caps — find each in the code and connect it to a line in this cost model.

# Appendix C — Security checklist

- Secrets: only in `.env` (local) or Render env vars (prod); never in git; revoke anything ever pasted into a chat or ticket.
- Input: validate type, size, count, and ranges at the API boundary.
- Output: escape all model/user text before DOM insertion.
- Spend: rate-limit any endpoint that costs money per call.
- Errors: log details server-side; return generic messages to clients.
