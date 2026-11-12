"""D109: who carries what, by what it means.

* **Cover** is a Knight's: the Knight job gives ``trait.cover`` (it was Roger's own). An author
  may still give it to one character; the demo shows it on a job.
* **The Demon Ring is Roger's alone**: his own trait ``trait.ring_bearer``, which the ring needs
  (besides a job that wields rings). The gear page says who can wear it.
* **Roger starts wearing it** in his free hand (Game Start ▸ Starting Equipment); the family
  chest holds the six charms only.

Re-runnable over ``project.asteria.json``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "src"))

from asteria.editor import EditorDocument  # noqa: E402
from asteria.editor.project.storage import load_document  # noqa: E402
from asteria.editor.rpg.game_start_authoring import GameStartAuthoringController  # noqa: E402

PATH = HERE / "project.asteria.json"
RING = {"actor_id": "hero_01", "slot_id": "sub_weapon", "equipment_id": "w_demon_ring"}
CHINESE = {"dlg.home_che.12": "空了。"}


def _data():
    data = json.loads(PATH.read_text(encoding="utf-8"))
    db = data["rpg_database"]
    (roger,) = [a for a in db["actors"] if a["actor_id"] == "hero_01"]
    roger["tags"] = sorted((set(roger["tags"]) - {"trait.cover"}) | {"trait.ring_bearer"})
    (knight,) = [c for c in db["classes"] if c["class_id"] == "knight"]
    knight["granted_tags"] = sorted(set(knight["granted_tags"]) | {"trait.cover"})
    (ring,) = [e for e in db["equipment"] if e["equipment_id"] == "w_demon_ring"]
    ring["required_capabilities"] = sorted(
        set(ring.get("required_capabilities", ())) | {"trait.ring_bearer"}
    )
    chest = data["event_programs"]["home.chest"]["instructions"]
    chest[:] = [
        x for x in chest if x.get("args", {}).get("args", {}).get("equipment_id") != "w_demon_ring"
    ]
    for step in chest:
        args = step.get("args", {})
        if args.get("args", {}).get("text") == "The Demon Ring and six charms!":
            args["args"]["text"] = "Six charms!"
        if args.get("text") == "Empty. The ring is yours.":
            args["text"] = "Empty."
    (zh,) = [t for t in db["locale_tables"] if t["locale"] == "zh-TW"]
    zh["entries"].update(CHINESE)
    return data


def main():
    PATH.write_text(json.dumps(_data(), indent=2) + "\n", encoding="utf-8")
    document = EditorDocument()
    load_document(document, str(PATH))
    controller = GameStartAuthoringController(document)
    form = controller.form_data()
    if RING not in form["worn"]:
        form["worn"].append(RING)
    new = controller.apply(form)
    raw = json.loads(PATH.read_text(encoding="utf-8"))
    raw["game_start"]["rpg_state"] = new.to_data()["rpg_state"]
    PATH.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
