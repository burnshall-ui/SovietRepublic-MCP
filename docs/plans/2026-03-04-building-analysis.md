# Building Analysis Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add three MCP tools: `get_production_chain`, `get_break_even`, and `get_spend_period`, plus the parser extension needed for spend data.

**Architecture:** Parser gets 4 new spend fields (same format as existing trade sections). Two pure building-analysis functions are added to mcp_server.py using already-loaded building data. Break-even combines building I/O with live economy prices. No new files needed.

**Tech Stack:** Python 3.13, mcp[cli]==1.3.0, pytest

---

### Task 1: Add spend sections to parser

**Files:**
- Modify: `parser.py`

**Step 1: Write failing test**

Create `tests/test_parser.py`:

```python
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from parser import parse_stats_file

STATS = pathlib.Path(__file__).parent.parent.parent / "media_soviet" / "save" / "autosave1" / "stats.ini"

def test_spend_fields_exist():
    records = parse_stats_file(STATS)
    rec = records[-1]
    assert hasattr(rec, "spend_constructions")
    assert hasattr(rec, "spend_factories")
    assert hasattr(rec, "spend_shops")
    assert hasattr(rec, "spend_vehicles")

def test_spend_vehicles_has_fuel():
    """SpendVehicles contains fuel data in most records."""
    records = parse_stats_file(STATS)
    fuel_found = any(r.spend_vehicles.get("fuel") for r in records)
    assert fuel_found, "Expected at least one record with fuel in spend_vehicles"

def test_spend_constructions_has_workers():
    """SpendConstructions contains workers/gravel in active construction records."""
    records = parse_stats_file(STATS)
    workers_found = any(r.spend_constructions.get("workers") for r in records)
    assert workers_found, "Expected at least one record with workers in spend_constructions"
```

**Step 2: Run test to verify it fails**

```
cd soviet_dashboard
python -m pytest tests/test_parser.py -v
```
Expected: `AttributeError: 'StatRecord' object has no attribute 'spend_constructions'`

**Step 3: Implement — add to `parser.py`**

In the `StatRecord` dataclass, add four new fields after `trade_vehicles`:
```python
spend_constructions: dict = field(default_factory=dict)
spend_factories: dict = field(default_factory=dict)
spend_shops: dict = field(default_factory=dict)
spend_vehicles: dict = field(default_factory=dict)
```

In `parse_stats_file`, extend `TRADE_SECTION_MAP` with (add alongside existing entries):
```python
"$Resources_SpendConstructions": "spend_constructions",
"$Resources_SpendFactories":     "spend_factories",
"$Resources_SpendShops":         "spend_shops",
"$Resources_SpendVehicles":      "spend_vehicles",
```

The spend sections use the same indented `resource amount cost` format as trade sections — the existing trade parsing loop handles them automatically once the section map is extended.

**Step 4: Run test to verify it passes**

```
python -m pytest tests/test_parser.py -v
```
Expected: all 3 tests PASS

---

### Task 2: Add `get_spend_period` tool

**Files:**
- Modify: `mcp_server.py`

**Step 1: Write failing test**

Add to `tests/test_mcp_tools.py` (create file):

```python
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from mcp_server import tool_get_spend_period

def test_spend_period_vehicles_returns_fuel():
    result = tool_get_spend_period("vehicles")
    assert "error" not in result
    assert "period" in result
    assert "vehicles" in result
    # SpendVehicles always has fuel in this save
    assert "fuel" in result["vehicles"]

def test_spend_period_invalid_section():
    result = tool_get_spend_period("invalid")
    assert "error" in result

def test_spend_period_all_sections():
    result = tool_get_spend_period("all")
    assert "error" not in result
    for section in ("constructions", "factories", "shops", "vehicles"):
        assert section in result
```

**Step 2: Run test to verify it fails**

```
python -m pytest tests/test_mcp_tools.py -v
```
Expected: `ImportError` or `AttributeError`

**Step 3: Implement in `mcp_server.py`**

Add section map constant after `_TRADE_FIELD_MAP`:
```python
_SPEND_FIELD_MAP = {
    "constructions": "spend_constructions",
    "factories":     "spend_factories",
    "shops":         "spend_shops",
    "vehicles":      "spend_vehicles",
}
```

