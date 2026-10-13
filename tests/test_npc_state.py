"""WLD-02 (ASTERIA_SPEC §26): NPC state model — visibility, alive, mood, stage, flags, location;
saved."""

from asteria.core import Entity, Scene, Transform
from asteria.events import EventInstruction, EventProgram
from asteria.rpg.world_record import WorldRecord
from asteria.runtime.npc_state import NpcIdentity2DComponent


def _npc(scene, npc_id, x=10.0, y=0.0):
    entity = scene.add_entity(Entity(npc_id.title()))
    entity.add_component(Transform(x, y))
    identity = NpcIdentity2DComponent()
    identity.npc_id = npc_id
    entity.add_component(identity)
    return entity


def _world(command, **args):
    return EventInstruction("WORLD", {"command": command, "args": args})


def test_old_world_records_load_and_npc_state_round_trips():
    old = WorldRecord().to_data()
    old["version"] = 1
    old.pop("npcs")
    assert WorldRecord.from_data(old).npcs == {}
    record = WorldRecord()
    record.npc("mira")["flags"]["met"] = True
    assert WorldRecord.from_data(record.to_data()).npc_value("mira", "flag.met") is True


def test_events_change_npc_state_hide_and_branch_on_it(runtime):
    game = runtime.game
    mira = _npc(game.scene, "mira")
    game.project.event_programs.register(
        "mira_leaves",
        EventProgram(
            (
                _world("SET_NPC", npc="mira", key="flag.met", value=True),
                _world("SET_NPC", npc="mira", key="mood", value="happy"),
                _world("SET_NPC", npc="mira", key="stage", value="2"),
                _world("SET_NPC", npc="mira", key="visible", value="false"),
                EventInstruction(
                    "IF_FALSE_SKIP",
                    {
                        "condition": {
                            "source": "npc",
                            "name": "mira.stage",
                            "operator": ">=",
                            "value": 2,
                            "scope_id": None,
                        },
                        "count": 1,
                    },
                ),
                EventInstruction("SET_SWITCH", {"name": "mira_stage_two", "value": True}),
            )
        ),
    )
    game.events.start("mira_leaves")
    game.update_events(0.0)
    assert not game.event_errors and game.save.event_context.get_switch("mira_stage_two")
    assert not mira.enabled  # hidden NPC: not drawn, not interactable (scene queries skip it)
    assert (
        game.world.npc_value("mira", "mood") == "happy"
        and game.world.npc_value("mira", "flag.met") is True
    )


def test_relocated_npc_appears_in_its_new_scene_and_state_survives_save(runtime):
    from asteria.runtime.game_save import GameRuntimeSave
    from asteria.runtime.game_session import GameSessionRuntime

    game = runtime.game
    town = game.scene
    inn = game.project.add_scene(Scene("Inn"))
    mira_town = _npc(town, "mira")
    mira_inn = _npc(inn, "mira", 0.0, 0.0)
    game.move_npc("mira", inn.id, 33.0, 4.0)
    assert not mira_town.enabled  # she left town
    game.transfer_player(inn.id, 0.0, 0.0)
    assert mira_inn.enabled and (mira_inn.get(Transform).x, mira_inn.get(Transform).y) == (
        33.0,
        4.0,
    )
    game.set_position("Mira", 40.0, 5.0)  # e.g. a cutscene MOVE
    game.set_facing("Mira", "left")
    game.sync_world_state()
    data = game.save.to_data()
    restored = GameSessionRuntime(game.project, GameRuntimeSave.from_data(data, game.project))
    state = restored.world.npcs["mira"]
    assert (
        state["scene_id"] == inn.id
        and state["position"] == [40.0, 5.0]
        and state["facing"] == "left"
    )
