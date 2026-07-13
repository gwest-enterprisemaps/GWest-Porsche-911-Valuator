"""ValuationAgent — the Claude-powered core of the app.

Claude platform elements used here:
  1. Messages API           — anthropic SDK, multi-turn agentic loop
  2. Vision                 — user photos passed as in-memory base64 image blocks
  3. Tool use               — Claude decides when/which tools to call
  4. MCP                    — tools are served by our own MCP server (stdio);
                              this class is the MCP *client* that bridges them
                              into the Claude tool-use loop
  5. Server-side web search — Anthropic-hosted `web_search` tool for live comps
  6. Structured output      — final answer forced through a JSON-schema'd
                              `finalize_valuation` tool
  7. Prompt caching         — `cache_control` on the system prompt + tool defs
"""

import json
import os
import sys
from contextlib import AsyncExitStack

from anthropic import AsyncAnthropic
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")
MAX_AGENT_TURNS = 12

SYSTEM_PROMPT = """You are a Porsche 911 valuation specialist. Given a car's \
specs, mileage, history, and photos, produce a rigorous market valuation.

Method — follow in order:
1. Call get_generation_info and get_value_drivers to ground yourself in the \
generation's traits and known issues.
2. Call get_trim_baseline for the anchor range, then adjust_for_mileage.
3. If photos were provided, assess them carefully: condition of paint, wheels, \
seats/interior wear vs stated mileage, visible mods, damage, tire condition, \
and whether the car matches the stated trim (aero, badges, wheels, exhaust).
4. Use web_search to find 3-5 recent comparable sales or live listings \
(same generation/trim, similar miles). Prefer sold/auction results over asks.
5. Reconcile the baseline, mileage adjustment, photo findings, and live comps \
into a final range. Comps outrank baselines when they conflict.
6. Finish by calling finalize_valuation exactly once with the complete report. \
Do not present the report as plain text — always use the tool.

Be honest about uncertainty: widen the range and lower confidence when photos \
are missing, history is thin, or comps are scarce. Flag anything in photos \
that contradicts the stated spec."""

REPORT_TOOL = {
    "name": "finalize_valuation",
    "description": "Submit the final structured valuation report. Call exactly once, as the last step.",
    "input_schema": {
        "type": "object",
        "properties": {
            "estimated_value_low_usd": {"type": "integer"},
            "estimated_value_high_usd": {"type": "integer"},
            "point_estimate_usd": {"type": "integer"},
            "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
            "condition_grade": {
                "type": "string",
                "enum": ["concours", "excellent", "good", "fair", "poor", "unknown"],
                "description": "Based on photos + stated history; 'unknown' if no photos.",
            },
            "summary": {"type": "string", "description": "3-5 sentence narrative of the valuation."},
            "photo_findings": {
                "type": "array", "items": {"type": "string"},
                "description": "Observations from the photos, incl. any spec mismatches. Empty if no photos.",
            },
            "value_drivers": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "factor": {"type": "string"},
                        "direction": {"type": "string", "enum": ["up", "down"]},
                        "impact": {"type": "string", "enum": ["low", "medium", "high"]},
                    },
                    "required": ["factor", "direction", "impact"],
                },
            },
            "comparable_sales": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "description": {"type": "string"},
                        "price_usd": {"type": "integer"},
                        "source": {"type": "string"},
                    },
                    "required": ["description", "price_usd", "source"],
                },
            },
            "caveats": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "estimated_value_low_usd", "estimated_value_high_usd", "point_estimate_usd",
            "confidence", "condition_grade", "summary", "value_drivers",
            "comparable_sales", "caveats",
        ],
    },
}

WEB_SEARCH_TOOL = {"type": "web_search_20250305", "name": "web_search", "max_uses": 4}


class ValuationAgent:
    """Owns the Anthropic client and a persistent MCP client session.

    Stateless per request: no user data, images, or conversation history
    survive beyond a single valuate() call — everything lives in memory.
    """

    def __init__(self) -> None:
        self.client = AsyncAnthropic()
        self._stack = AsyncExitStack()
        self.mcp: ClientSession | None = None
        self.mcp_tools: list[dict] = []

    async def start(self) -> None:
        """Spawn the MCP server as a stdio subprocess and discover its tools."""
        params = StdioServerParameters(command=sys.executable, args=["-m", "mcp_server.server"])
        read, write = await self._stack.enter_async_context(stdio_client(params))
        self.mcp = await self._stack.enter_async_context(ClientSession(read, write))
        await self.mcp.initialize()
        listed = await self.mcp.list_tools()
        # Bridge MCP tool schemas into Anthropic tool definitions
        self.mcp_tools = [
            {"name": t.name, "description": t.description or "", "input_schema": t.inputSchema}
            for t in listed.tools
        ]

    async def stop(self) -> None:
        await self._stack.aclose()

    def _tools(self) -> list[dict]:
        tools = [WEB_SEARCH_TOOL, *self.mcp_tools, REPORT_TOOL]
        # Prompt caching: cache the (static) tool definitions
        tools[-1] = {**tools[-1], "cache_control": {"type": "ephemeral"}}
        return tools

    @staticmethod
    def _user_content(specs: dict, images: list[tuple[str, str]]) -> list[dict]:
        """Build the multimodal user turn: photos (base64, in memory) + specs."""
        content: list[dict] = [
            {
                "type": "image",
                "source": {"type": "base64", "media_type": media_type, "data": b64},
            }
            for media_type, b64 in images
        ]
        content.append({
            "type": "text",
            "text": (
                "Please value this Porsche 911.\n\n"
                f"Specs provided by owner:\n{json.dumps(specs, indent=2)}\n\n"
                f"Photos attached: {len(images)}"
            ),
        })
        return content

    async def valuate(self, specs: dict, images: list[tuple[str, str]]) -> dict:
        """Run the agentic loop. Returns the structured report dict."""
        if self.mcp is None:
            raise RuntimeError("Agent not started")

        messages = [{"role": "user", "content": self._user_content(specs, images)}]
        mcp_tool_names = {t["name"] for t in self.mcp_tools}
        trace: list[str] = []

        for _ in range(MAX_AGENT_TURNS):
            response = await self.client.messages.create(
                model=MODEL,
                max_tokens=4096,
                system=[{
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},  # prompt caching
                }],
                tools=self._tools(),
                messages=messages,
            )

            messages.append({"role": "assistant", "content": response.content})

            tool_results: list[dict] = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                if block.name == "finalize_valuation":
                    report = dict(block.input)
                    report["agent_trace"] = trace
                    report["model"] = MODEL
                    return report
                if block.name in mcp_tool_names:
                    trace.append(f"mcp:{block.name}")
                    result = await self.mcp.call_tool(block.name, dict(block.input))
                    payload = "\n".join(
                        c.text for c in result.content if getattr(c, "type", "") == "text"
                    )
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": payload or "(empty result)",
                        "is_error": bool(result.isError),
                    })
                elif block.name == "web_search":
                    # Server-side tool: executed by Anthropic within the request.
                    trace.append("web_search")

            if tool_results:
                messages.append({"role": "user", "content": tool_results})
                continue

            if response.stop_reason == "end_turn":
                # Model answered in prose instead of the report tool — nudge once.
                messages.append({
                    "role": "user",
                    "content": "Please submit the report by calling finalize_valuation now.",
                })

        raise RuntimeError("Agent exceeded maximum turns without finalizing a valuation")
