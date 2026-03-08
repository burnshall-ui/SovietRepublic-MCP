# SovietRepublic-MCP

MCP server for [Workers & Resources: Soviet Republic](https://store.steampowered.com/app/784150/Workers__Resources_Soviet_Republic/). Exposes live game data as tools for Claude Code and Claude Desktop.

## What it does

Reads live game data on every tool call — no background process, no stale cache. Two data sources are used:

- **`header.bin`** — contains the current in-game date and money balance, updated every autosave (~weekly in-game). Used by `get_realtime`.
- **`stats.ini`** — contains period records (one snapshot per completed game year) with full economy, trade, and population history. Used by all other tools.

### Available tools

| Tool | Description |
|---|---|
| `get_stats` | Full snapshot: population, economy, year/day |
| `get_population` | Citizen counts and demographics |
| `get_economy` | All resource prices in RUB and USD |
| `get_citizen_status` | Happiness metrics (food, water, healthcare, …) on 0–1 scale |
| `get_history` | Time series for any metric across all autosave records |
| `get_trade` | Cumulative import/export totals since game start |
| `get_trade_period` | Import/export totals for a specific date range (delta between two snapshots) |
| `list_buildings` | Browse building definitions filtered by type, produced or consumed resource |
| `get_building_info` | Full I/O details for a specific building (workers, production rates, consumption rates) |
| `get_spend_period` | Resources consumed by constructions, factories, shops, or vehicles in a date range |
| `get_production_chain` | All buildings that produce a resource, with input requirements and efficiency ranking |
| `get_break_even` | Material cost per unit output vs import price — shows margin and profitability |
| `get_realtime` | Current date and money (RUB + USD) from `header.bin` — more up-to-date than period records |
| `list_saves` | All available save folders |

## Requirements

- Python 3.10+
- Workers & Resources: Soviet Republic installed (Steam)
- `mcp[cli]==1.3.0`

```
pip install -r requirements.txt
```

## Setup

### Claude Code (`~/.claude/settings.json`)

```json
{
  "mcpServers": {
    "soviet-republic": {
      "command": "python",
      "args": ["E:/SteamLibrary/steamapps/common/SovietRepublic/soviet_dashboard/main.py"]
    }
  }
}
```

### Claude Desktop (`claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "soviet-republic": {
      "command": "C:\\Users\\<you>\\AppData\\Local\\Programs\\Python\\Python313\\python.exe",
      "args": ["E:\\SteamLibrary\\steamapps\\common\\SovietRepublic\\soviet_desktop\\main.py"]
    }
  }
}
```

Restart Claude after editing the config. The server starts automatically when needed.

### Choosing a save

By default the server loads the **most recently modified** save — whatever you last saved or autosaved in-game. No configuration needed.

To pin a specific save, set the `SOVIET_SAVE` environment variable to the folder name inside `media_soviet/save/`:

**Claude Code** (`~/.claude/settings.json`):
```json
{
  "mcpServers": {
    "soviet-republic": {
      "command": "python",
      "args": ["E:/SteamLibrary/steamapps/common/SovietRepublic/soviet_dashboard/main.py"],
      "env": {
        "SOVIET_SAVE": "autosave2"
      }
    }
  }
}
```

**Claude Desktop** (`claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "soviet-republic": {
      "command": "python.exe",
      "args": ["E:\\SteamLibrary\\steamapps\\common\\SovietRepublic\\soviet_dashboard\\main.py"],
      "env": {
        "SOVIET_SAVE": "Meine Stadt"
      }
    }
  }
}
```

Use `list_saves` to see all available save folders. The response includes `"active_save"` showing which one is currently loaded.

## Data sources and field meanings

Understanding what each data field actually represents avoids common misinterpretations:

### `economy_rub` / `economy_usd` — Market prices, NOT production quantities

The most important thing to know: the `economy_rub` and `economy_usd` fields returned by `get_stats` and `get_economy` are **import/export market prices per unit** (RUB or USD per tonne, per MWh, per m³, etc.). They do NOT represent how much of a resource your republic produced.

```json
"economy_rub": {
  "steel": 763.18,       ← 763 RUB per tonne (market price)
  "chemicals": 1953.67,  ← 1953 RUB per tonne (market price)
  "nuclearfuel": 246327  ← 246,327 RUB per unit (market price)
}
```

### `Resources_Produced` — Actual production quantities (natural resources only)

The game only logs production quantities for **naturally extracted / grown resources**:
- `rawbauxite` (Rohes Bauxit)
- `plants` (Pflanzen)
- `food` (Essen)
- `gravel` (Kies)
- `rawgravel` (Bruchstein)
- `asphalt`, `concrete`, etc.

Factory-processed goods (steel, aluminium, chemicals, electronics, …) are **not tracked as production quantities** in `stats.ini`. Use the in-game Statistics → Production tab for those.

### Data sources summary

| What you want | Tool | What it returns |
|---|---|---|
| Current date & money balance | `get_realtime` | Live from `header.bin` |
| Production quantities (natural) | `get_spend_period section=factories` | Factory input consumption as proxy |
| Market prices for resources | `get_economy` / `get_stats` → economy_rub/usd | Price per unit |
| Import/export volumes | `get_trade_period` | Tonnes traded, cost paid |
| Population & demographics | `get_population` | Citizen counts |
| Historical price trends | `get_history metric=steel` | Price over time |

## Usage

Once connected, ask Claude naturally:

**Economy & trade**
> *"What's my current food supply satisfaction?"*
> *"Show me steel import history."*
> *"How much have I imported vs exported this year?"*
> *"What are the current market prices for building materials?"*

**Production planning**
> *"What buildings can produce aluminium, and which is the most efficient?"*
> *"What's the full production chain for steel — what raw materials do I need?"*
> *"Is it cheaper to produce electricity with a coal plant or to import it?"*
> *"Show me the break-even analysis for the steel mill."*

**Resource consumption**
> *"What resources did my construction sites use this year?"*
> *"How much fuel have my vehicles consumed since the start of the game?"*
> *"What did my factories consume last year compared to this year?"*

**Building lookup**
> *"List all buildings that produce concrete."*
> *"What are the input and output rates of the coal processing plant?"*

## Project structure

```
main.py          # Entry point — asyncio.run(run_mcp())
mcp_server.py    # 17 MCP tools, reads fresh from disk per call
parser.py        # Parses stats.ini → StatRecord dataclasses
requirements.txt # mcp[cli]==1.3.0
```
