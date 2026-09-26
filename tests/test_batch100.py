import json
from pathlib import Path
def test_closure_matrix_all_passes():
 p=Path(__file__).parents[1]/"BATCH100_CLOSURE.json"
 d=json.loads(p.read_text());assert d["all_pass"] is True
 assert all(d["gates"].values())
def test_closure_keeps_external_verification_honest():
 t=(Path(__file__).parents[1]/"BATCH100_ART_ENGINE_CLOSURE_AUDIT.md").read_text()
 assert "Actual PySide6" in t and "ModernGL/Pygame" in t and "Human Art PASS" in t
def test_closure_authorizes_assets_only_as_validation_phase():
 d=json.loads((Path(__file__).parents[1]/"BATCH100_CLOSURE.json").read_text())
 assert d["result"]=="PASS_FOR_STARTER_ASSET_VALIDATION"
