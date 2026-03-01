# Soviet Republic Live-Dashboard – Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** A Python process that reads Workers & Resources: Soviet Republic autosave data and serves a live dashboard on localhost:8765, with an Ollama chat interface and an MCP server for Claude Code integration.

**Architecture:** Single FastAPI process with a background file-watcher thread that re-parses `stats.ini` on every autosave, broadcasts updates via WebSocket, and exposes game data via REST API, Ollama-proxied chat, and MCP stdio mode.

**Tech Stack:** Python 3.13, FastAPI, uvicorn, watchdog, httpx, mcp[cli], Chart.js (CDN), pytest, pytest-asyncio

---

## Project Root

All files live in:
```
E:/SteamLibrary/steamapps/common/SovietRepublic/soviet_dashboard/
```

Game autosave data is at (relative to project root, one level up):
```
../media_soviet/save/autosave1/stats.ini
```

---

## Task 1: Project Scaffold + Dependencies

**Files:**
- Create: `requirements.txt`
- Create: `tests/__init__.py`
- Create: `tests/fixtures/sample_stats.ini`

**Step 1: Create requirements.txt**

```
fastapi==0.115.0
uvicorn[standard]==0.30.0
watchdog==4.0.1
httpx==0.27.0
mcp[cli]==1.3.0
pytest==8.3.0
pytest-asyncio==0.23.0
```

**Step 2: Install dependencies**

Run from `soviet_dashboard/`:
```bash
pip install -r requirements.txt
```
Expected: All packages install without error.

**Step 3: Create test fixture `tests/fixtures/sample_stats.ini`**

This is a minimal valid stats.ini for tests (two STAT_RECORDs):

```ini
$CRIME_SENTENCES 10 25 60
====================================================================

$STAT_RECORD 0
====================================================================
====================================================================
$DATE_DAY 364
$DATE_YEAR 1919

Economy
-------------------------------------------------

$Economy_PurchaseCostRUB
-------------
   steel 113.013054 1.050000
   coal 5.335760 1.050000
   food 42.000000 1.050000

$Economy_PurchaseCostUSD
-------------
   steel 134.732101 1.050000
   coal 5.940175 1.050000
   food 55.722630 1.050000

$Economy_DeliveryCostRUB 1.400000
$Economy_WorkdayCostRUB 3.150000

Citizens
$Citizens_Born 0
$Citizens_Dead 0
$Citizens_Escaped 0
$Citizens_ImigrantSoviet 5
$Citizens_Status 0 0.723101
$Citizens_Status 1 0.701264
$Citizens_Status 2 0.850604
$Citizens_Status 3 0.349523
$Citizens_Status 4 0.208374
$Citizens_Status 5 0.276013
$Citizens_Status 6 0.273940
$Citizens_Status 7 0.715070
$Citizens_Status 8 0.400279
$Citizens_AverageProductivity 0.658932
$Citizens_AverageLifespan 78.595711
$Citizens_AverageAge 31.727852
$Citizens_SmallChilds 271
$Citizens_MediumChilds 688
$Citizens_Adults 2798
$Citizens_Unemployed 2798
$Citizens_NoEducation 959
$Citizens_BasicEducationNum 2563
$Citizens_HighEducationNum 235
$Citizens_CarOwners 0

$STAT_RECORD 1
====================================================================
====================================================================
$DATE_DAY 3
$DATE_YEAR 1920

Economy
-------------------------------------------------

$Economy_PurchaseCostRUB
-------------
   steel 120.000000 1.050000
   coal 6.000000 1.050000
   food 44.000000 1.050000

$Economy_PurchaseCostUSD
-------------
   steel 140.000000 1.050000
   coal 6.500000 1.050000
   food 57.000000 1.050000

$Economy_DeliveryCostRUB 1.400000
$Economy_WorkdayCostRUB 3.150000

Citizens
$Citizens_Born 3
$Citizens_Dead 1
$Citizens_Escaped 0
$Citizens_ImigrantSoviet 0
$Citizens_Status 0 0.750000
$Citizens_Status 1 0.720000
$Citizens_Status 2 0.860000
$Citizens_Status 3 0.380000
$Citizens_Status 4 0.220000
$Citizens_Status 5 0.290000
$Citizens_Status 6 0.280000
$Citizens_Status 7 0.730000
$Citizens_Status 8 0.410000
$Citizens_AverageProductivity 0.670000
$Citizens_AverageLifespan 79.000000
$Citizens_AverageAge 32.000000
$Citizens_SmallChilds 274
$Citizens_MediumChilds 690
$Citizens_Adults 2800
$Citizens_Unemployed 2750
$Citizens_NoEducation 950
$Citizens_BasicEducationNum 2570
$Citizens_HighEducationNum 240
$Citizens_CarOwners 2
```

**Step 4: Create `tests/__init__.py`** (empty file)

**Step 5: Commit**

```bash
git add requirements.txt tests/
git commit -m "chore: scaffold project and add test fixture"
```

---

## Task 2: Stats Parser

**Files:**
- Create: `parser.py`
- Create: `tests/test_parser.py`

### Stats.ini Format Reference

- File has sections separated by `$STAT_RECORD N` markers
- Each section starts with `$DATE_DAY N` and `$DATE_YEAR N`
- Economy subsections: `$Economy_PurchaseCostRUB` followed by indented lines `   resource price multiplier`
- Scalar economy values: `$Economy_DeliveryCostRUB 1.400000`
- Citizens: lines like `$Citizens_Born 5`, `$Citizens_Status 0 0.723101`
- Skip: lines with `=` separators, lines with only whitespace, lines starting with text labels (e.g., "Economy", "Citizens")

### Step 1: Write failing tests

Create `tests/test_parser.py`:

