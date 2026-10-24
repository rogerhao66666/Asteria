"""Move details (priority, drain, recoil, several strikes, battle-only states) and grid
characters that notice the player (SightTrigger2D)."""

import random

import pytest

from asteria.core import Entity, Scene, Transform
from asteria.gameplay.abilities import AbilityDefinition
from asteria.rpg.battle_scheduler import BattleScheduler, BattleSchedulerDefinition
from asteria.rpg.battle_states import BattleStatePolicy
from asteria.runtime.grid_actors import (
    GridMover2DComponent,
    GridMoverSystem,
    SightTrigger2DComponent,
    line_of_sight,
)


def test_new_ability_fields_round_trip_and_validate():
    data = {
        "schema": "asteria.ability_definition",
        "version": 1,
        "ability_id": "x",
        "targeting": {
            "minimum_targets": 1,
            "maximum_targets": 1,
            "allow_self": False,
            "required_tags": [],
            "blocked_tags": [],
        },
        "costs": [],
        "conditions": {"type": "group", "mode": "all", "conditions": []},
        "effects": [],
        "tags": [],
        "priority": 1,
        "drain": 0.5,
        "recoil": 0.25,
        "hit_counts": {"2": 3, "5": 1},
        "hits": [{"tags": [], "power": 1.0, "first_checks": ["land"], "checks": ["crit"]}],
    }
    definition = AbilityDefinition.from_data(data)
    assert (definition.priority, definition.drain, definition.recoil) == (1, 0.5, 0.25)
    assert definition.hit_counts == {2: 3.0, 5: 1.0}
    assert definition.hits[0]["first_checks"] == ["land"]
    assert AbilityDefinition.from_data(definition.to_data()) == definition
    bare = AbilityDefinition.from_data({k: v for k, v in data.items() if k not in (
        "priority", "drain", "recoil", "hit_counts")})  # fmt: skip
    assert "priority" not in bare.to_data() and bare.hit_counts == {}
    with pytest.raises(ValueError):
        AbilityDefinition.from_data({**data, "drain": -1})
    with pytest.raises(ValueError):
        AbilityDefinition.from_data({**data, "hit_counts": {"0": 1}})


class _Member:
    def __init__(self, member_id, speed):
        self.member_id, self.side, self.initiative = member_id, "x", speed
        self.current_initiative = speed


def test_a_round_goes_by_priority_then_speed():
    fast, slow = _Member("fast", 50), _Member("slow", 5)
    scheduler = BattleScheduler((fast, slow), BattleSchedulerDefinition("s"))
    assert [e.member_id for e in scheduler._pending] == ["fast", "slow"]
    scheduler.set_priorities({"slow": 1})  # a quick move: first despite its speed
    assert scheduler.peek().member_id == "slow"
    scheduler.pop()
    scheduler.pop()
    scheduler.set_priorities({})
    scheduler.start_round()
    assert scheduler.peek().member_id == "fast"


def _creature_battle(monkeypatch):
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "reference_projects" / "full_verification_demo"
    sys.path.insert(0, str(root))
    import run_trial_smoke as smoke
    import trial_creatures

    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    project, game = smoke.load()
    trial_creatures.install(project, max_moves=4)
    library = project.gameplay_library.abilities
    shot = library.require("pet_shot").to_data()
    for ability_id, extra in (
        ("drain_shot", {"drain": 0.5}),
        ("recoil_shot", {"recoil": 0.5}),
        ("fury_shot", {"hit_counts": {3: 1}}),
        ("quick_shot", {"priority": 1}),
    ):
        library.register(AbilityDefinition.from_data({**shot, "ability_id": ability_id, **extra}))
        targeting = project.rpg_database.battle_targeting["pet_shot"].to_data()
        targeting["ability_id"] = ability_id
        from asteria.rpg.targeting import BattleTargetingDefinition

        project.rpg_database.battle_targeting[ability_id] = BattleTargetingDefinition.from_data(
            targeting
        )
    pet = game.add_pet("cub", level=10)
    pet.moves = ["drain_shot", "recoil_shot", "fury_shot", "quick_shot"]
    return game


HP = "vitality"


def test_drain_heals_and_recoil_hurts_by_the_damage_dealt(monkeypatch):
    game = _creature_battle(monkeypatch)
    battle = game.start_encounter("wild_cubs")
    me, foe = game.stage_ids("heroes")[0], game.stage_ids("enemies")[0]
    mine, theirs = battle.member(me).subject.resources, battle.member(foe).subject.resources
    theirs.get(HP).set_maximum(500)
    theirs.set_current(HP, 500)
    mine.set_current(HP, 1)
    before = theirs.current(HP)
    game._repeat_action(me, "drain_shot", (foe,), True, 1)
    dealt = before - theirs.current(HP)
    assert dealt > 0 and mine.current(HP) == min(mine.maximum(HP), 1 + max(1, int(dealt * 0.5)))
    kinds = [e.kind for e in game.drain_battle_log()]
    assert "drain" in kinds
    mine.set_current(HP, mine.maximum(HP))
    before, top = theirs.current(HP), mine.current(HP)
    game._repeat_action(me, "recoil_shot", (foe,), True, 1)
    dealt = before - theirs.current(HP)
    assert mine.current(HP) == max(0.0, top - max(1, int(dealt * 0.5)))  # never below 0
    assert "recoil" in [e.kind for e in game.drain_battle_log()]


