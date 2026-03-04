# SovietRepublic-MCP

MCP server for [Workers & Resources: Soviet Republic](https://store.steampowered.com/app/784150/Workers__Resources_Soviet_Republic/). Exposes live game data as tools for Claude Code and Claude Desktop.

## What it does

Reads the game's autosave (`stats.ini`) on every tool call and returns current data — no background process, no stale cache.

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
| `list_saves` | All available save folders |

## Requirements

- Python 3.10+
- Workers & Resources: Soviet Republic installed (Steam)
- `mcp[cli]==1.3.0`

```
pip install -r requirements.txt
```

## Setup

The server expects the game installed at the default Steam path. The autosave is read from:

```
<game root>/media_soviet/save/autosave1/stats.ini
```

If your game is installed elsewhere, update `STATS_PATH` in `mcp_server.py`.

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
      "args": ["E:\\SteamLibrary\\steamapps\\common\\SovietRepublic\\soviet_dashboard\\main.py"]
    }
  }
}
```

Restart Claude after editing the config. The server starts automatically when needed.

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
mcp_server.py    # 13 MCP tools, reads fresh from disk per call
parser.py        # Parses stats.ini → StatRecord dataclasses
requirements.txt # mcp[cli]==1.3.0
```
