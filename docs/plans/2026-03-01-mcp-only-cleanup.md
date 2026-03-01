# MCP-Only Cleanup Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Strip soviet_dashboard down to a pure MCP server — no web UI, no file watcher, no FastAPI, reads fresh from disk on every tool call.

**Architecture:** Each MCP tool call invokes `parse_stats_file(STATS_PATH)` directly. No shared GameState singleton, no background watcher thread. `mcp_server.py` and `parser.py` are the only meaningful modules; `main.py` is a minimal entry point.

**Tech Stack:** Python 3.13, mcp[cli]==1.3.0

---

### Task 1: Overhaul mcp_server.py — read fresh from disk

**Files:**
- Modify: `soviet_dashboard/mcp_server.py`

**Step 1: Replace the file contents**

Replace `mcp_server.py` with the following (removes `game_state`/`state` imports, adds `_load()` helper that calls `parse_stats_file` on each tool call, moves `STATS_PATH` here):

```python
"""MCP server exposing Soviet Republic game data as tools.

Run via: python main.py
"""
import asyncio
import json
import logging
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from parser import parse_stats_file

logger = logging.getLogger(__name__)

STATS_PATH = Path(__file__).parent.parent / "media_soviet" / "save" / "autosave1" / "stats.ini"
SAVES_DIR = STATS_PATH.parent.parent  # media_soviet/save/


def _load() -> list:
    """Load current autosave records fresh from disk."""
    if not STATS_PATH.exists():
        return []
    return parse_stats_file(STATS_PATH)


# ---------------------------------------------------------------------------
# Pure tool functions — each reads fresh from disk
# ---------------------------------------------------------------------------

def tool_get_stats() -> dict:
    records = _load()
    if not records:
        return {"error": "No data loaded"}
    rec = records[-1]
    return {
        "year": rec.year,
        "day": rec.day,
        "total_population": rec.total_population,
        "population": rec.citizens,
        "citizen_status": rec.citizen_status,
        "economy_rub": rec.economy_rub,
        "economy_usd": rec.economy_usd,
    }


def tool_get_population() -> dict:
    records = _load()
    if not records:
        return {"error": "No data loaded"}
    rec = records[-1]
    return {
        "total_population": rec.total_population,
        **rec.citizens,
    }


def tool_get_economy() -> dict:
    records = _load()
    if not records:
        return {"error": "No data loaded"}
    rec = records[-1]
    return {
        "rub": rec.economy_rub,
        "usd": rec.economy_usd,
        "scalars": rec.economy_scalars,
    }


STATUS_LABELS = [
    "food_supply", "water_supply", "healthcare", "education",
    "entertainment", "retail_goods", "housing", "public_transport", "safety",
]


def tool_get_citizen_status() -> dict:
    records = _load()
    if not records:
        return {"error": "No data loaded"}
    rec = records[-1]
    labeled = {
        STATUS_LABELS[i]: v
        for i, v in enumerate(rec.citizen_status)
        if i < len(STATUS_LABELS)
    }
    return {"status": rec.citizen_status, "labeled": labeled}


def tool_get_history(metric: str = "total_population") -> dict:
    records = _load()
    if not records:
        return {"metric": metric, "data": [], "warning": "No records loaded"}
    data = []
    found = False
    for r in records:
        if metric == "total_population":
            val = r.total_population
            found = True
        elif metric in r.citizens:
            val = r.citizens[metric]
            found = True
        elif metric in r.economy_rub:
            val = r.economy_rub[metric]
            found = True
        else:
            val = None
        data.append({"index": r.index, "year": r.year, "day": r.day, "value": val})
    result: dict = {"metric": metric, "data": data}
    if not found:
        result["warning"] = f"Metric '{metric}' not found in any record"
    return result


def tool_get_trade() -> dict:
    records = _load()
    if not records:
        return {"error": "No data loaded"}
    rec = records[-1]
    return {
        "year": rec.year,
        "day": rec.day,
        "imports": {
            "rub": rec.trade_import_rub,
            "usd": rec.trade_import_usd,
            "international_rub": rec.trade_import_international_rub,
            "international_usd": rec.trade_import_international_usd,
            "vehicles_rub": rec.trade_vehicles.get("import_rub", 0.0),
            "vehicles_usd": rec.trade_vehicles.get("import_usd", 0.0),
        },
        "exports": {
            "rub": rec.trade_export_rub,
            "usd": rec.trade_export_usd,
            "international_rub": rec.trade_export_international_rub,
            "international_usd": rec.trade_export_international_usd,
            "vehicles_rub": rec.trade_vehicles.get("export_rub", 0.0),
            "vehicles_usd": rec.trade_vehicles.get("export_usd", 0.0),
        },
    }


_TRADE_FIELD_MAP = {
    ("import", "rub"): "trade_import_rub",
    ("export", "rub"): "trade_export_rub",
    ("import", "usd"): "trade_import_usd",
    ("export", "usd"): "trade_export_usd",
    ("import", "international_rub"): "trade_import_international_rub",
    ("export", "international_rub"): "trade_export_international_rub",
    ("import", "international_usd"): "trade_import_international_usd",
    ("export", "international_usd"): "trade_export_international_usd",
}


def tool_get_trade_history(resource: str, currency: str = "rub", direction: str = "import") -> dict:
    field = _TRADE_FIELD_MAP.get((direction, currency))
    if field is None:
        return {"error": f"Invalid params: direction={direction!r}, currency={currency!r}. "
                         f"Valid currency: rub, usd, international_rub, international_usd. "
                         f"Valid direction: import, export."}
    records = _load()
    if not records:
        return {"resource": resource, "currency": currency, "direction": direction, "data": []}
    data = []
    for r in records:
        trade_dict = getattr(r, field)
        val = trade_dict.get(resource)
        data.append({"index": r.index, "year": r.year, "day": r.day, "value": val})
    return {"resource": resource, "currency": currency, "direction": direction, "data": data}


def tool_list_saves() -> dict:
    saves = []
    if SAVES_DIR.exists():
        for p in sorted(SAVES_DIR.iterdir()):
            if p.is_dir() and (p / "stats.ini").exists():
                saves.append({"name": p.name, "path": str(p)})
    return {"saves": saves}


# ---------------------------------------------------------------------------
# MCP server wiring
# ---------------------------------------------------------------------------

server = Server("soviet-republic")

TOOLS = [
    Tool(
        name="get_stats",
        description="Get complete current game snapshot (population, economy, year/day)",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="get_population",
        description="Get citizen counts and demographics (adults, children, education, unemployment)",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="get_economy",
        description="Get all resource prices in RUB and USD",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="get_citizen_status",
        description="Get happiness/wellbeing metrics (0-1 scale) for food, water, healthcare, etc.",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="get_history",
        description="Get time series data for a metric across all saved records",
        inputSchema={
            "type": "object",
            "properties": {
                "metric": {
                    "type": "string",
                    "description": "Metric name: 'total_population', citizen field, or resource name (e.g. 'steel')",
                }
            },
        },
    ),
    Tool(
        name="list_saves",
        description="List all available save folders",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="get_trade",
        description="Get current import/export data: which resources were traded this period, in RUB and USD, including vehicle and international trade totals",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="get_trade_history",
        description="Get time series of trade volume for a specific resource across all saved records",
        inputSchema={
            "type": "object",
            "properties": {
                "resource": {
                    "type": "string",
                    "description": "Resource name, e.g. 'fuel', 'steel', 'food'",
                },
                "currency": {
                    "type": "string",
                    "description": "Currency: 'rub', 'usd', 'international_rub', 'international_usd'. Default: 'rub'",
                },
                "direction": {
                    "type": "string",
                    "description": "Trade direction: 'import' or 'export'. Default: 'import'",
                },
            },
            "required": ["resource"],
        },
    ),
]


@server.list_tools()
async def list_tools():
    return TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    dispatch = {
        "get_stats": lambda: tool_get_stats(),
        "get_population": lambda: tool_get_population(),
        "get_economy": lambda: tool_get_economy(),
        "get_citizen_status": lambda: tool_get_citizen_status(),
        "get_history": lambda: tool_get_history(arguments.get("metric", "total_population")),
        "list_saves": lambda: tool_list_saves(),
        "get_trade": lambda: tool_get_trade(),
        "get_trade_history": lambda: tool_get_trade_history(
            arguments.get("resource", "fuel"),
            arguments.get("currency", "rub"),
            arguments.get("direction", "import"),
        ),
    }
    fn = dispatch.get(name)
    try:
        result = fn() if fn is not None else {"error": f"Unknown tool: {name}"}
    except Exception as exc:
        logger.exception("Tool %r raised an exception", name)
        result = {"error": f"Tool execution failed: {exc}"}
    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]


async def run_mcp():
    """Entry point: run as MCP stdio server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )
```