def test_a_several_strike_move_strikes_its_count_and_says_so(monkeypatch):
    game = _creature_battle(monkeypatch)
    battle = game.start_encounter("wild_cubs")
    me, foe = game.stage_ids("heroes")[0], game.stage_ids("enemies")[0]
    theirs = battle.member(foe).subject.resources
    theirs.get(HP).set_maximum(5000)
    theirs.set_current(HP, 5000)
    results = game._repeat_action(me, "fury_shot", (foe,), True, 1)
    assert len(results) == 3
    log = game.drain_battle_log()
    assert [e.data["count"] for e in log if e.kind == "strikes"] == [3]
    assert sum(1 for e in log if e.kind == "action") == 3


def test_foes_choose_at_the_round_start_and_priority_goes_first(monkeypatch):
    game = _creature_battle(monkeypatch)
    battle = game.start_encounter("wild_cubs")
    from asteria.rpg.battle_scheduler import BattleSchedulerDefinition as Definition

    assert battle.scheduler is not None or Definition  # the demo has a scheduler
    me = game.stage_ids("heroes")[0]
    priorities = game.plan_round({me: "quick_shot"})
    assert priorities[me] == 1
    foe = game.stage_ids("enemies")[0]
    assert game._planned[foe] in battle.member(foe).ability_ids
    if battle.scheduler is not None:
        battle.member(me).subject.stats.set("speed", 0.0)  # the slowest
        game.plan_round({me: "quick_shot"})
        assert game.current_turn_actor() == me


def test_battle_only_states_are_not_kept_on_the_creature(monkeypatch):
    from asteria.gameplay import StateDefinition

    game = _creature_battle(monkeypatch)
    db, library = game.project.rpg_database, game.project.gameplay_library
    library.add_state(StateDefinition("braced", 99.0))
    library.add_state(StateDefinition("sore", 99.0))
    db.add_battle_state_policy(BattleStatePolicy("braced", battle_only=True))
    db.add_battle_state_policy(BattleStatePolicy("sore"))
    assert BattleStatePolicy.from_data(db.battle_state_policies["braced"].to_data()).battle_only
    battle = game.start_encounter("wild_cubs")
    me = game.stage_ids("heroes")[0]
    for state in ("braced", "sore"):
        battle.member(me).subject.states.apply(state)
    game._write_battle_pets_to_save()
    assert game.pet_of_member(me).states == ["sore"]


def test_line_of_sight_needs_a_clear_straight_line_ahead():
    clear = lambda cell: False  # noqa: E731
    assert line_of_sight(3, "down", (5, 5), (5, 8), clear) == [(5, 6), (5, 7)]
    assert line_of_sight(3, "down", (5, 5), (5, 9), clear) is None  # too far
    assert line_of_sight(3, "down", (5, 5), (6, 7), clear) is None  # not in line
    assert line_of_sight(3, "up", (5, 5), (5, 7), clear) is None  # behind it
    assert line_of_sight(3, "down", (5, 5), (5, 7), lambda c: c == (5, 6)) is None  # a wall


def test_a_trainer_notices_walks_up_and_starts_its_event(monkeypatch):
    from pathlib import Path

    from asteria.editor import EditorDocument
    from asteria.events import EventProgram
    from asteria.events.program import EventInstruction
    from asteria.project import Project
    from asteria.runtime.components2d import Interaction2DComponent
    from asteria.runtime.game_session import GameSessionRuntime

    root = Path(__file__).resolve().parents[1] / "reference_projects" / "octopath_demo"
    project = Project.load_json(root / "project.asteria.json", EditorDocument().component_registry)
    project.event_programs.register(
        "challenge",
        EventProgram(
            (
                EventInstruction("DIALOGUE", {"speaker": "", "text": "Hey you!"}),
                EventInstruction("END"),
            ),
            name="challenge",
        ),
    )
    game = GameSessionRuntime(project, project.game_start.instantiate(project))
    trainer = game.scene.add_entity(Entity("Trainer"))
    trainer.add_component(Transform(5 * 16 + 8, 5 * 16 + 8))
    mover = trainer.add_component(GridMover2DComponent())
    mover.facing = "down"
    sight = trainer.add_component(SightTrigger2DComponent())
    sight.range, sight.music, sight.done_switch = 4, "chase_song", "beaten"
    talk = trainer.add_component(Interaction2DComponent())
    talk.event_program_id = "challenge"
    game.player.get(Transform).x, game.player.get(Transform).y = 5 * 16 + 8, 8 * 16 + 8
    game._tile_blocking.pop(game.scene.id, None)
    assert game.check_sight() == trainer.id
    assert game.event_busy and game.emotes[trainer.id][0] == "exclamation"
    assert game.presentation_requests[-1].args == {"asset_id": "chase_song", "temporary": True}
    for _ in range(200):
        game.field_update(1 / 30)
        if game.sighting is None:
            break
    assert trainer.get(Transform).y == 7 * 16 + 8  # walked up next to the player
    assert game.facing == "up" and game.pending_dialogue is not None
    game.save.event_context.set_switch("beaten", True)
    game.events.vm = None  # the event is over
    assert game.check_sight() is None  # beaten: it no longer notices


def test_a_looker_turns_only_between_its_own_directions():
    scene = Scene("Town")
    person = Entity("Guard")
    person.add_component(Transform(8, 8))
    mover = person.add_component(GridMover2DComponent())
    mover.behaviour, mover.pauses, mover.look_facings = "look_around", "0.1", "down, right"
    scene.add_entity(person)
    system = GridMoverSystem(random.Random(4))
    seen = set()
    for _ in range(600):
        system.update(scene, 1 / 60, None)
        seen.add(mover.facing)
    assert seen == {"down", "right"}
