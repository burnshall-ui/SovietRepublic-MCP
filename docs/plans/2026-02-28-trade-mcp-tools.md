# Trade MCP Tools Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add `get_trade` and `get_trade_history` MCP tools exposing import/export data from `stats.ini`.

**Architecture:** Extend `StatRecord` with trade fields, add parser logic for `$Resources_Import/Export*` sections (same indented-line pattern as existing economy sections), then wire up two new pure tool functions in `mcp_server.py`.

**Tech Stack:** Python 3.13, existing pytest suite, no new dependencies.

---

### Task 1: Extend fixture with trade data

**Files:**
- Modify: `tests/fixtures/sample_stats.ini`

The fixture needs trade sections so parser tests have something to assert against. Add to record 0 (after the `$Economy_WorkdayCostRUB` line, before `Citizens`):

**Step 1: Add trade sections to record 0 in the fixture**

Insert after line `$Economy_WorkdayCostRUB 3.150000` in record 0:

```ini
$Economy_SellCostRUB
-------------
   steel 105.000000 0.950000
   coal 4.800000 0.950000
$end

$Economy_SellCostUSD
-------------
   steel 124.000000 0.950000
$end

$Resources_ImportRUB
-------------
   fuel 14.000000 0.000000
   coal 5.000000 0.000000
$end

$Resources_ExportRUB
-------------
   steel 3.000000 0.000000
$end

$Resources_ImportUSD
-------------
$end

$Resources_ExportUSD
-------------
$end

$Resources_ImportInternationalRUB
-------------
   food 2.000000 0.000000
$end

$Resources_ExportInternationalRUB
-------------
$end

$Resources_ImportInternationalUSD
-------------
$end

$Resources_ExportInternationalUSD
-------------
$end

$Vehicles_ImportRUB 12223.920898
$Vehicles_ExportRUB 0.000000
$Vehicles_ImportUSD 0.000000
$Vehicles_ExportUSD 0.000000
```

And add to record 1 (after `$Economy_WorkdayCostRUB 3.150000`, before `Citizens`):

```ini
$Resources_ImportRUB
-------------
   fuel 8.000000 0.000000
$end

$Resources_ExportRUB
-------------
$end

$Resources_ImportUSD
-------------
$end

$Resources_ExportUSD
-------------
$end

$Resources_ImportInternationalRUB
-------------
$end

$Resources_ExportInternationalRUB
-------------
$end

$Resources_ImportInternationalUSD
-------------
$end

$Resources_ExportInternationalUSD
-------------
$end

$Vehicles_ImportRUB 0.000000
$Vehicles_ExportRUB 0.000000
$Vehicles_ImportUSD 0.000000
$Vehicles_ExportUSD 0.000000
```

**Step 2: Verify fixture is still parseable**

```bash
cd E:/SteamLibrary/steamapps/common/SovietRepublic/soviet_dashboard
python -c "from parser import parse_stats_file; from pathlib import Path; r = parse_stats_file(Path('tests/fixtures/sample_stats.ini')); print(len(r), 'records')"
```
Expected: `2 records`

---

### Task 2: Add trade fields to StatRecord

**Files:**
- Modify: `soviet_dashboard/parser.py` (lines 6-23, the dataclass)

**Step 1: Write failing tests for new parser fields**

Add to `tests/test_parser.py`:

```python
def test_trade_import_rub_parsed():
    records = parse_stats_file(FIXTURE)
    r = records[0]
    assert r.trade_import_rub["fuel"] == pytest.approx(14.0)
    assert r.trade_import_rub["coal"] == pytest.approx(5.0)


def test_trade_export_rub_parsed():
    records = parse_stats_file(FIXTURE)
    r = records[0]
    assert r.trade_export_rub["steel"] == pytest.approx(3.0)


def test_trade_import_international_rub_parsed():
    records = parse_stats_file(FIXTURE)
    r = records[0]
    assert r.trade_import_international_rub["food"] == pytest.approx(2.0)


def test_trade_vehicles_parsed():
    records = parse_stats_file(FIXTURE)
    r = records[0]
    assert r.trade_vehicles["import_rub"] == pytest.approx(12223.920898)
    assert r.trade_vehicles["export_rub"] == pytest.approx(0.0)


def test_trade_isolated_between_records():
    """Record 1 imports only fuel 8.0, not record 0's coal."""
    records = parse_stats_file(FIXTURE)
    assert records[1].trade_import_rub.get("fuel") == pytest.approx(8.0)
    assert "coal" not in records[1].trade_import_rub


def test_trade_empty_sections_are_empty_dicts():
    records = parse_stats_file(FIXTURE)
    assert records[0].trade_import_usd == {}
    assert records[0].trade_export_usd == {}
```

**Step 2: Run tests to verify they fail**

```bash
cd E:/SteamLibrary/steamapps/common/SovietRepublic/soviet_dashboard
python -m pytest tests/test_parser.py::test_trade_import_rub_parsed -v
```
Expected: `FAILED` with `AttributeError: 'StatRecord' object has no attribute 'trade_import_rub'`

**Step 3: Add trade fields to StatRecord dataclass**

