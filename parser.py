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
    trade_import_rub: dict = field(default_factory=dict)
    trade_export_rub: dict = field(default_factory=dict)
    trade_import_usd: dict = field(default_factory=dict)
    trade_export_usd: dict = field(default_factory=dict)
    trade_import_international_rub: dict = field(default_factory=dict)
    trade_export_international_rub: dict = field(default_factory=dict)
    trade_import_international_usd: dict = field(default_factory=dict)
    trade_export_international_usd: dict = field(default_factory=dict)
    trade_vehicles: dict = field(default_factory=dict)

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
    current_trade_section: Optional[str] = None  # key into StatRecord trade_* dicts

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

    VEHICLE_KEYS = {
        "$Vehicles_ImportRUB": "import_rub",
        "$Vehicles_ExportRUB": "export_rub",
        "$Vehicles_ImportUSD": "import_usd",
        "$Vehicles_ExportUSD": "export_usd",
    }

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
            current_trade_section = None
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
        if stripped.split()[0] in VEHICLE_KEYS and len(stripped.split()) == 2:
            key = VEHICLE_KEYS[stripped.split()[0]]
            try:
                current.trade_vehicles[key] = float(stripped.split()[1])
            except ValueError:
                pass
            continue

        # Economy resource line (indented): "   steel 113.013054 1.050000"
        if line != stripped and stripped and current_economy_section:
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

        # Non-indented non-$ lines reset economy section (e.g. "Citizens", "Economy")
        if not stripped.startswith("$"):
            current_economy_section = None
            current_trade_section = None
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
