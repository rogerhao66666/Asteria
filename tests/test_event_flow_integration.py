"""EVT-03 / EVT-04 in the real playable runtime (cutscenes, common and battle events) and their authoring."""

import pytest

pygame = pytest.importorskip("pygame")

from asteria.core import Transform  # noqa: E402
from asteria.editor.event_flow_authoring import battle_condition, track  # noqa: E402
from asteria.events import EventInstruction, EventProgram, LifecycleEventBinding  # noqa: E402
from asteria.events.common import CommonEvent  # noqa: E402


def _program(runtime, program_id, *instructions):
    runtime.game.project.event_programs.register(program_id, EventProgram(tuple(instructions)))


def W(command, wait=0.0, **args):
    data = {"command": command, "args": args}
    if wait:
        data["wait"] = wait
    return ("WORLD", data)


def _frames(runtime, count, events=()):
    for _ in range(count):
        runtime._frame(list(events), 0.05)


def test_cutscene_moves_the_player_runs_camera_vfx_fade_in_parallel_and_can_be_skipped(runtime):
    game = runtime.game
    runtime._ui_mode = "field"
    game.set_player_position(0.0, 0.0)
    tracks = [
        track(
            "hero",
            ("MOVE", {"entity": "player", "x": 20, "y": 0, "duration": 1.0}),
            ("FACE", {"entity": "player", "facing": "left"}),
        ),
        track("camera", W("CAMERA_FOCUS", entity="Astral Tyrant", zoom=1.4, blend=0.2)),
        track(
            "effects",
            W("PLAY_VFX", wait=0.2, asset_id="battle.fx.flame", entity="Astral Tyrant"),
            W("SCREEN_FADE", to=0.5, duration=0.2),
        ),
    ]
    _program(
        runtime,
        "intro",
        EventInstruction("SEQUENCE", {"tracks": tracks, "cutscene": True, "skippable": True, "wait": "all"}),
        EventInstruction("WORLD", {"command": "CAMERA_RELEASE", "args": {"blend": 0}}),
        EventInstruction("WORLD", {"command": "SCREEN_FADE", "args": {"to": 0, "duration": 0}}),
        EventInstruction("SET_SWITCH", {"name": "intro_done", "value": True}),
    )
    game.events.start("intro")
    right = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RIGHT)
    _frames(runtime, 6, [right])  # 0.3 s; the arrow key must not move the player during a cutscene
    x = game.player.get(Transform).x
    assert game.cutscene_active and 4.0 < x < 8.0  # driven by the tween (20 units / 1 s), not by input
    assert runtime.field_camera.zoom > 1.0 and runtime.field_effects.vfx  # camera and VFX tracks ran alongside
    assert runtime.screen.get_at((runtime.width // 2, 3))[:3] == (0, 0, 0)  # letterbox bar
    _frames(runtime, 3)
    assert runtime.field_effects.fade_alpha > 0.0  # the fade started after the VFX track's 0.2 s hold
    runtime.input_source.handle_events(
        [pygame.event.Event(pygame.KEYUP, key=pygame.K_RIGHT), pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)]
    )
    runtime.input.update(runtime.input_source.raw_state())
    runtime._field_input([], 0.0)  # Esc during the cutscene skips it
    _frames(runtime, 3)
    assert game.player.get(Transform).x == 20.0 and game.facing == "left"
    assert game.save.event_context.get_switch("intro_done") and not game.cutscene_active
    assert runtime.field_camera.zoom == 1.0 and runtime.field_effects.fade_alpha == 0.0
    assert not game.event_errors


def test_common_events_autorun_and_parallel_follow_their_switches(runtime):
    game = runtime.game
    runtime._ui_mode = "field"
    _program(
        runtime,
        "chapter_intro",
        EventInstruction("DIALOGUE", {"speaker": "", "text": "Chapter 1"}),
        EventInstruction("SET_SWITCH", {"name": "chapter_intro", "value": False}),
    )
    _program(
        runtime,
        "clock",
        EventInstruction("WAIT", {"seconds": 0.1}),
        EventInstruction("SET_VARIABLE", {"name": "ticks", "value": 1}),
    )
    game.project.common_events = [
        CommonEvent("chapter_intro", "autorun", "chapter_intro"),
        CommonEvent("clock", "parallel", "clock_on"),
    ]
    _frames(runtime, 2)
    assert game.pending_dialogue is None  # switches off: nothing runs
    game.save.event_context.set_switch("chapter_intro", True)
    game.save.event_context.set_switch("clock_on", True)
    _frames(runtime, 1)
    assert game.pending_dialogue.line.text == "Chapter 1" and game.event_busy  # autorun blocks the player
    game.acknowledge_dialogue()
    _frames(runtime, 4)
    assert not game.save.event_context.get_switch("chapter_intro") and not game.event_busy
    assert game.save.event_context.get_variable("ticks") == 1  # the parallel clock ran alongside


def test_battle_event_fires_on_its_condition_once_and_holds_battle_input(runtime):
    game = runtime.game
    _program(
        runtime,
        "boss_taunt",
        EventInstruction("DIALOGUE", {"speaker": "Astral Tyrant", "text": "You will not leave!"}),
        EventInstruction("SET_VARIABLE", {"name": "taunts", "value": 1}),
    )
    game.project.lifecycle_event_bindings.append(
        LifecycleEventBinding(
            "rpg.battle.round_started",
            "boss_taunt",
            conditions=(battle_condition("hp_ratio:astral_tyrant", "<=", 0.5),),
            once=True,
        )
    )
    runtime._ui_mode = "field"
    game.start_encounter("boss_room")
    runtime._battle_presentation.begin()
    assert game.pending_dialogue is None  # round 1 starts at full HP
    boss = next(m for m in game.battle.members if m.startswith("astral"))
    resources = game.battle.member(boss).subject.resources
    resources.set_current("vitality", resources.get("vitality").maximum * 0.4)
    game.battle.start_next_round()
    runtime._frame([], 0.016)
    assert game.pending_dialogue.line.speaker == "Astral Tyrant"
    before = len(game.battle_log)
    runtime._frame([pygame.event.Event(pygame.KEYDOWN, key=pygame.K_1)], 0.016)  # a skill key is not taken
    assert len(game.battle_log) == before and game.pending_dialogue is not None
    game.acknowledge_dialogue()
    runtime._frame([], 0.016)
    assert game.save.event_context.get_variable("taunts") == 1 and game.pending_dialogue is None
    game.battle.start_next_round()
    runtime._frame([], 0.016)
    assert game.pending_dialogue is None  # once per battle


@pytest.fixture
def window():
    pytest.importorskip("PySide6")
    from pathlib import Path

    from PySide6.QtWidgets import QApplication

    from asteria.editor.shell import AsteriaEditorWindow
    from asteria.project import Project

    ref = Path(__file__).parents[1] / "reference_projects/complex_reference_rpg/project.asteria.json"
    app = QApplication.instance() or QApplication([])
    value = AsteriaEditorWindow(None)
    value.document.set_project(Project.load_json(ref, value.document.component_registry), file_path=ref)
    value.refresh_all()
    yield value
    value.document.mark_saved()
    value.close()
    app.processEvents()


def test_common_and_battle_events_panel_edits_the_project_with_undo(window):
    panel = window.event_flow_editor
    assert window.events_workspace.tabText(window.events_workspace.indexOf(panel)) == "Common && Battle Events"
    assert panel.api.new_program("rest_routine") is not None
    panel.refresh()
    panel.common_program.setCurrentText("rest_routine")
    panel.common_trigger.setCurrentText("parallel")
    panel.common_switch.setText("resting")
    assert panel.add_common()
    project = window.document.project
    assert project.common_events[-1] == CommonEvent("rest_routine", "parallel", "resting")
    panel.battle_hook.setCurrentText("rpg.battle.round_started")
    panel.battle_program.setCurrentText("rest_routine")
    panel.cond_source.setCurrentText("battle")
    panel.cond_name.setText("round")
    panel.cond_op.setCurrentText(">=")
    panel.cond_value.setText("3")
    assert panel.add_condition()
    panel.battle_once.setChecked(True)
    assert panel.add_battle()
    binding = project.lifecycle_event_bindings[-1]
    assert binding.once and binding.conditions[0].to_data()["value"] == 3 and panel.battle.rowCount() == 1
    window.document.undo()
    window.document.undo()
    window.document.undo()
    assert not project.common_events and not panel.api.battle_events()


def test_sequence_editor_builds_tracks_and_the_event_editor_inserts_and_edits_them(window, monkeypatch):
    from asteria.editor.event_flow_widget import SequenceEditorDialog

    dialog = SequenceEditorDialog()
    dialog.opcode.setCurrentText("MOVE")
    dialog.fields["x"].setText("30")
    dialog._add_step_clicked()
    dialog.add_track("camera")
    dialog.opcode.setCurrentText("WORLD")
    dialog.fields["args"].setText("entity=Astral Tyrant, zoom=1.5")
    dialog.fields["wait"].setText("0.5")
    dialog._add_step_clicked()
    args = dialog.result_args()
    assert [t["name"] for t in args["tracks"]] == ["track1", "camera"] and args["cutscene"] and args["skippable"]
    assert args["tracks"][0]["instructions"][0] == {
        "opcode": "MOVE",
        "args": {"entity": "player", "x": 30, "y": 0, "duration": 1.0, "relative": False},
    }
    assert args["tracks"][1]["instructions"][0]["args"]["wait"] == 0.5

    from asteria.editor.workspace import WorkspaceMode

    window.workspace.set_mode(WorkspaceMode.EVENT)
    boss = next(e for e in window.document.project.scenes()[0].entities() if e.name == "Astral Tyrant")
    window.document.selection.set_single("entity", boss)
    window.refresh_all()
    monkeypatch.setattr(window, "_sequence_dialog", lambda current=None: args)
    window._event_add_command("sequence")
    program = window.document.project.event_programs.require("boss_interaction_event")
    index = next(i for i, x in enumerate(program.instructions) if x.opcode == "SEQUENCE")
    assert "Sequence  2 parallel tracks (track1, camera)" in window.event_editor.commands.item(index).text()
    edited = dict(args, tracks=args["tracks"][:1])
    monkeypatch.setattr(window, "_sequence_dialog", lambda current=None: edited)
    assert window._event_edit_command(index)
    assert (
        len(window.document.project.event_programs.require("boss_interaction_event").instructions[index].args["tracks"])
        == 1
    )
    window.document.undo()
    window.document.undo()
    assert all(
        x.opcode != "SEQUENCE"
        for x in window.document.project.event_programs.require("boss_interaction_event").instructions
    )


def test_script_authors_the_same_cutscene_and_events(tmp_path):
    from pathlib import Path

    from asteria.authoring.runner import run_authoring_script
    from asteria.editor import EditorDocument
    from asteria.project import Project

    ref = Path(__file__).parents[1] / "reference_projects/complex_reference_rpg/project.asteria.json"
    document = EditorDocument()
    document.set_project(Project.load_json(ref, document.component_registry), file_path=ref)
    source = (
        'intro = project.new_event("intro", "Intro")\n'
        "intro.sequence(\n"
        '    track("hero", move("player", 20, 0, 1.0), face("player", "left")),\n'
        '    track("camera", world("CAMERA_FOCUS", wait=0.5, entity="Astral Tyrant", zoom=1.5),\n'
        '          say("Tyrant", "Halt")),\n'
        "    cutscene=True, skippable=True,\n"
        ")\n"
        'project.common_event("intro", "autorun", "intro_on")\n'
        'project.battle_event("rpg.battle.round_started", "intro",\n'
        '                     conditions=[battle_condition("round", ">=", 2)], once=True)\n'
    )
    result = run_authoring_script(source, document.project, execute=document.execute)
    assert result.success, result.diagnostic
    project = document.project
    sequence = project.event_programs.require("intro").instructions[0]
    assert sequence.opcode == "SEQUENCE" and [t["name"] for t in sequence.args["tracks"]] == ["hero", "camera"]
    assert project.common_events[-1] == CommonEvent("intro", "autorun", "intro_on")
    assert project.lifecycle_event_bindings[-1].once
    roundtrip = Project.from_data(project.to_data(), document.component_registry)
    assert roundtrip.common_events == project.common_events
    assert roundtrip.lifecycle_event_bindings[-1].conditions == project.lifecycle_event_bindings[-1].conditions
