# Design: Trade MCP Tools

**Date:** 2026-02-28
**Status:** Approved

## Goal

Expose import/export trade data from `stats.ini` as two new MCP tools: `get_trade` (current snapshot) and `get_trade_history` (time series).

## Data Available in stats.ini

Per `$STAT_RECORD`, the following sections contain trade data (indented `resource amount value` lines):

- `$Resources_ImportRUB` / `$Resources_ExportRUB`
- `$Resources_ImportUSD` / `$Resources_ExportUSD`
- `$Resources_ImportInternationalRUB` / `$Resources_ExportInternationalRUB`
- `$Resources_ImportInternationalUSD` / `$Resources_ExportInternationalUSD`
- `$Vehicles_ImportRUB` / `$Vehicles_ExportRUB` / `$Vehicles_ImportUSD` / `$Vehicles_ExportUSD` (scalar)

## Changes

### 1. `parser.py` — StatRecord

Add new fields:
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

Parse all `$Resources_Import/Export*` sections using the same indented-line logic as `$Economy_PurchaseCostRUB`. Parse `$Vehicles_Import/ExportRUB/USD` as scalars into `trade_vehicles`.

### 2. `mcp_server.py` — Tool: `get_trade`

Returns latest record's trade data:
```json
{
  "year": 1950, "day": 3,
  "imports": {
    "rub": {"fuel": 14.0},
    "usd": {},
    "international_rub": {},
    "international_usd": {},
    "vehicles_rub": 12223.9,
    "vehicles_usd": 0.0
  },
  "exports": {
    "rub": {},
    "usd": {},
    "international_rub": {},
    "international_usd": {},
    "vehicles_rub": 0.0,
    "vehicles_usd": 0.0
  }
}
```

### 3. `mcp_server.py` — Tool: `get_trade_history`

Parameters:
- `resource: str` — e.g. `"fuel"`, `"steel"`
- `currency: str` — `"rub"` or `"usd"`
- `direction: str` — `"import"` or `"export"`

Returns time series across all records:
```json
{
  "resource": "fuel", "currency": "rub", "direction": "import",
  "data": [
    {"index": 1, "year": 1950, "day": 3, "value": 14.0},
    ...
  ]
}
```

## Testing

Add tests to `test_parser.py` (parse trade fields) and `test_mcp.py` (tool output shape).
