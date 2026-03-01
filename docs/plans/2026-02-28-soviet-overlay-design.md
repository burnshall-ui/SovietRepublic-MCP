# Soviet Republic Live-Dashboard – Design Doc

**Date:** 2026-02-28
**Status:** Approved

---

## Overview

A live dashboard for *Workers & Resources: Soviet Republic* that reads game save data in real-time, displays population and economic stats on a second monitor, and exposes the data to LLMs via both an in-dashboard chat interface (Ollama) and an MCP server (Claude Code).

---

## Goals

- Display live game stats on a second monitor, updating when the game autosaves
- Allow the user to chat with a local LLM ("Genosse Berater") that has full context of the current game state
- Expose game data to Claude Code via an MCP server for deeper analysis

---

## Architecture

### Single Python process (`main.py`)

```
soviet_dashboard/
├── main.py          # Entry point — starts webserver + watcher (+ MCP mode)
├── parser.py        # Parses stats.ini and other save files
├── watcher.py       # watchdog file system watcher
├── mcp_server.py    # MCP server tools (stdio mode)
└── static/
    └── index.html   # Dashboard UI (Chart.js via CDN, no build step)
```

**Start command:** `python main.py`
**MCP mode:** `python main.py --mcp` (stdio, for Claude Code integration)

### Webserver

- FastAPI on `http://localhost:8765`
- `GET /api/stats` — current parsed stats as JSON
- `GET /api/history` — all STAT_RECORD time series as JSON
- `WebSocket /ws` — pushes update whenever stats.ini changes
- `POST /api/chat` — proxies chat to Ollama with game context injected
- `GET /api/models` — list available Ollama models
- Static file serving for `static/index.html`

### File Watcher

- Monitors `media_soviet/save/autosave1/stats.ini` (newest autosave)
- On change: re-parse → update in-memory state → broadcast via WebSocket
- Also detects which autosave slot is most recently modified

---

## Dashboard UI

**Theme:** Dark, Soviet-inspired (dark background, red/gold accents)

### Sections

1. **Header** — Game year/day, last update timestamp, save name
2. **Population Tiles** — Total citizens, children, adults, unemployed, avg age, life expectancy, productivity
3. **Citizen Status Chart** — 9 happiness/wellbeing metrics as horizontal bar chart (`$Citizens_Status 0..8`)
4. **History Chart** — Line chart over all STAT_RECORD time entries; population growth + selectable resource prices
5. **Economy Table** — All resources with current price, color-coded (green=cheap, red=expensive)
6. **LLM Chat** — Chat field "Frag deinen sowjetischen Berater...", Ollama model selector dropdown, response displayed as "Genosse Berater"

### Live Updates

WebSocket connection: dashboard auto-refreshes charts/tiles on new data without page reload.

---

## MCP Server

Runs via stdio when invoked with `--mcp` flag.

### Claude Code integration

```json
// .claude/settings.json
{
  "mcpServers": {
    "soviet-republic": {
      "command": "python",
      "args": ["E:/SteamLibrary/steamapps/common/SovietRepublic/soviet_dashboard/main.py", "--mcp"]
    }
  }
}
```

### Tools

| Tool | Description |
|------|-------------|
| `get_stats()` | Complete current snapshot |
| `get_population()` | Citizen counts and demographics |
| `get_economy()` | All resource prices |
| `get_citizen_status()` | Happiness/wellbeing metrics (0–8) |
| `get_history(metric)` | Time series for a given metric |
| `list_saves()` | List all save folders with dates |

---

## Data Sources

All readable plain-text files in `media_soviet/save/autosave*/`:

| File | Content |
|------|---------|
| `stats.ini` | Economy, citizens, history records — primary source |
| `city_names.txt` | City names on the map |
| `script.ini` | World config (grid size, terrain type, world size) |
| `header.bin` | Binary — not parsed initially |
| `*.bin` | Binary save data — not parsed initially |

---

## Tech Stack

| Component | Library |
|-----------|---------|
| Web server | `fastapi` + `uvicorn` |
| File watching | `watchdog` |
| MCP server | `mcp` (Python SDK) |
| Ollama chat | `httpx` (async HTTP to Ollama REST API) |
| Frontend charts | Chart.js (CDN) |
| Frontend UI | Vanilla HTML/CSS/JS |

---

## Out of Scope (for now)

- Parsing binary `.bin` save files
- Writing/modifying game data
- Multi-save comparison
- External deployment