```python
import pytest
from pathlib import Path
from parser import parse_stats_file, StatRecord

FIXTURE = Path(__file__).parent / "fixtures" / "sample_stats.ini"


def test_returns_list_of_records():
    records = parse_stats_file(FIXTURE)
    assert len(records) == 2


def test_first_record_date():
    records = parse_stats_file(FIXTURE)
    assert records[0].year == 1919
    assert records[0].day == 364


def test_second_record_date():
    records = parse_stats_file(FIXTURE)
    assert records[1].year == 1920
    assert records[1].day == 3


def test_economy_rub_parsed():
    records = parse_stats_file(FIXTURE)
    assert records[0].economy_rub["steel"] == pytest.approx(113.013054)
    assert records[0].economy_rub["coal"] == pytest.approx(5.335760)


def test_economy_usd_parsed():
    records = parse_stats_file(FIXTURE)
    assert records[0].economy_usd["steel"] == pytest.approx(134.732101)


def test_citizens_scalars():
    records = parse_stats_file(FIXTURE)
    r = records[0]
    assert r.citizens["born"] == 0
    assert r.citizens["immigrants_soviet"] == 5
    assert r.citizens["adults"] == 2798
    assert r.citizens["unemployed"] == 2798
    assert r.citizens["small_childs"] == 271


def test_citizens_floats():
    records = parse_stats_file(FIXTURE)
    r = records[0]
    assert r.citizens["avg_productivity"] == pytest.approx(0.658932)
    assert r.citizens["avg_age"] == pytest.approx(31.727852)


def test_citizen_status_list():
    records = parse_stats_file(FIXTURE)
    r = records[0]
    assert len(r.citizen_status) == 9
    assert r.citizen_status[0] == pytest.approx(0.723101)
    assert r.citizen_status[2] == pytest.approx(0.850604)


def test_total_population():
    records = parse_stats_file(FIXTURE)
    r = records[0]
    # small + medium + adults
    assert r.total_population == 271 + 688 + 2798
```

**Step 2: Run to verify tests fail**

```bash
cd soviet_dashboard
pytest tests/test_parser.py -v
```
Expected: `ImportError: No module named 'parser'` or similar — all FAIL.

**Step 3: Implement `parser.py`**

```python
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class StatRecord:
    index: int
    year: int = 0
    day: int = 0
    economy_rub: dict = field(default_factory=dict)
    economy_usd: dict = field(default_factory=dict)
    economy_scalars: dict = field(default_factory=dict)
    citizens: dict = field(default_factory=dict)
    citizen_status: list = field(default_factory=list)

    @property
    def total_population(self) -> int:
        return (
            self.citizens.get("small_childs", 0)
            + self.citizens.get("medium_childs", 0)
            + self.citizens.get("adults", 0)
        )


def parse_stats_file(path: Path) -> list[StatRecord]:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    records: list[StatRecord] = []
    current: Optional[StatRecord] = None
    current_economy_section: Optional[str] = None  # "rub" or "usd"

    for line in lines:
        stripped = line.strip()

        # Skip separators and empty lines
        if not stripped or stripped.startswith("=") or stripped.startswith("-"):
            continue

        # New record marker
        if stripped.startswith("$STAT_RECORD "):
            idx = int(stripped.split()[1])
            current = StatRecord(index=idx)
            records.append(current)
            current_economy_section = None
            continue

        if current is None:
            continue

        # Date fields
        if stripped.startswith("$DATE_YEAR "):
            current.year = int(stripped.split()[1])
            continue
        if stripped.startswith("$DATE_DAY "):
            current.day = int(stripped.split()[1])
            continue

        # Economy section headers
        if stripped == "$Economy_PurchaseCostRUB":
            current_economy_section = "rub"
            continue
        if stripped == "$Economy_PurchaseCostUSD":
            current_economy_section = "usd"
            continue
        if stripped.startswith("$Economy_") and not stripped.startswith("$Economy_Purchase"):
            # Scalar economy value: $Economy_DeliveryCostRUB 1.400000
            parts = stripped.split()
            if len(parts) == 2:
                key = parts[0][1:]  # strip leading $
                try:
                    current.economy_scalars[key] = float(parts[1])
                except ValueError:
                    pass
            current_economy_section = None
            continue

        # Economy resource line (indented): "   steel 113.013054 1.050000"
        if line.startswith("   ") and current_economy_section:
            parts = stripped.split()
            if len(parts) >= 2:
                name = parts[0]
                try:
                    price = float(parts[1])
                    if current_economy_section == "rub":
                        current.economy_rub[name] = price
                    elif current_economy_section == "usd":
                        current.economy_usd[name] = price
                except ValueError:
                    pass
            continue

        # Non-indented non-$ lines reset economy section (e.g. "Citizens", "Economy")
        if not stripped.startswith("$"):
            current_economy_section = None
            continue

        # Citizens scalar fields
        citizen_int_map = {
            "$Citizens_Born": "born",
            "$Citizens_Dead": "dead",
            "$Citizens_Escaped": "escaped",
            "$Citizens_ImigrantSoviet": "immigrants_soviet",
            "$Citizens_ImigrantAfrica": "immigrants_africa",
            "$Citizens_SmallChilds": "small_childs",
            "$Citizens_MediumChilds": "medium_childs",
            "$Citizens_AdultsParent": "adults_parent",
            "$Citizens_Adults": "adults",
            "$Citizens_Unemployed": "unemployed",
            "$Citizens_NoEducation": "no_education",
            "$Citizens_BasicEducationNum": "basic_education",
            "$Citizens_HighEducationNum": "high_education",
            "$Citizens_EletronicNone": "electronics_none",
            "$Citizens_EletrinicRadio": "electronics_radio",
            "$Citizens_EletronicTV": "electronics_tv",
            "$Citizens_EletronicComputer": "electronics_computer",
            "$Citizens_CarOwners": "car_owners",
        }
        citizen_float_map = {
            "$Citizens_AverageProductivity": "avg_productivity",
            "$Citizens_AverageLifespan": "avg_lifespan",
            "$Citizens_AverageAge": "avg_age",
        }

        key_part = stripped.split()[0]
        parts = stripped.split()

        if key_part in citizen_int_map and len(parts) >= 2:
            try:
                current.citizens[citizen_int_map[key_part]] = int(parts[1])
            except ValueError:
                pass
            continue

        if key_part in citizen_float_map and len(parts) >= 2:
            try:
                current.citizens[citizen_float_map[key_part]] = float(parts[1])
            except ValueError:
                pass
            continue

        # Citizen status: $Citizens_Status 0 0.723101
        if stripped.startswith("$Citizens_Status ") and len(parts) == 3:
            try:
                idx = int(parts[1])
                val = float(parts[2])
                # Ensure list is long enough
                while len(current.citizen_status) <= idx:
                    current.citizen_status.append(0.0)
                current.citizen_status[idx] = val
            except ValueError:
                pass
            continue

    return records
```

