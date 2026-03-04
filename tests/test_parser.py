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
    records = parse_stats_file(STATS)
    fuel_found = any("fuel" in r.spend_vehicles for r in records)
    assert fuel_found, "Expected at least one record with fuel in spend_vehicles"

def test_spend_constructions_has_workers():
    records = parse_stats_file(STATS)
    workers_found = any("workers" in r.spend_constructions for r in records)
    assert workers_found, "Expected at least one record with workers in spend_constructions"
