"""Porsche 911 Valuation MCP Server.

Exposes 911 domain-knowledge tools over the Model Context Protocol (stdio).
The web app's Claude agent connects to this server as an MCP client, but it
works equally well plugged into Claude Desktop or any other MCP host:

    {
      "mcpServers": {
        "porsche-911-valuation": {
          "command": "python",
          "args": ["-m", "mcp_server.server"]
        }
      }
    }

Run standalone:  python -m mcp_server.server
"""

from datetime import date

from mcp.server.fastmcp import FastMCP

from mcp_server.data import (
    BASELINE_VALUES,
    GENERATIONS,
    VALUE_DRIVERS,
    driver_bucket,
    generation_for_year,
    normalize_trim,
)

mcp = FastMCP("porsche-911-valuation")


@mcp.tool()
def get_generation_info(model_year: int) -> dict:
    """Identify the 911 generation for a model year, with production years,
    generation notes, and known mechanical issues to inspect for."""
    gen = generation_for_year(model_year)
    if gen is None:
        return {
            "error": f"No 911 generation on file for model year {model_year}.",
            "supported_years": f"{GENERATIONS[0]['years'][0]}-{GENERATIONS[-1]['years'][1]}",
        }
    return {
        "generation": gen["code"],
        "production_years": f"{gen['years'][0]}-{gen['years'][1]}",
        "notes": gen["notes"],
        "known_issues": gen["known_issues"],
    }


@mcp.tool()
def get_trim_baseline(model_year: int, trim: str) -> dict:
    """Baseline good-condition private-sale value range (USD) for a 911
    generation + trim. These are illustrative anchors — always cross-check
    against live market comps before finalizing an estimate."""
    gen = generation_for_year(model_year)
    if gen is None:
        return {"error": f"No 911 generation on file for model year {model_year}."}
    trims = BASELINE_VALUES.get(gen["code"], {})
    key = normalize_trim(trim)
    if key not in trims:
        return {
            "error": f"No baseline for trim '{trim}' in generation {gen['code']}.",
            "available_trims": sorted(trims.keys()),
        }
    low, high = trims[key]
    return {
        "generation": gen["code"],
        "trim": key,
        "baseline_low_usd": low,
        "baseline_high_usd": high,
        "basis": "Good-condition private-sale, illustrative mid-2026 anchor. Validate with live comps.",
    }


@mcp.tool()
def adjust_for_mileage(base_value_usd: float, model_year: int, mileage: int) -> dict:
    """Adjust a baseline value for odometer mileage versus the 911 norm
    (~5,000 mi/year). Returns the adjusted value and the reasoning. GT and
    collectible cars are more mileage-sensitive; pass the Carrera-family
    default unless valuing a GT car."""
    age = max(date.today().year - model_year, 1)
    expected = age * 5000
    deviation = mileage - expected

    # ~1.5% value swing per 5k miles of deviation, capped at +/-25%
    pct = max(min((-deviation / 5000) * 0.015, 0.25), -0.25)
    adjusted = round(base_value_usd * (1 + pct))

    return {
        "expected_mileage_for_age": expected,
        "actual_mileage": mileage,
        "deviation_miles": deviation,
        "adjustment_pct": round(pct * 100, 1),
        "adjusted_value_usd": adjusted,
        "note": (
            "Heuristic: ±1.5% per 5,000 mi vs the ~5k mi/yr 911 norm, capped at ±25%. "
            "For GT/RS and air-cooled collectibles, mileage sensitivity is roughly double — "
            "weight comps more heavily than this heuristic."
        ),
    }


@mcp.tool()
def get_value_drivers(model_year: int) -> dict:
    """Options, specs, and history items that most move 911 values for the
    car's generation (e.g., manual gearbox, PTS paint, IMS retrofit, accident
    history). Use to score the owner's spec sheet and photo findings."""
    gen = generation_for_year(model_year)
    if gen is None:
        return {"error": f"No 911 generation on file for model year {model_year}."}
    bucket = driver_bucket(gen["code"])
    return {"generation": gen["code"], "value_drivers": VALUE_DRIVERS[bucket]}


@mcp.tool()
def list_supported_trims(model_year: int) -> dict:
    """List the trim families with baseline data for the generation matching
    a model year. Useful for validating/normalizing user-entered trims."""
    gen = generation_for_year(model_year)
    if gen is None:
        return {"error": f"No 911 generation on file for model year {model_year}."}
    return {"generation": gen["code"], "trims": sorted(BASELINE_VALUES.get(gen["code"], {}).keys())}


if __name__ == "__main__":
    mcp.run()  # stdio transport