**Step 4: Run tests**

```bash
pytest tests/test_parser.py -v
```
Expected: All 9 tests PASS.

**Step 5: Commit**

```bash
git add parser.py tests/test_parser.py
git commit -m "feat: implement stats.ini parser"
```

---

## Task 3: In-Memory State + Watcher

**Files:**
- Create: `state.py`
- Create: `watcher.py`
- Create: `tests/test_watcher.py`

**Step 1: Create `state.py`**

```python
"""Shared in-memory game state, updated by watcher, read by API and MCP."""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Callable
from parser import StatRecord

# Path to latest autosave stats.ini (relative to soviet_dashboard/)
STATS_PATH = Path(__file__).parent.parent / "media_soviet" / "save" / "autosave1" / "stats.ini"


@dataclass
class GameState:
    records: list[StatRecord] = field(default_factory=list)
    last_updated: Optional[str] = None  # ISO timestamp string
    error: Optional[str] = None

    @property
    def latest(self) -> Optional[StatRecord]:
        return self.records[-1] if self.records else None

    @property
    def history(self) -> list[StatRecord]:
        return self.records


# Singleton — imported by server.py and mcp_server.py
game_state = GameState()

# Callbacks registered by WebSocket server to broadcast updates
_on_update_callbacks: list[Callable] = []


def register_update_callback(cb: Callable):
    _on_update_callbacks.append(cb)


def notify_update():
    for cb in _on_update_callbacks:
        cb()
```

**Step 2: Write failing test for watcher**

Create `tests/test_watcher.py`:

```python
import time
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
from watcher import StatsWatcher


FIXTURE = Path(__file__).parent / "fixtures" / "sample_stats.ini"


def test_initial_load_parses_records(tmp_path):
    """Watcher should parse file on first load."""
    stats_file = tmp_path / "stats.ini"
    shutil.copy(FIXTURE, stats_file)

    from state import GameState
    gs = GameState()

    watcher = StatsWatcher(stats_path=stats_file, game_state=gs)
    watcher.load_and_update()

    assert len(gs.records) == 2
    assert gs.latest.year == 1920


def test_update_callback_called(tmp_path):
    """Watcher should call registered callbacks after load."""
    stats_file = tmp_path / "stats.ini"
    shutil.copy(FIXTURE, stats_file)

    from state import GameState
    gs = GameState()
    called = []

    watcher = StatsWatcher(stats_path=stats_file, game_state=gs, on_update=lambda: called.append(1))
    watcher.load_and_update()

    assert len(called) == 1
```

**Step 3: Run to verify tests fail**

```bash
pytest tests/test_watcher.py -v
```
Expected: `ImportError: No module named 'watcher'` — FAIL.

**Step 4: Implement `watcher.py`**

```python
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from watchdog.events import FileSystemEventHandler, FileModifiedEvent
from watchdog.observers import Observer

from parser import parse_stats_file

logger = logging.getLogger(__name__)


class StatsWatcher:
    def __init__(self, stats_path: Path, game_state, on_update: Optional[Callable] = None):
        self.stats_path = stats_path
        self.game_state = game_state
        self.on_update = on_update
        self._observer: Optional[Observer] = None

    def load_and_update(self):
        """Parse the stats file and update game_state. Safe to call from any thread."""
        try:
            records = parse_stats_file(self.stats_path)
            self.game_state.records = records
            self.game_state.last_updated = datetime.now(timezone.utc).isoformat()
            self.game_state.error = None
            logger.info(f"Loaded {len(records)} records from {self.stats_path}")
        except Exception as e:
            self.game_state.error = str(e)
            logger.error(f"Failed to parse {self.stats_path}: {e}")

        if self.on_update:
            self.on_update()

    def start(self):
        """Load once, then watch for file changes."""
        self.load_and_update()

        handler = _ChangeHandler(self.stats_path, self.load_and_update)
        self._observer = Observer()
        self._observer.schedule(handler, str(self.stats_path.parent), recursive=False)
        self._observer.start()
        logger.info(f"Watching {self.stats_path}")

    def stop(self):
        if self._observer:
            self._observer.stop()
            self._observer.join()


class _ChangeHandler(FileSystemEventHandler):
    def __init__(self, target_path: Path, callback: Callable):
        self.target_path = target_path
        self.callback = callback

    def on_modified(self, event):
        if not event.is_directory and Path(event.src_path) == self.target_path:
            self.callback()
```

**Step 5: Run tests**

```bash
pytest tests/test_watcher.py -v
```
Expected: Both tests PASS.

**Step 6: Commit**

```bash
git add state.py watcher.py tests/test_watcher.py
git commit -m "feat: add game state and file watcher"
```

---

## Task 4: FastAPI Server + WebSocket

**Files:**
- Create: `server.py`
- Create: `tests/test_server.py`

**Step 1: Write failing tests**

Create `tests/test_server.py`:

