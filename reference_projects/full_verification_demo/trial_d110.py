"""D110: what a character starts wearing is the character's own, and labels that do nothing go.

* **Starting equipment on the actor.** Each actor's ``starting_equipment`` (slot, gear) is put
  on at New Game (``rpg.items.starting_gear``). The pieces Game Start's loadouts held move to
  their actors, and those loadouts go. Game Start ▸ Starting Equipment only shows them now,
  with a jump to each character.
* **Slots as records.** A project whose slots lived only in those loadouts (the Party RPG
  template) gets them as its own equipment slot records, so a fresh loadout has them.
* **No more "Actor Kind" / "Roster".** ``actor.playable`` and ``roster.NN`` were labels no rule
  read. They are gone from the actors, along with their definitions and words.

Runs on this demo, the Party RPG template and its demo copy. Re-runnable.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PATHS = (
    HERE / "project.asteria.json",
    REPO / "src" / "asteria" / "templates" / "party_rpg" / "project.asteria.json",
    REPO / "reference_projects" / "party_rpg_demo" / "project.asteria.json",
)
GONE = ("actor.", "roster.")  # property groups that only labelled
PLAIN = {"schema", "version", "instance_id", "equipment_id", "attachments", "growth"}


def _label(tag):
    return tag.startswith(GONE) or tag in ("actor.*", "roster.*")


def _plain(piece, actor_id):
    """A piece made as starting gear is (no sockets, growth, rolls or wear), so the actor's
    field makes it again the same."""
    return (
        set(piece) <= PLAIN
        and not piece.get("attachments")
        and piece.get("growth") is None
        and piece.get("instance_id", "").startswith(f"{piece.get('equipment_id')}:{actor_id}")
    )


def _slot_records(db, loadouts):
    """Slots from the loadouts become the project's own records when it has none."""
    if db.get("equipment_slots"):
        return
    found = {}
    for loadout in loadouts.values():
        for slot in loadout.get("slots", ()):
            found.setdefault(slot["slot_id"], slot)
    db["equipment_slots"] = [
        {
            "slot_id": slot_id,
            "display_name": slot_id.replace("_", " ").title(),
            "order": (index + 1) * 10,
            "capacity": found[slot_id].get("capacity", 1),
            "accepted_tags": list(found[slot_id].get("accepted_tags", ())),
        }
        for index, slot_id in enumerate(sorted(found))
    ]


def migrate(data):
    db = data["rpg_database"]
    state = (data.get("game_start") or {}).get("rpg_state") or {}
    loadouts = state.get("loadouts", {})
    _slot_records(db, loadouts)
    actors = {a["actor_id"]: a for a in db["actors"]}
    for actor_id in sorted(loadouts):
        loadout, actor = loadouts[actor_id], actors.get(actor_id)
        pieces = [(s, p) for s, ps in sorted(loadout["equipped"].items()) for p in ps]
        if actor is None or not all(_plain(p, actor_id) for _s, p in pieces):
            continue  # a piece with a life of its own stays in Game Start
        rows = [{"slot_id": s, "equipment_id": p["equipment_id"]} for s, p in pieces]
        if rows:
            actor["starting_equipment"] = rows
        del loadouts[actor_id]
    order = {s["slot_id"]: (s.get("order", 0), i) for i, s in enumerate(db["equipment_slots"])}
    for actor in db["actors"]:
        actor["tags"] = [t for t in actor.get("tags", ()) if not _label(t)]
        if actor.get("starting_equipment"):  # as the slots are ordered
            actor["starting_equipment"].sort(key=lambda r: order.get(r["slot_id"], (1 << 30, 0)))
    if "tag_definitions" in db:
        db["tag_definitions"] = [t for t in db["tag_definitions"] if not _label(t["tag_id"])]
    for table in db.get("locale_tables", ()):
        words = table["entries"]
        for key in [k for k in words if k.startswith(("data.tag.actor.", "data.tag.roster."))]:
            del words[key]
    return data


def main():
    for path in PATHS:
        data = json.loads(path.read_text(encoding="utf-8"))
        path.write_text(json.dumps(migrate(data), indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.path.insert(0, str(HERE))
    main()
