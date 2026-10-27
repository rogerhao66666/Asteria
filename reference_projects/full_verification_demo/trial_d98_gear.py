"""D98: the demo starts with one spare piece of most gear (Game Start ▸ Starting Gear)."""
import json
from pathlib import Path

from asteria.editor import EditorDocument
from asteria.editor.game_start_authoring import GameStartAuthoringController
from asteria.editor.storage import load_document

path = Path("reference_projects/full_verification_demo/project.asteria.json")
doc = EditorDocument()
load_document(doc, str(path))
db = doc.project.rpg_database
c = GameStartAuthoringController(doc)
data = c.form_data()
data["gear"] = {
    k: 1
    for k, e in sorted(db.equipment.items())
    if e.slot != "form" and (getattr(e, "rarity", "") or "") != "mythic" and not k.endswith("_ex")
}
new = c.apply(data)
raw = json.loads(path.read_text())
raw["game_start"]["rpg_state"] = new.to_data()["rpg_state"]
path.write_text(json.dumps(raw, indent=2) + "\n")