```python
import pytest
import shutil
from pathlib import Path
from fastapi.testclient import TestClient

FIXTURE = Path(__file__).parent / "fixtures" / "sample_stats.ini"


@pytest.fixture(autouse=True)
def load_fixture_data():
    """Pre-load fixture data into game_state before each test."""
    from state import game_state
    from parser import parse_stats_file
    game_state.records = parse_stats_file(FIXTURE)
    game_state.last_updated = "2026-02-28T12:00:00+00:00"
    game_state.error = None


@pytest.fixture
def client():
    from server import app
    return TestClient(app)


def test_stats_endpoint_returns_200(client):
    r = client.get("/api/stats")
    assert r.status_code == 200


def test_stats_has_population(client):
    r = client.get("/api/stats")
    data = r.json()
    assert "population" in data
    assert data["population"]["adults"] == 2800  # latest record (record 1)


def test_stats_has_economy(client):
    r = client.get("/api/stats")
    data = r.json()
    assert "economy_rub" in data
    assert data["economy_rub"]["steel"] == pytest.approx(120.0)


def test_stats_has_citizen_status(client):
    r = client.get("/api/stats")
    data = r.json()
    assert "citizen_status" in data
    assert len(data["citizen_status"]) == 9


def test_history_endpoint(client):
    r = client.get("/api/history")
    data = r.json()
    assert "records" in data
    assert len(data["records"]) == 2
    assert data["records"][0]["year"] == 1919


def test_models_endpoint(client):
    r = client.get("/api/models")
    assert r.status_code == 200
    assert "models" in r.json()
```

**Step 2: Run to verify tests fail**

```bash
pytest tests/test_server.py -v
```
Expected: `ImportError: No module named 'server'` — FAIL.

**Step 3: Implement `server.py`**

```python
import asyncio
import json
import logging
from typing import Any

import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from state import game_state, register_update_callback

logger = logging.getLogger(__name__)
app = FastAPI(title="Soviet Republic Dashboard")

# Serve static files (index.html)
_static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

# Active WebSocket connections
_ws_clients: list[WebSocket] = []

OLLAMA_BASE = "http://localhost:11434"


@app.get("/")
async def index():
    html = (_static_dir / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(html)


@app.get("/api/stats")
async def get_stats() -> dict:
    rec = game_state.latest
    if rec is None:
        return {"error": "No data loaded yet"}
    return {
        "year": rec.year,
        "day": rec.day,
        "last_updated": game_state.last_updated,
        "total_population": rec.total_population,
        "population": rec.citizens,
        "citizen_status": rec.citizen_status,
        "economy_rub": rec.economy_rub,
        "economy_usd": rec.economy_usd,
        "economy_scalars": rec.economy_scalars,
    }


@app.get("/api/history")
async def get_history() -> dict:
    records = []
    for r in game_state.history:
        records.append({
            "index": r.index,
            "year": r.year,
            "day": r.day,
            "total_population": r.total_population,
            "economy_rub": r.economy_rub,
        })
    return {"records": records}


@app.get("/api/models")
async def get_models() -> dict:
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{OLLAMA_BASE}/api/tags")
            data = resp.json()
            models = [m["name"] for m in data.get("models", [])]
            return {"models": models}
    except Exception:
        return {"models": [], "error": "Ollama not reachable"}


@app.post("/api/chat")
async def chat(payload: dict) -> dict:
    message: str = payload.get("message", "")
    model: str = payload.get("model", "llama3")

    rec = game_state.latest
    context_summary = ""
    if rec:
        context_summary = (
            f"Spieljahr: {rec.year}, Tag: {rec.day}. "
            f"Bevölkerung: {rec.total_population} (Erwachsene: {rec.citizens.get('adults', 0)}, "
            f"Arbeitslose: {rec.citizens.get('unemployed', 0)}). "
            f"Bildung: Keine={rec.citizens.get('no_education', 0)}, "
            f"Basis={rec.citizens.get('basic_education', 0)}, "
            f"Höher={rec.citizens.get('high_education', 0)}. "
            f"Produktivität: {rec.citizens.get('avg_productivity', 0):.1%}. "
            f"Stahl (RUB): {rec.economy_rub.get('steel', 0):.0f}, "
            f"Kohle: {rec.economy_rub.get('coal', 0):.0f}, "
            f"Nahrung: {rec.economy_rub.get('food', 0):.0f}."
        )

    system_prompt = (
        "Du bist Genosse Berater, ein erfahrener sowjetischer Wirtschaftsplaner. "
        "Du analysierst die Spielstatistiken von 'Workers & Resources: Soviet Republic' "
        "und gibst dem Spieler konkrete, hilfreiche Ratschläge auf Deutsch. "
        "Sei präzise, verwende die echten Zahlen aus den Daten. "
        f"Aktuelle Spieldaten: {context_summary}"
    )

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{OLLAMA_BASE}/api/chat",
                json={
                    "model": model,
                    "stream": False,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": message},
                    ],
                },
            )
            data = resp.json()
            answer = data.get("message", {}).get("content", "Keine Antwort erhalten.")
            return {"response": answer}
    except Exception as e:
        return {"response": f"Fehler: Ollama nicht erreichbar ({e})"}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    _ws_clients.append(ws)
    try:
        while True:
            await ws.receive_text()  # keep alive
    except WebSocketDisconnect:
        _ws_clients.remove(ws)


async def _broadcast_update():
    """Called by watcher when stats.ini changes."""
    import asyncio
    data = json.dumps({"type": "update"})
    dead = []
    for ws in _ws_clients:
        try:
            await ws.send_text(data)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _ws_clients.remove(ws)


def on_stats_update():
    """Sync callback — schedules async broadcast."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(_broadcast_update(), loop)
    except RuntimeError:
        pass


register_update_callback(on_stats_update)
```

**Step 4: Run tests**

