"""An encounter can name the turn scheduler it uses with a ``scheduler:<id>`` tag."""

import dataclasses

from test_battle_extensions_session import _first_encounter, _session

from asteria.rpg.battle_scheduler import BattleSchedulerDefinition


def test_the_encounter_tag_picks_the_scheduler():
    game = _session()
    db = game.project.rpg_database
    default = next(iter(db.battle_schedulers.values()))
    db.battle_schedulers["rounds"] = BattleSchedulerDefinition("rounds", mode="round")
    encounter_id = _first_encounter(game)
    game.start_encounter(encounter_id)
    assert game.battle.scheduler.definition.scheduler_id == default.scheduler_id
    game.battle = None
    game.mode = "field"
    game.encounter_id = None
    encounter = db.encounters[encounter_id]
    db.encounters[encounter_id] = dataclasses.replace(
        encounter, tags=(*encounter.tags, "scheduler:rounds")
    )
    game.start_encounter(encounter_id)
    assert game.battle.scheduler.definition.scheduler_id == "rounds"
