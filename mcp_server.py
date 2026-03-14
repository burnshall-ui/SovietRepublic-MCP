"""
MCP server exposing Soviet Republic game data as tools.

Run standalone via: python main.py
Pure tool functions are also imported directly by tests.
"""
import json
import logging
import os
import struct
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from parser import parse_stats_file

logger = logging.getLogger(__name__)

SAVES_DIR = Path(__file__).parent.parent / "media_soviet" / "save"
BUILDINGS_DIR = Path(__file__).parent.parent / "media_soviet" / "buildings_types"
ACTIVE_SAVE_FILE = Path(__file__).parent / "active_save.cfg"


def _get_stats_path() -> Path:
    """Return path to stats.ini.

    Priority:
    1. active_save.cfg file (set via set_active_save tool)
    2. SOVIET_SAVE env var (folder name, e.g. "autosave2" or "SEHR NEU")
    3. Most recently modified save folder that contains stats.ini
    """
    if ACTIVE_SAVE_FILE.exists():
        save_name = ACTIVE_SAVE_FILE.read_text(encoding="utf-8").strip()
        if save_name:
            explicit = SAVES_DIR / save_name / "stats.ini"
            if explicit.exists():
                return explicit
            logger.warning("active_save.cfg=%r not found, falling back", save_name)

    save_name = os.environ.get("SOVIET_SAVE", "").strip()
    if save_name:
        explicit = SAVES_DIR / save_name / "stats.ini"
        if explicit.exists():
            return explicit
        logger.warning("SOVIET_SAVE=%r not found, falling back to newest save", save_name)

    candidates = [p / "stats.ini" for p in SAVES_DIR.iterdir()
                  if p.is_dir() and (p / "stats.ini").exists()]
    if not candidates:
        return SAVES_DIR / "autosave1" / "stats.ini"  # safe fallback
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _load() -> list:
    path = _get_stats_path()
    if not path.exists():
        return []
    return parse_stats_file(path)

# ---------------------------------------------------------------------------
# Pure tool functions — no MCP dependency, tested directly
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


def tool_get_history(metric: str = "total_population", limit: int = 50) -> dict:
    records = _load()
    if not records:
        return {"metric": metric, "data": [], "warning": "No records loaded"}
    data = []
    found = False
    for r in sorted(records, key=lambda r: _date_key(r.year, r.day)):
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
    if limit > 0:
        data = data[-limit:]
    result: dict = {"metric": metric, "data": data, "total_records": len(records)}
    if limit > 0 and len(records) > limit:
        result["note"] = f"Showing last {limit} of {len(records)} records. Pass limit=0 for all."
    if not found:
        result["warning"] = f"Metric '{metric}' not found in any record"
    return result