```bash
pytest tests/test_server.py -v
```
Expected: All 6 tests PASS. (models test may show empty list if Ollama not running — that's fine.)

**Step 5: Commit**

```bash
git add server.py tests/test_server.py
git commit -m "feat: add FastAPI server with REST and WebSocket endpoints"
```

---

## Task 5: MCP Server

**Files:**
- Create: `mcp_server.py`
- Create: `tests/test_mcp.py`

**Step 1: Write failing tests**

Create `tests/test_mcp.py`:

```python
import pytest
import shutil
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "sample_stats.ini"


@pytest.fixture(autouse=True)
def load_fixture_data():
    from state import game_state
    from parser import parse_stats_file
    game_state.records = parse_stats_file(FIXTURE)
    game_state.last_updated = "2026-02-28T12:00:00+00:00"


def test_get_stats_returns_dict():
    from mcp_server import tool_get_stats
    result = tool_get_stats()
    assert isinstance(result, dict)
    assert result["year"] == 1920


def test_get_population_returns_dict():
    from mcp_server import tool_get_population
    result = tool_get_population()
    assert result["total_population"] == 274 + 690 + 2800  # record 1 values
    assert result["adults"] == 2800


def test_get_economy_returns_dict():
    from mcp_server import tool_get_economy
    result = tool_get_economy()
    assert "steel" in result["rub"]
    assert result["rub"]["steel"] == pytest.approx(120.0)


def test_get_citizen_status_returns_list():
    from mcp_server import tool_get_citizen_status
    result = tool_get_citizen_status()
    assert len(result["status"]) == 9
    assert result["status"][0] == pytest.approx(0.75)


def test_get_history_returns_records():
    from mcp_server import tool_get_history
    result = tool_get_history(metric="total_population")
    assert len(result["data"]) == 2
    assert result["data"][0]["year"] == 1919


def test_list_saves_returns_list():
    from mcp_server import tool_list_saves
    result = tool_list_saves()
    assert isinstance(result["saves"], list)
```

**Step 2: Run to verify tests fail**

```bash
pytest tests/test_mcp.py -v
```
Expected: `ImportError: No module named 'mcp_server'` — FAIL.

**Step 3: Implement `mcp_server.py`**

```python
"""
MCP server exposing Soviet Republic game data as tools.

Run standalone: python main.py --mcp
"""
import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from state import game_state

logger = logging.getLogger(__name__)

SAVES_DIR = Path(__file__).parent.parent / "media_soviet" / "save"

# ---------------------------------------------------------------------------
# Pure tool functions (also used by tests directly)
# ---------------------------------------------------------------------------

def tool_get_stats() -> dict:
    rec = game_state.latest
    if rec is None:
        return {"error": "No data loaded"}
    return {
        "year": rec.year,
        "day": rec.day,
        "last_updated": game_state.last_updated,
        "total_population": rec.total_population,
        "population": rec.citizens,
        "citizen_status": rec.citizen_status,
        "economy_rub": rec.economy_rub,
        "economy_usd": rec.economy_usd,
    }


def tool_get_population() -> dict:
    rec = game_state.latest
    if rec is None:
        return {"error": "No data loaded"}
    return {
        "total_population": rec.total_population,
        **rec.citizens,
    }


def tool_get_economy() -> dict:
    rec = game_state.latest
    if rec is None:
        return {"error": "No data loaded"}
    return {
        "rub": rec.economy_rub,
        "usd": rec.economy_usd,
        "scalars": rec.economy_scalars,
    }


def tool_get_citizen_status() -> dict:
    STATUS_LABELS = [
        "food_supply", "water_supply", "healthcare", "education",
        "entertainment", "retail_goods", "housing", "public_transport", "safety",
    ]
    rec = game_state.latest
    if rec is None:
        return {"error": "No data loaded"}
    labeled = {STATUS_LABELS[i]: v for i, v in enumerate(rec.citizen_status) if i < len(STATUS_LABELS)}
    return {"status": rec.citizen_status, "labeled": labeled}


def tool_get_history(metric: str = "total_population") -> dict:
    data = []
    for r in game_state.history:
        if metric == "total_population":
            val = r.total_population
        elif metric in r.citizens:
            val = r.citizens[metric]
        elif metric in r.economy_rub:
            val = r.economy_rub[metric]
        else:
            val = None
        data.append({"index": r.index, "year": r.year, "day": r.day, "value": val})
    return {"metric": metric, "data": data}


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
        description="Get happiness/wellbeing metrics (0–1 scale) for food, water, healthcare, etc.",
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
    }
    fn = dispatch.get(name)
    if fn is None:
        result = {"error": f"Unknown tool: {name}"}
    else:
        result = fn()
    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]


async def run_mcp():
    """Entry point when run with --mcp flag."""
    from parser import parse_stats_file
    from state import STATS_PATH
    # Pre-load data before MCP session starts
    if STATS_PATH.exists():
        game_state.records = parse_stats_file(STATS_PATH)
        logger.info(f"MCP: loaded {len(game_state.records)} records")

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )
```

**Step 4: Run tests**

```bash
pytest tests/test_mcp.py -v
```
Expected: All 6 tests PASS.

**Step 5: Commit**

```bash
git add mcp_server.py tests/test_mcp.py
git commit -m "feat: add MCP server with game data tools"
```

---

## Task 6: Ollama Chat + Main Entry Point

**Files:**
- Create: `main.py`

**Step 1: Create `main.py`**

```python
"""
Entry point for Soviet Republic Dashboard.

Usage:
  python main.py          # Start web dashboard on http://localhost:8765
  python main.py --mcp    # Run as MCP stdio server (for Claude Code)
"""
import asyncio
import logging
import sys
import threading

import uvicorn

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def run_web():
    """Start FastAPI + file watcher."""
    from state import game_state, STATS_PATH
    from watcher import StatsWatcher
    from server import on_stats_update

    watcher = StatsWatcher(
        stats_path=STATS_PATH,
        game_state=game_state,
        on_update=on_stats_update,
    )
    watcher.start()

    logger.info(f"Dashboard: http://localhost:8765")
    uvicorn.run("server:app", host="0.0.0.0", port=8765, log_level="warning")

    watcher.stop()


def run_mcp():
    """Run as MCP stdio server."""
    from mcp_server import run_mcp as _run
    asyncio.run(_run())


if __name__ == "__main__":
    if "--mcp" in sys.argv:
        run_mcp()
    else:
        run_web()
```

**Step 2: Test manually**

```bash
python main.py
```
Expected output:
```
INFO: Dashboard: http://localhost:8765
INFO: Loaded 64 records from .../stats.ini
```

Open `http://localhost:8765` in browser — should return empty page (no HTML yet).

**Step 3: Commit**

```bash
git add main.py
git commit -m "feat: add main entry point with web/mcp modes"
```

---

## Task 7: Dashboard HTML

**Files:**
- Create: `static/index.html`

**Step 1: Create `static/` directory**

```bash
mkdir -p soviet_dashboard/static
```

**Step 2: Create `static/index.html`**

```html
<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Soviet Republic – Genosse Berater</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
  <style>
    :root {
      --bg: #0d0d0d;
      --surface: #1a1a1a;
      --surface2: #222;
      --red: #cc2200;
      --red-light: #ff4422;
      --gold: #c8a84b;
      --text: #e8e0d0;
      --text-dim: #888;
      --border: #333;
      --green: #4caf50;
      --yellow: #ffc107;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: var(--bg);
      color: var(--text);
      font-family: 'Courier New', monospace;
      font-size: 13px;
      min-height: 100vh;
    }
    header {
      background: var(--surface);
      border-bottom: 2px solid var(--red);
      padding: 10px 20px;
      display: flex;
      align-items: center;
      gap: 20px;
    }
    header h1 {
      color: var(--red-light);
      font-size: 18px;
      letter-spacing: 2px;
      text-transform: uppercase;
    }
    #status {
      margin-left: auto;
      display: flex;
      align-items: center;
      gap: 8px;
      color: var(--text-dim);
      font-size: 11px;
    }
    #ws-dot {
      width: 8px; height: 8px;
      border-radius: 50%;
      background: #555;
      display: inline-block;
    }
    #ws-dot.connected { background: var(--green); }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
      gap: 14px;
      padding: 14px;
    }
    .card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 4px;
      padding: 14px;
    }
    .card h2 {
      color: var(--gold);
      font-size: 11px;
      letter-spacing: 2px;
      text-transform: uppercase;
      margin-bottom: 12px;
      border-bottom: 1px solid var(--border);
      padding-bottom: 6px;
    }
    .tiles {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 8px;
    }
    .tile {
      background: var(--surface2);
      border: 1px solid var(--border);
      border-radius: 3px;
      padding: 8px;
      text-align: center;
    }
    .tile .val { font-size: 22px; color: var(--red-light); font-weight: bold; }
    .tile .lbl { font-size: 10px; color: var(--text-dim); margin-top: 2px; text-transform: uppercase; }
    .chart-container { position: relative; height: 200px; }
    table { width: 100%; border-collapse: collapse; font-size: 12px; }
    th { color: var(--text-dim); text-align: left; padding: 4px 6px; font-weight: normal; border-bottom: 1px solid var(--border); }
    td { padding: 3px 6px; border-bottom: 1px solid #1e1e1e; }
    tr:hover td { background: #1e1e1e; }
    .price-high { color: #ff6644; }
    .price-mid  { color: var(--gold); }
    .price-low  { color: var(--green); }
    .chat-section {
      grid-column: 1 / -1;
    }
    #chat-messages {
      height: 200px;
      overflow-y: auto;
      background: var(--surface2);
      border: 1px solid var(--border);
      border-radius: 3px;
      padding: 10px;
      margin-bottom: 8px;
      font-size: 12px;
      line-height: 1.5;
    }
    .msg-user { color: var(--gold); margin-bottom: 6px; }
    .msg-bot  { color: var(--text); margin-bottom: 10px; padding-left: 12px; border-left: 2px solid var(--red); }
    .msg-bot .speaker { color: var(--red-light); font-size: 10px; }
    #chat-controls { display: flex; gap: 8px; }
    #chat-input {
      flex: 1;
      background: var(--surface2);
      border: 1px solid var(--border);
      color: var(--text);
      padding: 8px;
      font-family: inherit;
      font-size: 12px;
      border-radius: 3px;
    }
    #chat-input:focus { outline: none; border-color: var(--red); }
    #model-select {
      background: var(--surface2);
      border: 1px solid var(--border);
      color: var(--text);
      padding: 6px;
      font-family: inherit;
      font-size: 12px;
      border-radius: 3px;
    }
    button {
      background: var(--red);
      color: white;
      border: none;
      padding: 8px 14px;
      cursor: pointer;
      font-family: inherit;
      font-size: 12px;
      border-radius: 3px;
      letter-spacing: 1px;
    }
    button:hover { background: var(--red-light); }
    button:disabled { background: #444; cursor: not-allowed; }
    .history-selectors { display: flex; gap: 8px; margin-bottom: 8px; flex-wrap: wrap; }
    .history-selectors label { font-size: 11px; color: var(--text-dim); display: flex; align-items: center; gap: 4px; cursor: pointer; }
    input[type=checkbox] { accent-color: var(--red); }
    #date-display { font-size: 20px; color: var(--red-light); font-weight: bold; }
  </style>
</head>
<body>

<header>
  <h1>&#9733; Soviet Republic – Genosse Berater</h1>
  <div id="date-display">Jahr … Tag …</div>
  <div id="status">
    <span id="ws-dot"></span>
    <span id="last-updated">–</span>
  </div>
</header>

<div class="grid">

  <!-- Population Tiles -->
  <div class="card">
    <h2>Bevölkerung</h2>
    <div class="tiles">
      <div class="tile"><div class="val" id="t-total">–</div><div class="lbl">Gesamt</div></div>
      <div class="tile"><div class="val" id="t-adults">–</div><div class="lbl">Erwachsene</div></div>
      <div class="tile"><div class="val" id="t-unemployed">–</div><div class="lbl">Arbeitslos</div></div>
      <div class="tile"><div class="val" id="t-childs">–</div><div class="lbl">Kinder</div></div>
      <div class="tile"><div class="val" id="t-age">–</div><div class="lbl">Ø Alter</div></div>
      <div class="tile"><div class="val" id="t-productivity">–</div><div class="lbl">Produktivität</div></div>
    </div>
  </div>

  <!-- Citizen Status -->
  <div class="card">
    <h2>Bürger-Status</h2>
    <div class="chart-container">
      <canvas id="statusChart"></canvas>
    </div>
  </div>

  <!-- Economy Table -->
  <div class="card">
    <h2>Ressourcenpreise (RUB)</h2>
    <div style="max-height:260px;overflow-y:auto;">
      <table>
        <thead><tr><th>Ressource</th><th>RUB</th><th>USD</th></tr></thead>
        <tbody id="economy-table"></tbody>
      </table>
    </div>
  </div>

  <!-- History Chart -->
  <div class="card">
    <h2>Verlauf</h2>
    <div class="history-selectors">
      <label><input type="checkbox" id="h-pop" checked> Bevölkerung</label>
      <label><input type="checkbox" id="h-steel"> Stahl</label>
      <label><input type="checkbox" id="h-coal"> Kohle</label>
      <label><input type="checkbox" id="h-food"> Nahrung</label>
    </div>
    <div class="chart-container">
      <canvas id="historyChart"></canvas>
    </div>
  </div>

  <!-- LLM Chat -->
  <div class="card chat-section">
    <h2>Genosse Berater (LLM)</h2>
    <div id="chat-messages">
      <div class="msg-bot">
        <div class="speaker">GENOSSE BERATER</div>
        Genosse, bereit zur Analyse deiner Republik. Was möchtest du wissen?
      </div>
    </div>
    <div id="chat-controls">
      <select id="model-select"><option value="">Modell laden…</option></select>
      <input type="text" id="chat-input" placeholder="Frag deinen sowjetischen Berater…" />
      <button id="chat-send" onclick="sendChat()">SENDEN</button>
    </div>
  </div>

</div>

<script>
// ─── State ───────────────────────────────────────────────────────────────────
let currentStats = null;
let historyData = null;
let statusChartInstance = null;
let historyChartInstance = null;

// ─── WebSocket ───────────────────────────────────────────────────────────────
function connectWS() {
  const ws = new WebSocket(`ws://${location.host}/ws`);
  ws.onopen = () => document.getElementById('ws-dot').classList.add('connected');
  ws.onclose = () => {
    document.getElementById('ws-dot').classList.remove('connected');
    setTimeout(connectWS, 3000);
  };
  ws.onmessage = () => { fetchStats(); fetchHistory(); };
}