**Step 2: Verify import works**

```bash
cd soviet_dashboard
python -c "from mcp_server import server; print('OK')"
```

Expected: `OK` (no ImportError)

---

### Task 2: Simplify main.py

**Files:**
- Modify: `soviet_dashboard/main.py`

**Step 1: Replace with minimal entry point**

The `--mcp` flag is still accepted (ignored) so existing `settings.json` configs don't break.

```python
"""Soviet Republic MCP Server

Run via: python main.py
"""
import asyncio
import logging

logging.basicConfig(level=logging.WARNING)

from mcp_server import run_mcp

asyncio.run(run_mcp())
```

**Step 2: Verify it imports cleanly**

```bash
python -c "import ast; ast.parse(open('main.py').read()); print('syntax OK')"
```

Expected: `syntax OK`

---

### Task 3: Update requirements.txt

**Files:**
- Modify: `soviet_dashboard/requirements.txt`

**Step 1: Replace with MCP-only dependencies**

```
mcp[cli]==1.3.0
```

---

### Task 4: Delete unused files

**Files to delete:**
- `soviet_dashboard/state.py`
- `soviet_dashboard/watcher.py`
- `soviet_dashboard/server.py`
- `soviet_dashboard/static/index.html`
- `soviet_dashboard/pyproject.toml`
- `soviet_dashboard/tests/` (entire directory)

