"""Everyone on the Full Verification maps wears a look of their own, and Aldric's house has a bed
that rests the party."""

import sys
from pathlib import Path

DEMO = Path(__file__).resolve().parents[1] / "reference_projects" / "full_verification_demo"
sys.path.insert(0, str(DEMO))

import run_trial_smoke as smoke  # noqa: E402

from asteria.runtime.components2d import SpriteRenderer2D  # noqa: E402
from asteria.runtime.field_ai import VisibleEncounterComponent  # noqa: E402

PARTY = {"Player", "Mira", "Vesper", "Cael"}


def test_no_two_people_share_a_look():
    project, _game = smoke.load()
    wearers = {}  # sprite sheet -> names wearing it
    for scene in project.scenes():
        for entity in scene.entities():
            renderer = entity.try_get(SpriteRenderer2D)
            if renderer is None or entity.has(VisibleEncounterComponent):
                continue  # a kind of foe looks alike on purpose
            if entity.name.startswith("doodad:"):
                continue
            wearers.setdefault(renderer.sprite_sheet_asset_id, set()).add(entity.name)
    shared = {sheet: names for sheet, names in wearers.items() if len(names) > 1}
    assert not shared, shared
    party_sheets = {s for s, names in wearers.items() if names & PARTY}
    assert len(party_sheets) == 4  # the hero and three companions keep their own


def test_sleeping_in_the_bed_rests_the_party():
    _project, game = smoke.load()
    home = next(s for s in game.project.scenes() if s.name == "Aldric's House")
    town = next(s for s in game.project.scenes() if s.name == "Hearthfold")
    assert any(e.name == "House Door" for e in town.entities())
    game.transfer_player(home.id)
    game.damage_party("vitality", 500)
    values = game.save.rpg_state.actor_snapshots[smoke.HERO].resources["values"]["vitality"]
    assert values["current"] < values["maximum"]
    game.events.start("home.bed")
    for _ in range(200):
        if not game.event_busy:
            break
        runner = game._dialogue_runner()
        dialogue = None if runner is None else runner.dialogue
        if dialogue is not None and dialogue.choice is not None:
            game.choose(0)  # Sleep
        elif dialogue is not None and dialogue.dialogue is not None:
            game.acknowledge_dialogue()
        else:
            game.update_events(0.1)
    values = game.save.rpg_state.actor_snapshots[smoke.HERO].resources["values"]["vitality"]
    assert values["current"] == values["maximum"]