Add tool function before `tool_list_saves`:
```python
def tool_get_spend_period(
    section: str = "all",
    start_year: int = None,
    start_day: int = None,
    end_year: int = None,
    end_day: int = None,
) -> dict:
    if section != "all" and section not in _SPEND_FIELD_MAP:
        return {"error": f"Invalid section: {section!r}. Valid: {list(_SPEND_FIELD_MAP)} + 'all'"}
    records = _load()
    if not records:
        return {"error": "No data loaded"}
    valid = [r for r in records if r.year > 0]
    if not valid:
        return {"error": "No valid records"}

    start_rec = _find_nearest_record(valid, start_year, start_day if start_day else 1, "at_or_after") if start_year else valid[0]
    end_rec   = _find_nearest_record(valid, end_year,   end_day   if end_day   else 365, "at_or_before") if end_year else valid[-1]

    if start_rec is None or end_rec is None:
        return {"error": "No records found for the specified date range"}
    if _date_key(end_rec.year, end_rec.day) < _date_key(start_rec.year, start_rec.day):
        return {"error": "End date is before start date"}

    sections = list(_SPEND_FIELD_MAP) if section == "all" else [section]
    result = {
        "period": {"from": f"{start_rec.year}/{start_rec.day}", "to": f"{end_rec.year}/{end_rec.day}"},
    }
    for sec in sections:
        field = _SPEND_FIELD_MAP[sec]
        result[sec] = _diff_trade_dicts(getattr(end_rec, field), getattr(start_rec, field))
    return result
```

Add Tool definition in `TOOLS` list (before `list_saves`):
```python
Tool(
    name="get_spend_period",
    description=(
        "Get resource consumption totals for a date range, by category. "
        "section: 'constructions' (building materials), 'factories' (production inputs), "
        "'shops' (retail goods), 'vehicles' (fuel), or 'all'. "
        "Returns quantity (physical units) and cost per resource."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "section": {"type": "string", "description": "Category: 'constructions', 'factories', 'shops', 'vehicles', or 'all'. Default: 'all'"},
            "start_year": {"type": "integer", "description": "Start year. Omit for game start."},
            "start_day":  {"type": "integer", "description": "Start day (1-365). Default: 1"},
            "end_year":   {"type": "integer", "description": "End year. Omit for latest."},
            "end_day":    {"type": "integer", "description": "End day (1-365). Default: 365"},
        },
    },
),
```

Add dispatch entry:
```python
"get_spend_period": lambda: tool_get_spend_period(
    arguments.get("section", "all"),
    arguments.get("start_year"),
    arguments.get("start_day"),
    arguments.get("end_year"),
    arguments.get("end_day"),
),
```

**Step 4: Run tests**

```
python -m pytest tests/test_mcp_tools.py -v
```
Expected: all 3 tests PASS

---

### Task 3: Add `get_production_chain` tool

**Files:**
- Modify: `mcp_server.py`

**Step 1: Write failing test**

Add to `tests/test_mcp_tools.py`:

```python
from mcp_server import tool_get_production_chain

def test_chain_electricity():
    result = tool_get_production_chain("eletric")
    assert "error" not in result
    assert result["resource"] == "eletric"
    assert len(result["producers"]) > 0
    names = [p["building"] for p in result["producers"]]
    assert "powerplant_coal" in names

def test_chain_marks_recommended():
    result = tool_get_production_chain("eletric")
    recommended = [p for p in result["producers"] if p.get("recommended")]
    assert len(recommended) == 1

def test_chain_unknown_resource():
    result = tool_get_production_chain("unobtainium")
    assert "error" in result or result["producers"] == []

def test_chain_inputs_traced():
    result = tool_get_production_chain("aluminium")
    aluminium_plant = next(p for p in result["producers"] if p["building"] == "aluminium_plant")
    assert "alumina" in aluminium_plant["inputs"]
    # alumina has its own producers
    assert aluminium_plant["inputs"]["alumina"]["produced_by"] != []
```

**Step 2: Run test to verify it fails**

```
python -m pytest tests/test_mcp_tools.py::test_chain_electricity -v
```
Expected: `ImportError` or `AttributeError`

**Step 3: Implement in `mcp_server.py`**

Add helper before `tool_list_saves`:

```python
def _build_resource_producer_map() -> dict[str, list[dict]]:
    """Returns {resource: [building_dict, ...]} for all buildings."""
    result: dict[str, list] = {}
    for b in _load_buildings():
        for resource in b["production"]:
            result.setdefault(resource, []).append(b)
    return result


def _trace_chain(resource: str, producer_map: dict, visited: set, depth: int = 0) -> dict:
    if depth > 6:  # guard against runaway recursion
        return {"resource": resource, "producers": [], "note": "max depth reached"}
    producers_raw = producer_map.get(resource, [])
    if not producers_raw:
        return {"resource": resource, "producers": []}

    # Efficiency metric: output_rate / workers (None workers → 0)
    def efficiency(b):
        w = b["workers_needed"] or 1
        rate = b["production"].get(resource, 0)
        cps_rate = b["consumption_per_second"].get(resource, 0) * 3600
        return (rate + cps_rate) / w

    best = max(producers_raw, key=efficiency)

    producers_out = []
    for b in producers_raw:
        if b["name"] in visited:
            continue
        visited.add(b["name"])

        all_consumed = {**b["consumption"]}
        # Add per-second rates (×3600 to put on same scale as hourly rates)
        for r, rate in b["consumption_per_second"].items():
            all_consumed[r] = all_consumed.get(r, 0) + rate * 3600

        inputs = {}
        for inp_resource, inp_rate in all_consumed.items():
            sub = _trace_chain(inp_resource, producer_map, visited.copy(), depth + 1)
            inputs[inp_resource] = {
                "rate": inp_rate,
                "produced_by": [p["building"] for p in sub["producers"]],
            }

        eff = efficiency(b)
        producers_out.append({
            "building": b["name"],
            "workers": b["workers_needed"],
            "output_rate": b["production"].get(resource, 0),
            "efficiency": round(eff, 6),
            "recommended": b["name"] == best["name"],
            "inputs": inputs,
        })

    return {"resource": resource, "producers": producers_out}


def tool_get_production_chain(resource: str) -> dict:
    if not resource:
        return {"error": "Missing required argument: resource"}
    producer_map = _build_resource_producer_map()
    if resource not in producer_map:
        return {"resource": resource, "producers": [],
                "note": "No building produces this resource — it is a raw material or import."}
    return _trace_chain(resource, producer_map, set())
```

Add Tool definition in `TOOLS` (before `list_saves`):
```python
Tool(
    name="get_production_chain",
    description=(
        "Trace the full production chain for a resource. Shows all buildings that produce it, "
        "their input requirements, and recursively what produces those inputs. "
        "Marks the most efficient producer (highest output/worker ratio) as 'recommended'. "
        "Leaf inputs with no producer are raw materials or imports."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "resource": {"type": "string", "description": "Resource name, e.g. 'aluminium', 'eletric', 'steel', 'food'"},
        },
        "required": ["resource"],
    },
),
```

Add dispatch entry:
```python
"get_production_chain": lambda: tool_get_production_chain(arguments.get("resource", "")),
```

**Step 4: Run all chain tests**

```
python -m pytest tests/test_mcp_tools.py -k "chain" -v
```
Expected: all 4 PASS

---

### Task 4: Add `get_break_even` tool

**Files:**
- Modify: `mcp_server.py`

**Step 1: Write failing test**

Add to `tests/test_mcp_tools.py`:

```python
from mcp_server import tool_get_break_even

def test_break_even_coal_plant():
    result = tool_get_break_even("powerplant_coal")
    assert "error" not in result
    assert result["building"] == "powerplant_coal"
    assert "outputs" in result
    assert "eletric" in result["outputs"]
    eletric = result["outputs"]["eletric"]
    assert "material_cost_per_unit" in eletric
    assert "import_price" in eletric

def test_break_even_unknown_building():
    result = tool_get_break_even("nonexistent_building")
    assert "error" in result

def test_break_even_shows_margin():
    result = tool_get_break_even("powerplant_coal")
    eletric = result["outputs"]["eletric"]
    assert "margin_per_unit" in eletric
```

**Step 2: Run test to verify it fails**

```
python -m pytest tests/test_mcp_tools.py -k "break_even" -v
```
Expected: `ImportError` or `AttributeError`

**Step 3: Implement in `mcp_server.py`**

Add tool function before `tool_list_saves`:

```python
def tool_get_break_even(building: str) -> dict:
    if not building:
        return {"error": "Missing required argument: building"}
    path = BUILDINGS_DIR / f"{building}.ini"
    if not path.exists():
        matches = [p for p in BUILDINGS_DIR.glob("*.ini") if p.stem.lower() == building.lower()]
        if not matches:
            return {"error": f"Building '{building}' not found. Use list_buildings to browse."}
        path = matches[0]
    b = _parse_building(path)

    records = _load()
    if not records:
        return {"error": "No economy data loaded"}
    rec = records[-1]
    prices_rub = rec.economy_rub
    workday_cost = rec.economy_scalars.get("Economy_WorkdayCostRUB", 0.0)

    # Total material input cost per in-game period
    total_input_cost = 0.0
    inputs_detail = {}
    for resource, rate in b["consumption"].items():
        price = prices_rub.get(resource, None)
        cost = (price * rate) if price is not None else None
        if cost is not None:
            total_input_cost += cost
        inputs_detail[resource] = {
            "rate": rate,
            "price_rub": price,
            "cost_per_period": round(cost, 4) if cost is not None else "price unknown",
        }
    # Per-second consumption (electricity demand etc.) — shown separately, not summed
    for resource, rate in b["consumption_per_second"].items():
        price = prices_rub.get(resource, None)
        inputs_detail[resource] = {
            "rate_per_second": rate,
            "price_rub": price,
            "note": "per-second rate — not included in material cost sum",
        }

    outputs = {}
    for resource, output_rate in b["production"].items():
        import_price = prices_rub.get(resource)
        if output_rate > 0:
            mat_cost_per_unit = round(total_input_cost / output_rate, 4) if output_rate else None
            margin = round(import_price - mat_cost_per_unit, 4) if (import_price is not None and mat_cost_per_unit is not None) else None
            outputs[resource] = {
                "output_rate": output_rate,
                "import_price": import_price,
                "material_cost_per_unit": mat_cost_per_unit,
                "margin_per_unit": margin,
                "profitable_vs_import": (margin > 0) if margin is not None else None,
            }

    result = {
        "building": b["name"],
        "type": b["type"],
        "workers": b["workers_needed"],
        "workday_cost_rub": workday_cost if workday_cost else "not set",
        "inputs": inputs_detail,
        "outputs": outputs,
    }
    if not workday_cost:
        result["note"] = "Worker salary (Economy_WorkdayCostRUB) is 0 — margin excludes labor costs."
    return result
```

Add Tool definition in `TOOLS` (before `list_saves`):
```python
Tool(
    name="get_break_even",
    description=(
        "Calculate production profitability for a building. Combines building I/O rates "
        "with current market prices to show material cost per unit of output vs import price. "
        "Positive margin = cheaper to produce than import. "
        "Worker salary included if Economy_WorkdayCostRUB is set in game settings."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "building": {"type": "string", "description": "Building name, e.g. 'powerplant_coal', 'steel_mill'"},
        },
        "required": ["building"],
    },
),
```

Add dispatch entry:
```python
"get_break_even": lambda: tool_get_break_even(arguments.get("building", "")),
```

**Step 4: Run all tests**

```
python -m pytest tests/ -v
```
Expected: all tests PASS

---

### Task 5: Update README and Memory

**Files:**
- Modify: `README.md`
- Modify: `C:/Users/tspor/.claude/projects/E--SteamLibrary-steamapps-common-SovietRepublic/memory/MEMORY.md`

Update tool count to **13** in README. Add three rows to the tool table:

```markdown
| `get_production_chain` | Trace full production chain for any resource, with efficiency ranking |
| `get_break_even`       | Compare production cost vs import price for a building |
| `get_spend_period`     | Resource consumption totals by category (construction/factory/vehicles) for a date range |
```

Update `mcp_server.py    # 10 MCP tools` → `# 13 MCP tools`

Update MEMORY.md tool list to include the three new tools and note spend fields in parser.

---

### Verify response sizes

```
python -c "
import json
from mcp_server import tool_get_production_chain, tool_get_break_even, tool_get_spend_period

for label, fn in [
    ('chain aluminium', lambda: tool_get_production_chain('aluminium')),
    ('chain eletric',   lambda: tool_get_production_chain('eletric')),
    ('break_even coal', lambda: tool_get_break_even('powerplant_coal')),
    ('spend all',       lambda: tool_get_spend_period('all')),
]:
    r = fn()
    t = json.dumps(r, indent=2)
    print(f'{label}: {len(t):,} chars (~{len(t)//4:,} tokens)')
"
```

All results should stay well under 20k characters.