In `parser.py`, extend the `StatRecord` dataclass (after `citizen_status` field):

```python
trade_import_rub: dict = field(default_factory=dict)
trade_export_rub: dict = field(default_factory=dict)
trade_import_usd: dict = field(default_factory=dict)
trade_export_usd: dict = field(default_factory=dict)
trade_import_international_rub: dict = field(default_factory=dict)
trade_export_international_rub: dict = field(default_factory=dict)
trade_import_international_usd: dict = field(default_factory=dict)
trade_export_international_usd: dict = field(default_factory=dict)
trade_vehicles: dict = field(default_factory=dict)
```

**Step 4: Run tests — still fail (fields exist but parser doesn't fill them)**

```bash
python -m pytest tests/test_parser.py::test_trade_import_rub_parsed -v
```
Expected: `FAILED` with `assert {} == ...` (empty dict)

---

### Task 3: Add trade parsing logic to parser

**Files:**
- Modify: `soviet_dashboard/parser.py` (the `parse_stats_file` function)

The parser uses a `current_economy_section` string state variable. Add a `current_trade_section` variable that maps to the right dict on `current`.

**Step 1: Add the trade section map and state variable**

In `parse_stats_file`, after the `current_economy_section` variable declaration (line ~32), add:

```python
current_trade_section: Optional[str] = None  # key into StatRecord trade_* dicts
```

Add this mapping dict inside the function (before the loop):

```python
TRADE_SECTION_MAP = {
    "$Resources_ImportRUB": "trade_import_rub",
    "$Resources_ExportRUB": "trade_export_rub",
    "$Resources_ImportUSD": "trade_import_usd",
    "$Resources_ExportUSD": "trade_export_usd",
    "$Resources_ImportInternationalRUB": "trade_import_international_rub",
    "$Resources_ExportInternationalRUB": "trade_export_international_rub",
    "$Resources_ImportInternationalUSD": "trade_import_international_usd",
    "$Resources_ExportInternationalUSD": "trade_export_international_usd",
}
```

**Step 2: Reset trade section on new record**

In the `$STAT_RECORD` block (where `current_economy_section = None` is set), also add:
```python
current_trade_section = None
```

**Step 3: Add trade section header detection**

After the existing `$Economy_` handling block, add a new `if` block:

```python
# Trade section headers
if stripped in TRADE_SECTION_MAP:
    current_trade_section = TRADE_SECTION_MAP[stripped]
    current_economy_section = None
    continue

# $end resets trade section
if stripped == "$end":
    current_trade_section = None
    continue

# Scalar vehicle trade: $Vehicles_ImportRUB 12223.9
VEHICLE_KEYS = {
    "$Vehicles_ImportRUB": "import_rub",
    "$Vehicles_ExportRUB": "export_rub",
    "$Vehicles_ImportUSD": "import_usd",
    "$Vehicles_ExportUSD": "export_usd",
}
if stripped.split()[0] in VEHICLE_KEYS and len(stripped.split()) == 2:
    key = VEHICLE_KEYS[stripped.split()[0]]
    try:
        current.trade_vehicles[key] = float(stripped.split()[1])
    except ValueError:
        pass
    continue
```

**Step 4: Add indented-line handling for trade sections**

The existing indented-line block (around line 80) handles `current_economy_section`. Extend it to also handle `current_trade_section`:

The existing block looks like:
```python
# Economy resource line (indented): "   steel 113.013054 1.050000"
if line != stripped and stripped and current_economy_section:
    ...
```

Add after that block:

```python
# Trade resource line (indented): "   fuel 14.000004 0.000000"
if line != stripped and stripped and current_trade_section:
    parts = stripped.split()
    if len(parts) >= 2:
        name = parts[0]
        try:
            amount = float(parts[1])
            getattr(current, current_trade_section)[name] = amount
        except ValueError:
            pass
    continue
```

**Step 5: Reset trade section on non-$ non-indented lines**

The existing reset at the bottom of the loop:
```python
if not stripped.startswith("$"):
    current_economy_section = None
    continue
```
Extend to also reset trade section:
```python
if not stripped.startswith("$"):
    current_economy_section = None
    current_trade_section = None
    continue
```

**Step 6: Run all parser tests**

```bash
python -m pytest tests/test_parser.py -v
```
Expected: All tests PASS (both old and new)

**Step 7: Commit**

```bash
cd E:/SteamLibrary/steamapps/common/SovietRepublic/soviet_dashboard
git add tests/fixtures/sample_stats.ini tests/test_parser.py parser.py
git commit -m "feat: parse trade import/export sections from stats.ini"
```

---

### Task 4: Add `tool_get_trade` to mcp_server

**Files:**
- Modify: `soviet_dashboard/mcp_server.py`

**Step 1: Write failing MCP tests**

Add to `tests/test_mcp.py`:

```python
def test_get_trade_returns_dict():
    from mcp_server import tool_get_trade
    result = tool_get_trade()
    assert isinstance(result, dict)
    assert "imports" in result
    assert "exports" in result


def test_get_trade_import_rub():
    from mcp_server import tool_get_trade
    result = tool_get_trade()
    # Record 1 (latest) has fuel import 8.0
    assert result["imports"]["rub"].get("fuel") == pytest.approx(8.0)


def test_get_trade_vehicles():
    from mcp_server import tool_get_trade
    result = tool_get_trade()
    assert "vehicles_rub" in result["imports"]
    assert result["imports"]["vehicles_rub"] == pytest.approx(0.0)


def test_get_trade_no_data():
    from state import game_state
    from mcp_server import tool_get_trade
    game_state.records = []
    result = tool_get_trade()
    assert "error" in result
```

**Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_mcp.py::test_get_trade_returns_dict -v
```
Expected: `FAILED` with `ImportError` or `AttributeError`

**Step 3: Add `tool_get_trade` function to mcp_server.py**

Add after `tool_get_economy`:

```python
def tool_get_trade() -> dict:
    rec = game_state.latest
    if rec is None:
        return {"error": "No data loaded"}
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
```

**Step 4: Run MCP tests**

```bash
python -m pytest tests/test_mcp.py -v
```
Expected: all tests PASS

---

### Task 5: Add `tool_get_trade_history` to mcp_server

**Files:**
- Modify: `soviet_dashboard/mcp_server.py`

**Step 1: Write failing tests**

Add to `tests/test_mcp.py`:

```python
def test_get_trade_history_import():
    from mcp_server import tool_get_trade_history
    result = tool_get_trade_history(resource="fuel", currency="rub", direction="import")
    assert result["resource"] == "fuel"
    assert result["currency"] == "rub"
    assert result["direction"] == "import"
    assert len(result["data"]) == 2
    # record 0: fuel=14.0, record 1: fuel=8.0
    assert result["data"][0]["value"] == pytest.approx(14.0)
    assert result["data"][1]["value"] == pytest.approx(8.0)


def test_get_trade_history_export():
    from mcp_server import tool_get_trade_history
    result = tool_get_trade_history(resource="steel", currency="rub", direction="export")
    # record 0: steel exported 3.0, record 1: no steel export → None
    assert result["data"][0]["value"] == pytest.approx(3.0)
    assert result["data"][1]["value"] is None


def test_get_trade_history_missing_resource():
    from mcp_server import tool_get_trade_history
    result = tool_get_trade_history(resource="unobtainium", currency="rub", direction="import")
    for entry in result["data"]:
        assert entry["value"] is None


def test_get_trade_history_invalid_params():
    from mcp_server import tool_get_trade_history
    result = tool_get_trade_history(resource="fuel", currency="xyz", direction="import")
    assert "error" in result
```

**Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_mcp.py::test_get_trade_history_import -v
```
Expected: `FAILED` with `ImportError`

**Step 3: Add `tool_get_trade_history` function**

Add after `tool_get_trade`:

```python
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
    if not game_state.history:
        return {"resource": resource, "currency": currency, "direction": direction, "data": []}
    data = []
    for r in game_state.history:
        trade_dict = getattr(r, field)
        val = trade_dict.get(resource)  # None if not traded this period
        data.append({"index": r.index, "year": r.year, "day": r.day, "value": val})
    return {"resource": resource, "currency": currency, "direction": direction, "data": data}
```

**Step 4: Run all MCP tests**

```bash
python -m pytest tests/test_mcp.py -v
```
Expected: all tests PASS

---

### Task 6: Register new tools in MCP server

**Files:**
- Modify: `soviet_dashboard/mcp_server.py` (TOOLS list and dispatch dict)

**Step 1: Add tool definitions to TOOLS list**

Append to the `TOOLS` list:

```python
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
```

**Step 2: Add to dispatch dict in `call_tool`**

In the `dispatch` dict inside `call_tool`, add:

```python
"get_trade": lambda: tool_get_trade(),
"get_trade_history": lambda: tool_get_trade_history(
    arguments.get("resource", "fuel"),
    arguments.get("currency", "rub"),
    arguments.get("direction", "import"),
),
```

**Step 3: Run full test suite**

```bash
python -m pytest tests/ -v
```
Expected: all tests PASS (43+ tests, no failures)

**Step 4: Commit**

```bash
git add mcp_server.py tests/test_mcp.py
git commit -m "feat: add get_trade and get_trade_history MCP tools"
```

---

### Task 7: Smoke test with live game data

**Step 1: Start MCP server manually and verify output**

```bash
cd E:/SteamLibrary/steamapps/common/SovietRepublic/soviet_dashboard
python -c "
from parser import parse_stats_file
from state import game_state
from pathlib import Path
game_state.records = parse_stats_file(Path('media_soviet/save/autosave1/stats.ini'))
from mcp_server import tool_get_trade, tool_get_trade_history
import json
print(json.dumps(tool_get_trade(), indent=2))
print(json.dumps(tool_get_trade_history('fuel', 'rub', 'import'), indent=2))
"
```
Expected: JSON output with non-empty `imports` dict showing fuel and other traded resources.

**Step 2: Restart Claude Desktop app to pick up new MCP tools**

Fully close and reopen Claude Desktop. The new `get_trade` and `get_trade_history` tools should appear in the tool list.
