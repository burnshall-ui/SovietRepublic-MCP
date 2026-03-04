# Building Analysis Features — Design

## Features

### 1. `get_production_chain(resource)`
Traces recursively through building definitions to find all production paths for a resource.

- For each resource: all buildings that produce it, with their input requirements
- Recursion stops when an input has no known producer (= raw material / import)
- Cycle protection via visited set
- Efficiency metric: output_rate / workers_needed → highest = "recommended"
- `consumption_per_second` rates normalised to same unit as `consumption` (×3600)

### 2. `get_break_even(building)`
Combines building I/O with current market prices from `get_economy`.

For each produced resource:
- Material cost per unit output = `sum(input_rate × input_price_rub) / output_rate`
- Import price of output = `economy_rub[resource]`
- Margin = import price − material cost per unit
- Worker cost from `Economy_WorkdayCostRUB` scalar (noted as unavailable if 0)

### 3. Parser extension + `get_spend_period()`
Add four new fields to `StatRecord`:
- `spend_constructions`, `spend_factories`, `spend_shops`, `spend_vehicles`

Section mapping in parser (same format as trade sections):
- `$Resources_SpendConstructions` → `spend_constructions`
- `$Resources_SpendFactories` → `spend_factories`
- `$Resources_SpendShops` → `spend_shops`
- `$Resources_SpendVehicles` → `spend_vehicles`

New tool `get_spend_period(section, start_year?, start_day?, end_year?, end_day?)`:
- Same delta logic as `get_trade_period`
- `section`: "constructions", "factories", "shops", "vehicles", or "all"
- Returns resource quantities and costs spent in the period

## Files Changed
- `parser.py` — add 4 spend fields to StatRecord + section mapping
- `mcp_server.py` — add chain/break-even helpers + 3 new tools + dispatch entries
- `README.md` — update tool count and table
- `MEMORY.md` — update tool list
