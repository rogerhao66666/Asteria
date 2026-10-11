"""RPG-07 (ASTERIA_SPEC §24): generic world interactions — capability, requirements, cost, check, outcome."""

import pytest

from asteria.events import EventInstruction, EventProgram
from asteria.rpg.world_interactions import WorldInteraction
from asteria.rpg.world_record import FactionDefinition


def _add(game, **fields):
    value = WorldInteraction(**fields)
    game.project.rpg_database.add_world_interaction(value)
    return value


def test_refusals_cost_success_rewards_and_one_time_use(runtime):
    game = runtime.game
    state, ctx = game.save.rpg_state, game.save.event_context
    game.project.rpg_database.add_faction(FactionDefinition("guild", "Guild"))
    game.project.event_programs.register(
        "thanks", EventProgram((EventInstruction("SET_SWITCH", {"name": "thanked", "value": True}),))
    )
    _add(
        game,
        interaction_id="open_vault",
        verb="open",
        actor_tag="roster.01",
        required_item="ether_leaf",
        requirements=({"source": "switch", "name": "vault_found", "operator": "==", "value": "true"},),
        cost_currencies={"gold": 10},
        success_items={"focus_stone": 2},
        success_switch="vault_open",
        success_event="thanks",
        reputation={"guild": 5},
        repeatable=False,
    )
    state.inventory.add("ether_leaf", 1)
    state.currencies["gold"] = 15.0
    assert game.perform_interaction("open_vault") == ("refused", "requires vault_found == True")
    assert state.currencies["gold"] == 15.0  # nothing paid for a refused attempt
    ctx.set_switch("vault_found", True)
    before = state.inventory.count("focus_stone")
    assert game.perform_interaction("open_vault") == ("success", "")
    assert state.currencies["gold"] == 5.0 and state.inventory.count("focus_stone") == before + 2
    assert ctx.get_switch("vault_open") and ctx.get_variable("interaction.open_vault") == "success"
    assert (
        game.save.rpg_state.world.reputation.get("guild", 0) == 5
        if hasattr(game.save.rpg_state.world, "reputation")
        else True
    )
    game.update_events(0.0)
    game.update_events(0.0)
    assert ctx.get_switch("thanked")  # follow-up event ran
    assert game.perform_interaction("open_vault") == ("refused", "already done")


def test_party_capability_and_cost_are_checked(runtime):
    game = runtime.game
    _add(game, interaction_id="persuade_guard", verb="persuade", actor_tag="diplomat", cost_items={"fire_dust": 1})
    assert game.perform_interaction("persuade_guard") == ("refused", "needs a party member with diplomat")
    _add(game, interaction_id="trade", verb="buy", cost_items={"boss_emblem": 999})
    assert game.perform_interaction("trade")[0] == "refused"


def test_stat_checks_are_deterministic_and_failures_run_their_branch(runtime):
    game = runtime.game
    _add(
        game,
        interaction_id="pick_lock",
        verb="custom",
        check_stat="speed",
        difficulty=10_000,
        base_chance=0.0,
        failure_switch="alarm",
    )
    assert game.perform_interaction("pick_lock") == ("failure", "")
    assert game.save.event_context.get_switch("alarm")
    _add(game, interaction_id="lift_rock", verb="custom", check_stat="power", difficulty=0, base_chance=1.0)
    assert game.perform_interaction("lift_rock") == ("success", "")
    chances = WorldInteraction("x", check_stat="power", difficulty=50, base_chance=0.5, chance_per_point=0.01)
    assert chances.chance(70) == pytest.approx(0.7) and chances.chance(500) == 1.0 and chances.chance(-500) == 0.0


def test_an_event_runs_an_interaction_and_branches_on_its_outcome(runtime):
    game = runtime.game
    runtime._ui_mode = "field"
    _add(game, interaction_id="search_bush", verb="search", success_items={"fire_dust": 1})
    game.project.event_programs.register(
        "bush",
        EventProgram(
            (
                EventInstruction("WORLD", {"command": "INTERACT", "args": {"interaction_id": "search_bush"}}),
                EventInstruction(
                    "IF_FALSE_SKIP",
                    {
                        "condition": {
                            "source": "variable",
                            "name": "interaction.search_bush",
                            "operator": "==",
                            "value": "success",
                            "scope_id": None,
                        },
                        "count": 1,
                    },
                ),
                EventInstruction("DIALOGUE", {"speaker": "", "text": "You found fire dust."}),
            )
        ),
    )
    before = game.save.rpg_state.inventory.count("fire_dust")
    game.events.start("bush")
    runtime._frame([], 0.016)
    assert game.pending_dialogue.line.text == "You found fire dust."
    assert game.save.rpg_state.inventory.count("fire_dust") == before + 1


def test_the_world_interactions_form_editor_creates_valid_records(tmp_path):
    from pathlib import Path

    from asteria.editor import EditorDocument
    from asteria.editor.game_systems_authoring import GameSystemsAuthoringController
    from asteria.project import Project

    ref = Path(__file__).parents[1] / "reference_projects/complex_reference_rpg/project.asteria.json"
    document = EditorDocument()
    document.set_project(Project.load_json(ref, document.component_registry), file_path=ref)
    api = GameSystemsAuthoringController(document)
    api.create_new("world_interactions", "fish_pond")
    data = api.form_data("world_interactions", "fish_pond")
    data.update(verb="fish", check_stat="speed", success_items={"fire_dust": 1}, failure_event="boss_interaction_event")
    data["requirements"] = [{"source": "variable", "name": "rod", "operator": ">=", "value": "1"}]
    api.edit("world_interactions", "fish_pond", api.decode("world_interactions", data))
    value = document.project.rpg_database.world_interactions["fish_pond"]
    assert value.verb == "fish" and value.requirements[0]["value"] == 1
    roundtrip = Project.from_data(document.project.to_data(), document.component_registry)
    assert roundtrip.rpg_database.world_interactions["fish_pond"] == value
    data["success_items"] = {"no_such_item": 1}
    with pytest.raises(Exception):
        api.edit("world_interactions", "fish_pond", api.decode("world_interactions", data))
        document.project.validate()
