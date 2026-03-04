import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from mcp_server import tool_get_spend_period

def test_spend_period_vehicles_returns_fuel():
    result = tool_get_spend_period("vehicles")
    assert "error" not in result
    assert "period" in result
    assert "vehicles" in result
    assert isinstance(result["vehicles"], dict)

def test_spend_period_invalid_section():
    result = tool_get_spend_period("invalid")
    assert "error" in result

def test_spend_period_all_sections():
    result = tool_get_spend_period("all")
    assert "error" not in result
    for section in ("constructions", "factories", "shops", "vehicles"):
        assert section in result

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
    assert "error" not in result
    assert result["producers"] == []
    assert "note" in result

def test_chain_inputs_traced():
    result = tool_get_production_chain("aluminium")
    producers = {p["building"]: p for p in result["producers"]}
    assert "aluminium_plant" in producers, "aluminium_plant not found in producers"
    alumina_input = producers["aluminium_plant"]["inputs"].get("alumina")
    assert alumina_input is not None
    assert alumina_input["produced_by"] != []

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
