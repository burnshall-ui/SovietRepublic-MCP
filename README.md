# SovietRepublic-MCP

MCP server for [Workers & Resources: Soviet Republic](https://store.steampowered.com/app/524850/Workers__Resources_Soviet_Republic/). Exposes live game data as tools for Claude Code and Claude Desktop.

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
| `get_trade` | Current period import/export totals |
| `get_trade_history` | Trade volume over time for a specific resource |
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

> *"Wie entwickelt sich meine Bevölkerung?"*
> *"What's my current food supply satisfaction?"*
> *"Show me steel import history."*

## Project structure

```
main.py          # Entry point — asyncio.run(run_mcp())
mcp_server.py    # 8 MCP tools, reads fresh from disk per call
parser.py        # Parses stats.ini → StatRecord dataclasses
requirements.txt # mcp[cli]==1.3.0
```