// ─── Fetch ───────────────────────────────────────────────────────────────────
async function fetchStats() {
  const r = await fetch('/api/stats');
  currentStats = await r.json();
  renderStats();
}

async function fetchHistory() {
  const r = await fetch('/api/history');
  historyData = await r.json();
  renderHistory();
}

async function fetchModels() {
  const r = await fetch('/api/models');
  const data = await r.json();
  const sel = document.getElementById('model-select');
  sel.innerHTML = '';
  (data.models || []).forEach(m => {
    const opt = document.createElement('option');
    opt.value = opt.textContent = m;
    sel.appendChild(opt);
  });
  if (!data.models?.length) {
    sel.innerHTML = '<option value="">Ollama nicht verbunden</option>';
  }
}

// ─── Render Stats ─────────────────────────────────────────────────────────────
function renderStats() {
  if (!currentStats || currentStats.error) return;
  const s = currentStats;
  document.getElementById('date-display').textContent = `Jahr ${s.year} · Tag ${s.day}`;
  document.getElementById('last-updated').textContent = s.last_updated?.substring(11,19) + ' UTC' || '–';

  document.getElementById('t-total').textContent = fmt(s.total_population);
  document.getElementById('t-adults').textContent = fmt(s.population?.adults);
  document.getElementById('t-unemployed').textContent = fmt(s.population?.unemployed);
  document.getElementById('t-childs').textContent = fmt((s.population?.small_childs || 0) + (s.population?.medium_childs || 0));
  document.getElementById('t-age').textContent = (s.population?.avg_age || 0).toFixed(1);
  document.getElementById('t-productivity').textContent = ((s.population?.avg_productivity || 0) * 100).toFixed(0) + '%';

  renderStatusChart(s.citizen_status);
  renderEconomyTable(s.economy_rub, s.economy_usd);
}