def tool_get_trade() -> dict:
    records = _load()
    if not records:
        return {"error": "No data loaded"}
    # Use the record with the largest total export value (the cumulative grand-total
    # record), rather than records[-1] which may have a stale/wrong date due to the
    # mega-record structure in stats.ini.
    def _trade_total(r):
        return sum(
            (e["amount"] if isinstance(e, dict) else e)
            for e in r.trade_export_rub.values()
        ) + sum(
            (e["amount"] if isinstance(e, dict) else e)
            for e in r.trade_import_rub.values()
        )
    rec = max(records, key=_trade_total)
    # Use the latest periodic record's date (mega-record date is unreliable)
    valid_dated = [r for r in records if r.year > 0]
    latest = max(valid_dated, key=lambda r: _date_key(r.year, r.day)) if valid_dated else rec
    return {
        "year": latest.year,
        "day": latest.day,
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

_SPEND_FIELD_MAP = {
    "constructions": "spend_constructions",
    "factories":     "spend_factories",
    "shops":         "spend_shops",
    "vehicles":      "spend_vehicles",
}


def _date_key(year: int, day: int) -> int:
    """Convert year+day to a sortable integer for comparison."""
    return year * 1000 + day


def _find_nearest_record(records: list, year: int, day: int, mode: str = "nearest"):
    """Find the record nearest to a given date.
    mode='at_or_after' — first record >= date (for period start)
    mode='at_or_before' — last record <= date (for period end)
    mode='nearest' — closest by absolute distance
    """
    target = _date_key(year, day)
    best = None
    best_dist = float("inf")

    for r in records:
        rk = _date_key(r.year, r.day)
        if mode == "at_or_after" and rk < target:
            continue
        if mode == "at_or_before" and rk > target:
            continue
        dist = abs(rk - target)
        if dist < best_dist:
            best = r
            best_dist = dist
    return best


def _sum_trade_values(records: list, field: str) -> dict:
    """Sum per-resource amounts across all records for a given trade/spend field.

    Each periodic record stores the amount traded/spent during that ~5-day
    period (NOT a running cumulative).  Summing gives the total for the range.
    Cost data in periodic records is typically 0, so only amounts are reliable.
    """
    totals: dict[str, float] = {}
    for r in records:
        for k, entry in getattr(r, field).items():
            amt = entry["amount"] if isinstance(entry, dict) else entry
            totals[k] = totals.get(k, 0.0) + amt
    return {k: {"quantity": round(v, 2)} for k, v in sorted(totals.items()) if round(v, 2) != 0.0}


def tool_get_trade_period(
    start_year: int = None,
    start_day: int = None,
    end_year: int = None,
    end_day: int = None,
    direction: str = "both",
    currency: str = "rub",
) -> dict:
    """Trade totals for a date range, computed by summing periodic record values."""
    records = _load()
    if not records:
        return {"error": "No data loaded"}

    # Filter out index-0 records with year=0 (empty/placeholder), sort by date
    valid = sorted([r for r in records if r.year > 0], key=lambda r: _date_key(r.year, r.day))
    if not valid:
        return {"error": "No valid records with date > 0"}

    # Determine date range
    s_year = start_year if start_year is not None else valid[0].year
    s_day = start_day if start_day is not None else 1
    e_year = end_year if end_year is not None else valid[-1].year
    e_day = end_day if end_day is not None else 365
    range_start = _date_key(s_year, s_day)
    range_end = _date_key(e_year, e_day)

    # Select all records within the date range
    in_range = [r for r in valid if range_start <= _date_key(r.year, r.day) <= range_end]
    if not in_range:
        return {"error": f"No records found between {s_year}/{s_day} and {e_year}/{e_day}"}

    result = {
        "period": {
            "from": f"{in_range[0].year}/{in_range[0].day}",
            "to": f"{in_range[-1].year}/{in_range[-1].day}",
        },
        "currency": currency,
        "records_summed": len(in_range),
    }

    import_field = _TRADE_FIELD_MAP.get(("import", currency))
    export_field = _TRADE_FIELD_MAP.get(("export", currency))

    if import_field is None or export_field is None:
        return {"error": f"Invalid currency: {currency!r}. "
                         f"Valid: rub, usd, international_rub, international_usd"}

    if direction in ("both", "import"):
        result["imports"] = _sum_trade_values(in_range, import_field)

    if direction in ("both", "export"):
        result["exports"] = _sum_trade_values(in_range, export_field)

    return result


def _parse_building(path: Path) -> dict:
    result = {
        "name": path.stem,
        "type": None,
        "workers_needed": None,
        "production": {},
        "consumption": {},
        "consumption_per_second": {},
    }
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.strip().split()
        if not parts:
            continue
        tok = parts[0]
        if len(parts) == 1 and tok.startswith("$TYPE_"):
            result["type"] = tok[1:]  # e.g. "TYPE_FACTORY"
        elif tok == "$WORKERS_NEEDED" and len(parts) >= 2:
            try:
                result["workers_needed"] = int(float(parts[1]))
            except ValueError:
                pass
        elif tok == "$PRODUCTION" and len(parts) >= 3:
            try:
                result["production"][parts[1]] = float(parts[2])
            except ValueError:
                pass
        elif tok == "$CONSUMPTION" and len(parts) >= 3:
            try:
                result["consumption"][parts[1]] = float(parts[2])
            except ValueError:
                pass
        elif tok == "$CONSUMPTION_PER_SECOND" and len(parts) >= 3:
            try:
                result["consumption_per_second"][parts[1]] = float(parts[2])
            except ValueError:
                pass
    return result


def _load_buildings() -> list[dict]:
    if not BUILDINGS_DIR.exists():
        return []
    return [_parse_building(p) for p in sorted(BUILDINGS_DIR.glob("*.ini"))]


def tool_list_buildings(type: str = None, produces: str = None, consumes: str = None) -> dict:
    buildings = _load_buildings()
    filtered = any([type, produces, consumes])
    results = []
    for b in buildings:
        if type and (b["type"] is None or type.upper() not in b["type"].upper()):
            continue
        if produces and produces.lower() not in b["production"]:
            continue
        if consumes:
            c_lower = consumes.lower()
            if c_lower not in b["consumption"] and c_lower not in b["consumption_per_second"]:
                continue
        if filtered:
            results.append({
                "name": b["name"],
                "type": b["type"],
                "workers": b["workers_needed"],
                "produces": sorted(b["production"].keys()),
                "consumes": sorted(set(b["consumption"]) | set(b["consumption_per_second"])),
            })
        else:
            # Compact format without filters: only buildings with meaningful data
            if not (b["workers_needed"] or b["production"] or b["consumption"]):
                continue
            results.append({"name": b["name"], "type": b["type"], "workers": b["workers_needed"]})
    note = None if filtered else "No filter applied — showing buildings with workers/I/O data only. Use type/produces/consumes filters for full details."
    result = {"count": len(results), "buildings": results}
    if note:
        result["note"] = note
    return result


def tool_get_building_info(name: str) -> dict:
    if not name:
        return {"error": "Missing required argument: name"}
    path = BUILDINGS_DIR / f"{name}.ini"
    if not path.exists():
        # Try case-insensitive search
        matches = [p for p in BUILDINGS_DIR.glob("*.ini") if p.stem.lower() == name.lower()]
        if not matches:
            return {"error": f"Building '{name}' not found. Use list_buildings to browse available buildings."}
        path = matches[0]
    return _parse_building(path)


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
    valid = sorted([r for r in records if r.year > 0], key=lambda r: _date_key(r.year, r.day))
    if not valid:
        return {"error": "No valid records"}

    s_year = start_year if start_year is not None else valid[0].year
    s_day = start_day if start_day is not None else 1
    e_year = end_year if end_year is not None else valid[-1].year
    e_day = end_day if end_day is not None else 365
    range_start = _date_key(s_year, s_day)
    range_end = _date_key(e_year, e_day)

    in_range = [r for r in valid if range_start <= _date_key(r.year, r.day) <= range_end]
    if not in_range:
        return {"error": f"No records found between {s_year}/{s_day} and {e_year}/{e_day}"}

    sections = list(_SPEND_FIELD_MAP) if section == "all" else [section]
    result = {
        "period": {"from": f"{in_range[0].year}/{in_range[0].day}", "to": f"{in_range[-1].year}/{in_range[-1].day}"},
        "records_summed": len(in_range),
    }
    for sec in sections:
        result[sec] = _sum_trade_values(in_range, _SPEND_FIELD_MAP[sec])
    return result


def _build_resource_producer_map() -> dict:
    """Returns {resource: [building_dict, ...]} for all buildings."""
    result = {}
    for b in _load_buildings():
        for resource in b["production"]:
            result.setdefault(resource, []).append(b)
    return result


def _trace_chain(resource: str, producer_map: dict, visited: set, depth: int = 0) -> dict:
    if depth > 6:
        return {"resource": resource, "producers": [], "note": "max depth reached"}
    producers_raw = producer_map.get(resource, [])
    if not producers_raw:
        return {"resource": resource, "producers": []}

    def efficiency(b):
        w = b["workers_needed"] or 1
        return b["production"].get(resource, 0) / w

    best = max(producers_raw, key=efficiency)

    producers_out = []
    for b in producers_raw:
        if b["name"] in visited:
            continue
        visited.add(b["name"])

        all_consumed = {**b["consumption"]}
        for r, rate in b["consumption_per_second"].items():
            all_consumed[r] = all_consumed.get(r, 0) + rate * 3600

        inputs = {}
        for inp_resource, inp_rate in all_consumed.items():
            sub = _trace_chain(inp_resource, producer_map, visited.copy(), depth + 1)
            inputs[inp_resource] = {
                "rate": inp_rate,
                "produced_by": [p["building"] for p in sub["producers"]],
            }

        producers_out.append({
            "building": b["name"],
            "workers": b["workers_needed"],
            "output_rate": b["production"].get(resource, 0),
            "efficiency": round(efficiency(b), 6),
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

    total_input_cost = 0.0
    inputs_detail = {}
    for resource, rate in b["consumption"].items():
        price = prices_rub.get(resource)
        cost = price * rate if price is not None else None
        if cost is not None:
            total_input_cost += cost
        inputs_detail[resource] = {
            "rate": rate,
            "price_rub": price,
            "cost_per_period": round(cost, 4) if cost is not None else "price unknown",
        }
    for resource, rate in b["consumption_per_second"].items():
        price = prices_rub.get(resource)
        key = f"{resource}_per_second" if resource in inputs_detail else resource
        inputs_detail[key] = {
            "rate_per_second": rate,
            "price_rub": price,
            "note": "per-second rate — not included in material cost sum",
        }

    outputs = {}
    for resource, output_rate in b["production"].items():
        if output_rate <= 0:
            continue
        import_price = prices_rub.get(resource)
        mat_cost_per_unit = round(total_input_cost / output_rate, 4)
        margin = round(import_price - mat_cost_per_unit, 4) if import_price is not None else None
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


def tool_get_realtime() -> dict:
    """Read live game state directly from header.bin (updated every autosave)."""
    stats_path = _get_stats_path()
    save_dir = stats_path.parent
    header_path = save_dir / "header.bin"
    workers_path = save_dir / "workers.bin"

    if not header_path.exists():
        return {"error": f"header.bin not found in {save_dir}"}

    data = header_path.read_bytes()
    if len(data) < 0x1a0:
        return {"error": "header.bin too small to parse"}

    usd = struct.unpack_from("<f", data, 0x184)[0]
    rub = struct.unpack_from("<f", data, 0x188)[0]
    day = struct.unpack_from("<I", data, 0x198)[0]
    year = struct.unpack_from("<I", data, 0x19c)[0]

    # Convert 0-indexed day-of-year to day/month
    month_lengths = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    month_names = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    remaining = day
    month = 0
    while month < 11 and remaining >= month_lengths[month]:
        remaining -= month_lengths[month]
        month += 1
    date_str = f"{remaining + 1}. {month_names[month]} {year}"

    result = {
        "save": save_dir.name,
        "date": date_str,
        "year": year,
        "day_of_year": day + 1,
        "money_rub": round(rub, 2),
        "money_usd": round(usd, 2),
        "source": "header.bin",
        "note": "Updated every autosave (~weekly in-game). More current than stats.ini period records.",
    }

    if workers_path.exists():
        wdata = workers_path.read_bytes()
        if len(wdata) >= 4:
            result["total_persons_registered"] = struct.unpack_from("<I", wdata, 0)[0]

    return result


def tool_list_saves() -> dict:
    active_path = _get_stats_path()
    pinned = ACTIVE_SAVE_FILE.read_text(encoding="utf-8").strip() if ACTIVE_SAVE_FILE.exists() else None
    saves = []
    if SAVES_DIR.exists():
        for p in sorted(SAVES_DIR.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
            if p.is_dir() and (p / "stats.ini").exists():
                saves.append({
                    "name": p.name,
                    "active": (p / "stats.ini").resolve() == active_path.resolve(),
                })
    return {"saves": saves, "active_save": active_path.parent.name, "pinned": pinned}


def tool_set_active_save(name: str) -> dict:
    if not name:
        return {"error": "Missing required argument: name"}
    target = SAVES_DIR / name / "stats.ini"
    if not target.exists():
        # Try case-insensitive match
        matches = [p for p in SAVES_DIR.iterdir()
                   if p.is_dir() and p.name.lower() == name.lower() and (p / "stats.ini").exists()]
        if not matches:
            return {"error": f"Save '{name}' not found. Use list_saves to see available saves."}
        name = matches[0].name
    ACTIVE_SAVE_FILE.write_text(name, encoding="utf-8")
    return {"ok": True, "active_save": name}


def tool_get_active_save() -> dict:
    if ACTIVE_SAVE_FILE.exists():
        pinned = ACTIVE_SAVE_FILE.read_text(encoding="utf-8").strip()
        return {"mode": "pinned", "active_save": pinned}
    env_save = os.environ.get("SOVIET_SAVE", "").strip()
    if env_save:
        return {"mode": "env_var", "active_save": env_save}
    active = _get_stats_path().parent.name
    return {"mode": "auto_newest", "active_save": active}


def tool_clear_active_save() -> dict:
    if ACTIVE_SAVE_FILE.exists():
        ACTIVE_SAVE_FILE.unlink()
        return {"ok": True, "mode": "auto_newest", "note": "Pin removed — now following the most recently modified save."}
    return {"ok": True, "note": "No pin was set."}


# ---------------------------------------------------------------------------
# MCP server wiring
# ---------------------------------------------------------------------------

server = Server("soviet-republic")

TOOLS = [
    Tool(
        name="get_stats",
        description=(
            "Get complete snapshot from the latest stats.ini period record: population, year/day, "
            "and economy data. "
            "IMPORTANT: 'economy_rub' and 'economy_usd' contain MARKET PRICES per unit (RUB or USD "
            "per tonne/MWh/etc.) — NOT production quantities, NOT output volumes. "
            "To get actual production quantities use get_spend_period (factory inputs) or "
            "the Resources_Produced data via get_history. "
            "For current date and money balance use get_realtime instead."
        ),
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="get_population",
        description="Get citizen counts and demographics (adults, children, education, unemployment)",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="get_economy",
        description=(
            "Get all resource MARKET PRICES in RUB and USD (price per tonne, MWh, m³, etc.). "
            "These are import/export prices — NOT production quantities or output volumes. "
            "Example: 'steel: 763' means 1 tonne of steel costs 763 RUB on the market."
        ),
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="get_citizen_status",
        description="Get happiness/wellbeing metrics (0-1 scale) for food, water, healthcare, etc.",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="get_history",
        description=(
            "Get time series of a metric across all period records in stats.ini. "
            "For economy metrics (e.g. 'steel', 'food'): returns MARKET PRICE history, not production. "
            "For 'total_population' or citizen fields: returns demographic history."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "metric": {
                    "type": "string",
                    "description": "Metric name: 'total_population', citizen field, or resource name (e.g. 'steel' = price history)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max number of recent records to return. Default 50. Pass 0 for all (may be large).",
                },
            },
        },
    ),
    Tool(
        name="list_buildings",
        description=(
            "List buildings from game definition files, optionally filtered by type, "
            "resource produced, or resource consumed. "
            "With filters: returns name, type, workers, and full I/O resource lists. "
            "Without filters: returns compact list (name, type, workers) of all buildings with workers/I/O data. "
            "Use get_building_info for full production/consumption rates of one building."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "description": "Filter by building type, e.g. 'FACTORY', 'POWERPLANT', 'LIVING', 'STORAGE'. Case-insensitive partial match.",
                },
                "produces": {
                    "type": "string",
                    "description": "Filter to buildings that produce this resource, e.g. 'eletric', 'steel', 'food'.",
                },
                "consumes": {
                    "type": "string",
                    "description": "Filter to buildings that consume this resource, e.g. 'coal', 'eletric', 'water'.",
                },
            },
        },
    ),
    Tool(
        name="get_building_info",
        description=(
            "Get full production/consumption details for a specific building. "
            "Returns workers needed, all produced resources with output rates, "
            "and all consumed resources with input rates. "
            "Use list_buildings first to find the building name."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Building filename without .ini, e.g. 'powerplant_coal', 'alumina_plant'.",
                },
            },
            "required": ["name"],
        },
    ),
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
    Tool(
        name="get_break_even",
        description=(
            "Calculate production profitability for a building. Combines building I/O rates "
            "with current market prices to show material cost per unit of output vs import price. "
            "Positive margin = cheaper to produce than import. "
            "Worker salary (Economy_WorkdayCostRUB) is shown for reference but not included in margin."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "building": {"type": "string", "description": "Building name, e.g. 'powerplant_coal', 'steel_mill'"},
            },
            "required": ["building"],
        },
    ),
    Tool(
        name="get_realtime",
        description=(
            "Get live game state from header.bin: current date, money (RUB + USD). "
            "More current than get_stats — updated every autosave (~weekly in-game). "
            "Use this for current balance and exact date."
        ),
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="list_saves",
        description="List all available save folders and show which one is currently active",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="set_active_save",
        description="Pin a specific save folder as the active save. Use the exact folder name from list_saves.",
        inputSchema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Save folder name, e.g. '22804 - test_claude' or 'autosave1'"},
            },
            "required": ["name"],
        },
    ),
    Tool(
        name="get_active_save",
        description="Show which save is currently active and how it was selected (pinned / env_var / auto_newest)",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="clear_active_save",
        description="Remove the pinned save — reverts to automatically following the most recently modified save",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="get_trade",
        description=(
            "Get CUMULATIVE import/export data since game start. "
            "Each resource entry has 'amount' (physical quantity: tonnes, MWh, m³, etc. — NOT money) "
            "and 'cost' (total currency value spent/earned). "
            "For trade in a specific time period, use get_trade_period instead."
        ),
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="get_trade_period",
        description=(
            "Get import/export totals for a date range by summing all periodic records. "
            "Returns physical quantities (tonnes, MWh, m³, etc.) per resource. "
            "Omit start for 'since game start', omit end for 'until now'. "
            "Note: per-period cost data is not available — use get_trade for cumulative costs."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "start_year": {
                    "type": "integer",
                    "description": "Start year (e.g. 1953). Omit for game start.",
                },
                "start_day": {
                    "type": "integer",
                    "description": "Start day of year (1-365). Default: 1",
                },
                "end_year": {
                    "type": "integer",
                    "description": "End year (e.g. 1954). Omit for latest data.",
                },
                "end_day": {
                    "type": "integer",
                    "description": "End day of year (1-365). Default: 365",
                },
                "direction": {
                    "type": "string",
                    "description": "Trade direction: 'import', 'export', or 'both'. Default: 'both'",
                },
                "currency": {
                    "type": "string",
                    "description": "Currency: 'rub', 'usd', 'international_rub', 'international_usd'. Default: 'rub'",
                },
            },
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
        "get_history": lambda: tool_get_history(arguments.get("metric", "total_population"), arguments.get("limit", 50)),
        "list_buildings": lambda: tool_list_buildings(
            arguments.get("type"),
            arguments.get("produces"),
            arguments.get("consumes"),
        ),
        "get_building_info": lambda: tool_get_building_info(arguments.get("name", "")),
        "get_spend_period": lambda: tool_get_spend_period(
            arguments.get("section", "all"),
            arguments.get("start_year"),
            arguments.get("start_day"),
            arguments.get("end_year"),
            arguments.get("end_day"),
        ),
        "get_production_chain": lambda: tool_get_production_chain(arguments.get("resource", "")),
        "get_break_even": lambda: tool_get_break_even(arguments.get("building", "")),
        "get_realtime": lambda: tool_get_realtime(),
        "list_saves": lambda: tool_list_saves(),
        "set_active_save": lambda: tool_set_active_save(arguments.get("name", "")),
        "get_active_save": lambda: tool_get_active_save(),
        "clear_active_save": lambda: tool_clear_active_save(),
        "get_trade": lambda: tool_get_trade(),
        "get_trade_period": lambda: tool_get_trade_period(
            arguments.get("start_year"),
            arguments.get("start_day"),
            arguments.get("end_year"),
            arguments.get("end_day"),
            arguments.get("direction", "both"),
            arguments.get("currency", "rub"),
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