**Step 1: Delete them**

```bash
cd soviet_dashboard
rm state.py watcher.py server.py pyproject.toml
rm -rf static/ tests/
```

**Step 2: Verify only MCP files remain**

```bash
ls *.py
```

Expected: `main.py  mcp_server.py  parser.py`

---

### Task 5: Smoke-test the MCP server

**Step 1: Verify startup (Ctrl+C after a few seconds)**

```bash
python main.py
```

Expected: process starts silently (no errors, no web server output). Kill with Ctrl+C.

**Step 2: Quick tool sanity check via Python**

```bash
python -c "
from mcp_server import tool_get_stats, tool_list_saves
saves = tool_list_saves()
print('saves:', saves)
stats = tool_get_stats()
print('stats keys:', list(stats.keys()))
"
```

Expected: prints saves list and stat keys without errors. If stats.ini doesn't exist on disk, `tool_get_stats` returns `{"error": "No data loaded"}` — that's fine.

---

### Task 6: Update MEMORY.md

**Files:**
- Modify: `C:/Users/tspor/.claude/projects/E--SteamLibrary-steamapps-common-SovietRepublic/memory/MEMORY.md`

Update the Architecture section to reflect the simplified structure:
- Remove references to `state.py`, `watcher.py`, `server.py`, `static/index.html`
- Update tech stack (remove fastapi, uvicorn, watchdog, httpx)
- Update test suite entry (no more tests)
- Note that `--mcp` flag is now ignored / no longer needed