function fmt(n) { return n != null ? n.toLocaleString('de-DE') : '–'; }

const STATUS_LABELS = ['Nahrung','Wasser','Gesundheit','Bildung','Freizeit','Güter','Wohnen','ÖPNV','Sicherheit'];

function renderStatusChart(statuses) {
  if (!statuses?.length) return;
  const vals = statuses.map(v => Math.round(v * 100));
  const colors = vals.map(v => v >= 70 ? '#4caf50' : v >= 45 ? '#ffc107' : '#cc2200');

  if (statusChartInstance) statusChartInstance.destroy();
  statusChartInstance = new Chart(document.getElementById('statusChart'), {
    type: 'bar',
    data: {
      labels: STATUS_LABELS,
      datasets: [{ data: vals, backgroundColor: colors, borderWidth: 0 }]
    },
    options: {
      indexAxis: 'y',
      plugins: { legend: { display: false } },
      scales: {
        x: { min: 0, max: 100, ticks: { color: '#888', font: { size: 10 } }, grid: { color: '#222' } },
        y: { ticks: { color: '#ccc', font: { size: 10 } }, grid: { display: false } }
      }
    }
  });
}

const PRICE_THRESHOLDS = { high: 100, mid: 20 };
function priceClass(rub) {
  if (rub >= PRICE_THRESHOLDS.high) return 'price-high';
  if (rub >= PRICE_THRESHOLDS.mid) return 'price-mid';
  return 'price-low';
}

function renderEconomyTable(rub, usd) {
  if (!rub) return;
  const tbody = document.getElementById('economy-table');
  tbody.innerHTML = '';
  const names = Object.keys(rub).sort((a,b) => rub[b] - rub[a]);
  names.forEach(name => {
    const tr = document.createElement('tr');
    const cls = priceClass(rub[name]);
    tr.innerHTML = `<td>${name}</td><td class="${cls}">${rub[name].toFixed(1)}</td><td class="price-low">${(usd?.[name] || 0).toFixed(1)}</td>`;
    tbody.appendChild(tr);
  });
}

// ─── History Chart ────────────────────────────────────────────────────────────
function renderHistory() {
  if (!historyData?.records) return;
  const records = historyData.records;
  const labels = records.map(r => `${r.year}/${r.day}`);

  const datasets = [];
  if (document.getElementById('h-pop').checked)
    datasets.push({ label: 'Bevölkerung', data: records.map(r => r.total_population), borderColor: '#ff4422', tension: 0.3, pointRadius: 2, yAxisID: 'y' });
  if (document.getElementById('h-steel').checked)
    datasets.push({ label: 'Stahl (RUB)', data: records.map(r => r.economy_rub?.steel ?? null), borderColor: '#aaa', tension: 0.3, pointRadius: 2, yAxisID: 'y2' });
  if (document.getElementById('h-coal').checked)
    datasets.push({ label: 'Kohle (RUB)', data: records.map(r => r.economy_rub?.coal ?? null), borderColor: '#888', tension: 0.3, pointRadius: 2, yAxisID: 'y2' });
  if (document.getElementById('h-food').checked)
    datasets.push({ label: 'Nahrung (RUB)', data: records.map(r => r.economy_rub?.food ?? null), borderColor: '#4caf50', tension: 0.3, pointRadius: 2, yAxisID: 'y2' });

  if (historyChartInstance) historyChartInstance.destroy();
  historyChartInstance = new Chart(document.getElementById('historyChart'), {
    type: 'line',
    data: { labels, datasets },
    options: {
      plugins: { legend: { labels: { color: '#888', font: { size: 10 } } } },
      scales: {
        x: { ticks: { color: '#888', font: { size: 9 }, maxTicksLimit: 10 }, grid: { color: '#1a1a1a' } },
        y:  { position: 'left',  ticks: { color: '#ff4422', font: { size: 9 } }, grid: { color: '#1e1e1e' } },
        y2: { position: 'right', ticks: { color: '#aaa',    font: { size: 9 } }, grid: { display: false } }
      }
    }
  });
}

['h-pop','h-steel','h-coal','h-food'].forEach(id =>
  document.getElementById(id).addEventListener('change', renderHistory)
);

// ─── Chat ─────────────────────────────────────────────────────────────────────
async function sendChat() {
  const input = document.getElementById('chat-input');
  const model = document.getElementById('model-select').value;
  const msg = input.value.trim();
  if (!msg || !model) return;

  const btn = document.getElementById('chat-send');
  btn.disabled = true;
  input.value = '';

  appendMsg('user', msg);

  const r = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message: msg, model }),
  });
  const data = await r.json();
  appendMsg('bot', data.response || '…');
  btn.disabled = false;
}

function appendMsg(role, text) {
  const container = document.getElementById('chat-messages');
  const div = document.createElement('div');
  if (role === 'user') {
    div.className = 'msg-user';
    div.textContent = '▶ ' + text;
  } else {
    div.className = 'msg-bot';
    div.innerHTML = `<div class="speaker">GENOSSE BERATER</div>${escapeHtml(text)}`;
  }
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

function escapeHtml(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\n/g,'<br>');
}

document.getElementById('chat-input').addEventListener('keydown', e => {
  if (e.key === 'Enter') sendChat();
});

// ─── Init ─────────────────────────────────────────────────────────────────────
fetchStats();
fetchHistory();
fetchModels();
connectWS();
</script>
</body>
</html>
```

**Step 3: Test the full system**

```bash
python main.py
```

Open `http://localhost:8765` — verify:
- Header shows current game year/day
- Population tiles populated
- Citizen status bar chart renders
- Economy table shows resource prices sorted by price
- History chart shows population line
- Chat field connects to Ollama (select model, ask a question)
- WebSocket dot is green

**Step 4: Commit**

```bash
git add static/index.html
git commit -m "feat: add dashboard UI with charts and LLM chat"
```

---

## Task 8: MCP Server Claude Code Integration

**Files:**
- Modify: `C:/Users/tspor/.claude/settings.json`

**Step 1: Verify MCP mode works**

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1"}}}' | python main.py --mcp
```
Expected: JSON response with server info.

**Step 2: Add MCP server to Claude Code settings**

Open `C:/Users/tspor/.claude/settings.json` and add the `mcpServers` section:

```json
{
  "mcpServers": {
    "soviet-republic": {
      "command": "python",
      "args": [
        "E:/SteamLibrary/steamapps/common/SovietRepublic/soviet_dashboard/main.py",
        "--mcp"
      ]
    }
  }
}
```

**Step 3: Restart Claude Code and verify**

Run `/mcp` in Claude Code — `soviet-republic` should appear in the list.

Test: Ask Claude "What is the current population in my Soviet Republic save?"

**Step 4: Final commit**

```bash
git add .
git commit -m "docs: add MCP Claude Code integration instructions"
```

---

## Run Instructions Summary

```bash
# Install
cd E:/SteamLibrary/steamapps/common/SovietRepublic/soviet_dashboard
pip install -r requirements.txt

# Run dashboard
python main.py
# → Open http://localhost:8765

# Run tests
pytest tests/ -v

# MCP mode (Claude Code calls this automatically)
python main.py --mcp
```
