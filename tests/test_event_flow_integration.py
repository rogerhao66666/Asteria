"""EVT-03 / EVT-04 in the real playable runtime (cutscenes, common and battle events) and their
authoring."""

import pytest

pygame = pytest.importorskip("pygame")

from asteria.core import Transform  # noqa: E402
from asteria.editor.events.flow_authoring import battle_condition, track  # noqa: E402
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
        EventInstruction(
            "SEQUENCE", {"tracks": tracks, "cutscene": True, "skippable": True, "wait": "all"}
        ),
        EventInstruction("WORLD", {"command": "CAMERA_RELEASE", "args": {"blend": 0}}),
        EventInstruction("WORLD", {"command": "SCREEN_FADE", "args": {"to": 0, "duration": 0}}),
        EventInstruction("SET_SWITCH", {"name": "intro_done", "value": True}),
    )
    game.events.start("intro")
    right = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RIGHT)
    _frames(runtime, 6, [right])  # 0.3 s; the arrow key must not move the player during a cutscene
    x = game.player.get(Transform).x
    assert (
        game.cutscene_active and 4.0 < x < 8.0
    )  # driven by the tween (20 units / 1 s), not by input
    assert (
        runtime.field_camera.zoom > 1.0 and runtime.field_effects.vfx
    )  # camera and VFX tracks ran alongside
    assert runtime.screen.get_at((runtime.width // 2, 3))[:3] == (0, 0, 0)  # letterbox bar
    _frames(runtime, 3)
    assert (
        runtime.field_effects.fade_alpha > 0.0
    )  # the fade started after the VFX track's 0.2 s hold
    runtime.input_source.handle_events(
        [
            pygame.event.Event(pygame.KEYUP, key=pygame.K_RIGHT),
            pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE),
        ]
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
    assert (
        game.pending_dialogue.line.text == "Chapter 1" and game.event_busy
    )  # autorun blocks the player
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
    runtime._frame(
        [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_1)], 0.016
    )  # a skill key is not taken
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

    ref = (
        Path(__file__).parents[1] / "reference_projects/complex_reference_rpg/project.asteria.json"
    )
    app = QApplication.instance() or QApplication([])
    value = AsteriaEditorWindow(None)
    value.document.set_project(
        Project.load_json(ref, value.document.component_registry), file_path=ref
    )
    value.refresh_all()
    yield value
    value.document.mark_saved()
    value.close()
    app.processEvents()


def test_common_and_battle_events_panel_edits_the_project_with_undo(window):
    panel = window.event_flow_editor
    assert (
        window.events_workspace.tabText(window.events_workspace.indexOf(panel))
        == "Common && Battle Events"
    )
    assert panel.api.new_program("rest_routine") is not None
    panel.refresh()
    panel.common_program.setCurrentText("rest_routine")
    panel.common_trigger.setCurrentText("parallel")
    panel.common_switch.setCurrentText("resting")
    assert panel.add_common()
    project = window.document.project
    assert project.common_events[-1] == CommonEvent("rest_routine", "parallel", "resting")
    panel.battle_hook.setCurrentIndex(panel.battle_hook.findData("rpg.battle.round_started"))
    panel.battle_program.setCurrentText("rest_routine")
    panel.cond_source.setCurrentText("battle")
    panel.cond_name.setCurrentText("round")
    panel.cond_op.setCurrentText(">=")
    panel.cond_number.setValue(3)
    assert panel.add_condition()
    panel.battle_once.setChecked(True)
    assert panel.add_battle()
    binding = project.lifecycle_event_bindings[-1]
    assert (
        binding.once
        and binding.conditions[0].to_data()["value"] == 3
        and panel.battle.rowCount() == 1
    )
    window.document.undo()
    window.document.undo()
    window.document.undo()
    assert not project.common_events and not panel.api.battle_events()


def test_sequence_editor_builds_tracks_and_the_event_editor_inserts_and_edits_them(
    window, monkeypatch
):
    from asteria.editor.events.flow_widget import SequenceEditorDialog

    dialog = SequenceEditorDialog()
    dialog.opcode.setCurrentText("MOVE")
    dialog.fields["x"].setText("30")
    dialog._add_step_clicked()
    dialog.add_track("camera")
    dialog.opcode.setCurrentText("WORLD")
    dialog.world.set_command("CAMERA_FOCUS", {"entity": "Astral Tyrant", "zoom": 1.5})
    dialog.fields["wait"].setText("0.5")
    dialog._add_step_clicked()
    args = dialog.result_args()
    assert (
        [t["name"] for t in args["tracks"]] == ["track1", "camera"]
        and args["cutscene"]
        and args["skippable"]
    )
    assert args["tracks"][0]["instructions"][0] == {
        "opcode": "MOVE",
        "args": {"entity": "player", "x": 30, "y": 0, "duration": 1.0, "relative": False},
    }
    assert args["tracks"][1]["instructions"][0]["args"]["wait"] == 0.5

    from asteria.editor.project.workspace import WorkspaceMode

    window.workspace.set_mode(WorkspaceMode.EVENT)
    boss = next(
        e for e in window.document.project.scenes()[0].entities() if e.name == "Astral Tyrant"
    )
    window.document.selection.set_single("entity", boss)
    window.refresh_all()
    monkeypatch.setattr(window, "_sequence_dialog", lambda current=None: args)
    window._event_add_command("sequence")
    program = window.document.project.event_programs.require("boss_interaction_event")
    index = next(i for i, x in enumerate(program.instructions) if x.opcode == "SEQUENCE")
    assert (
        "Sequence  2 parallel tracks (track1, camera)"
        in window.event_editor.commands.item(index).text()
    )
    edited = dict(args, tracks=args["tracks"][:1])
    monkeypatch.setattr(window, "_sequence_dialog", lambda current=None: edited)
    assert window._event_edit_command(index)
    assert (
        len(
            window.document.project.event_programs.require("boss_interaction_event")
            .instructions[index]
            .args["tracks"]
        )
        == 1
    )
    window.document.undo()
    window.document.undo()
    assert all(
        x.opcode != "SEQUENCE"
        for x in window.document.project.event_programs.require(
            "boss_interaction_event"
        ).instructions
    )


def test_script_authors_the_same_cutscene_and_events(tmp_path):
    from pathlib import Path

    from asteria.authoring.runner import run_authoring_script
    from asteria.editor import EditorDocument
    from asteria.project import Project

    ref = (
        Path(__file__).parents[1] / "reference_projects/complex_reference_rpg/project.asteria.json"
    )
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
    assert sequence.opcode == "SEQUENCE" and [t["name"] for t in sequence.args["tracks"]] == [
        "hero",
        "camera",
    ]
    assert project.common_events[-1] == CommonEvent("intro", "autorun", "intro_on")
    assert project.lifecycle_event_bindings[-1].once
    roundtrip = Project.from_data(project.to_data(), document.component_registry)
    assert roundtrip.common_events == project.common_events
    assert (
        roundtrip.lifecycle_event_bindings[-1].conditions
        == project.lifecycle_event_bindings[-1].conditions
    )


def test_a_sequence_runs_dialogue_and_music_tracks_in_parallel(runtime, resource_root):
    """EVT-04: dialogue and music are ordinary tracks of a SEQUENCE; the music starts while the
    line waits."""
    import shutil
    from pathlib import Path

    from asteria.runtime.audio_mixer import RecordingAudioDevice

    reference = (
        Path(__file__).resolve().parents[1] / "reference_projects" / "complex_reference_rpg"
    )
    shutil.copytree(
        reference / "playable_assets" / "audio", resource_root / "playable_assets" / "audio"
    )

    runtime.audio.device = device = RecordingAudioDevice()
    game = runtime.game
    runtime._ui_mode = "field"
    tracks = [
        track("talk", ("DIALOGUE", {"speaker": "Guide", "text": "The gate opens at dusk."})),
        track("music", W("PLAY_BGM", asset_id="battle_theme", fade=0.0)),
    ]
    _program(
        runtime,
        "scene_with_music",
        EventInstruction("SEQUENCE", {"tracks": tracks, "cutscene": False, "wait": "all"}),
        EventInstruction("SET_SWITCH", {"name": "scene_done", "value": True}),
    )
    game.events.start("scene_with_music")
    _frames(runtime, 3)
    assert (
        game.pending_dialogue is not None
        and game.pending_dialogue.line.text == "The gate opens at dusk."
    )
    assert any(
        call[0] == "play_music" and "battle_theme" in call[1] for call in device.calls
    )  # alongside the line
    assert not game.save.event_context.get_switch(
        "scene_done"
    )  # the sequence waits for every track
    _frames(runtime, 1, [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, mod=0)])
    _frames(runtime, 3)
    assert game.pending_dialogue is None and game.save.event_context.get_switch("scene_done")
    assert not game.event_errors


def test_entity_events_lists_the_scenes_people_and_objects_beside_the_events(window):
    editor = window.event_editor
    window.document.select_scene(window.viewport.current_scene())
    window.refresh_selection_context()
    scene = window.viewport.current_scene()
    assert editor.picker.count() == len(list(scene.entities())) > 0  # not an empty page
    assert not editor.body.isEnabled()  # greyed until one is picked
    first = editor.picker.item(0)
    assert "event" in first.text()  # how many events each one has, those with events first
    entity = first.data(0x0100)
    editor.picker.itemClicked.emit(first)
    assert window.document.selection.value is entity
    assert editor.body.isEnabled() and editor.picker.count() > 1  # the list stays
    assert editor.picker.currentItem().data(0x0100) is entity
    assert editor.title.text().startswith("Events — ")
    assert editor.trigger_combo.currentData() in ("action", "autorun", "parallel")
    assert editor.commands.item(0).text().startswith("◆")  # the commands as RPG Maker lists


def test_conditions_read_in_words_and_are_picked(window):
    from asteria.editor.events.flow_widget import describe_condition
    from asteria.editor.records.vocabulary import words
    from asteria.events.conditions import EventCondition as Condition

    names = {"warlord": "Crimson Warlord"}
    said = lambda *args: describe_condition(Condition(*args), names)  # noqa: E731
    assert said("battle", "hp_ratio:warlord", "<=", 0.5) == "Crimson Warlord HP % is at most 50 %"
    assert said("battle", "alive:warlord", "==", False) == "Crimson Warlord is down"
    assert said("battle", "round", ">=", 3) == "Round is at least 3"
    assert said("switch", "throne.hot", "==", True) == "Throne · Hot is on"
    assert said("switch", "throne.hot", "!=", True) == "Throne · Hot is off"
    assert said("variable", "gold", ">", 2.5) == "Gold is above 2.5"
    assert words("door.crypt.stairs_up") == "Door · Crypt · Stairs Up"
    assert words("v1.5") == "V1.5"

    panel = window.event_flow_editor
    panel.api.new_program("switch_on")
    panel.refresh()
    panel.cond_source.setCurrentText("switch")
    assert panel.cond_name.isEditable()
    panel.cond_name.setCurrentText("gate.open")
    panel.cond_flag.setCurrentText("false")
    assert panel.add_condition()
    assert panel._condition_values[-1] == Condition("switch", "gate.open", "==", False)
    panel.cond_source.setCurrentText("battle")
    assert not panel.cond_name.isEditable() and panel.cond_name.currentText() == "round"
    panel.cond_number.setValue(2)
    assert panel.add_condition()
    assert panel._condition_values[-1].value == 2
    assert panel.conditions.item(0).text() == "Gate · Open is off"
    panel.conditions.setCurrentRow(0)
    panel.remove_condition()
    assert [c.name for c in panel._condition_values] == ["round"]


def test_a_world_command_is_a_form_of_its_own_fields_and_loses_nothing(window):
    from asteria.editor.events.world_command_form import WorldCommandDialog, WorldCommandForm
    from asteria.runtime.session.world_commands import WORLD_COMMAND_ARGUMENTS

    form = WorldCommandForm(window.document)
    for command, keys in WORLD_COMMAND_ARGUMENTS.items():
        form.set_command(command)
        assert set(form.fields) == set(keys), command
    # records by their names, numbers unset until used, what no field holds still kept
    args = {"item_id": "x_not_listed", "quantity": 3, "their_own": "kept", "shaped": [1, 2]}
    form.set_command("GIVE_ITEM", args)
    assert form.result_args() == args and form.other.text() == "their_own=kept"
    assert form.fields["quantity"].value() == 3
    # another command keeps what the two share
    form.set_command("SET_POSITION", {"entity": "player", "x": 4})
    form.command.setCurrentText("WALK_TO")
    assert form.command_name() == "WALK_TO" and form.result_args()["entity"] == "player"
    # a walk is clicked, and reads back the way MOVE_ROUTE reads it
    form.set_command("MOVE_ROUTE", {"entity": "player"})
    for direction in ("up", "up", "left"):
        form.fields["route"].add(direction)
    assert form.result_args()["route"] == "up 2, left 1"
    # a name that must be there and can be anything comes ready made
    form.set_command("TIMER_START")
    assert form.result_args()["timer_id"] == "new_timer" and not form.missing()
    # the window refuses until what the engine needs is there
    dialog = WorldCommandDialog(window.document, command="MOVE_ROUTE", args={"entity": "player"})
    dialog.accept()
    assert "Route" in dialog.error.text()
    dialog.deleteLater()
    form.deleteLater()


def test_a_new_name_takes_one_click_and_stays_free(window):
    from asteria.editor.events.name_dialog import SwitchDialog, VariableDialog, name_picker
    from asteria.editor.ui.fit import ValueCombo

    combo = name_picker(window.document, "switch", "door_open")
    combo.setCurrentIndex(combo.findData(ValueCombo.NEW))
    assert combo.currentText() == "new_switch"
    combo.setCurrentIndex(combo.findData(ValueCombo.NEW))
    assert combo.currentText() == "new_switch_2"
    assert combo.itemData(combo.count() - 1) == ValueCombo.NEW

    picked = SwitchDialog(window.document, "Set Switch", name="door_open", value=False)
    assert (picked.name(), picked.value()) == ("door_open", False)
    copied = VariableDialog(window.document, args={"name": "gold", "from_variable": "score"})
    assert copied.result_args() == {"name": "gold", "from_variable": "score"}
    number = VariableDialog(window.document, args={"name": "gold", "value": 5})
    assert number.result_args() == {"name": "gold", "value": 5}
    text = VariableDialog(window.document, args={"name": "gold", "value": "5"})
    assert text.result_args() == {"name": "gold", "value": "5"}
    for dialog in (picked, copied, number, text):
        dialog.deleteLater()


def test_world_and_switch_commands_are_made_and_edited_by_dialogs(window, monkeypatch):
    from asteria.editor.project.workspace import WorkspaceMode

    window.workspace.set_mode(WorkspaceMode.EVENT)
    boss = next(
        e for e in window.document.project.scenes()[0].entities() if e.name == "Astral Tyrant"
    )
    window.document.selection.set_single("entity", boss)
    window.refresh_all()
    program = window.document.project.event_programs.require("boss_interaction_event")
    made = {"command": "GIVE_ITEM", "args": {"item_id": "herb"}}
    monkeypatch.setattr(window, "_world_dialog", lambda command="", args=None: made)
    window._event_add_command("world")
    program = window.document.project.event_programs.require("boss_interaction_event")
    index = next(i for i, x in enumerate(program.instructions) if x.args == made)
    changed = {"command": "GIVE_ITEM", "args": {"item_id": "herb", "quantity": 2}}
    monkeypatch.setattr(window, "_world_dialog", lambda command="", args=None: changed)
    assert window._event_edit_command(index)
    program = window.document.project.event_programs.require("boss_interaction_event")
    assert program.instructions[index].args["args"]["quantity"] == 2
    monkeypatch.setattr(window, "_switch_dialog", lambda *a, **k: ("gate", False))
    window._event_add_command("switch")
    program = window.document.project.event_programs.require("boss_interaction_event")
    added = next(x for x in program.instructions if x.opcode == "SET_SWITCH")
    assert added.args == {"name": "gate", "value": False}


def test_a_new_command_goes_before_the_end_and_rows_name_records(window, monkeypatch):
    from asteria.editor.events.editing import describe_instruction
    from asteria.editor.events.world_command_form import record_names
    from asteria.editor.project.workspace import WorkspaceMode
    from asteria.events import EventInstruction, EventProgram

    window.workspace.set_mode(WorkspaceMode.EVENT)
    boss = next(
        e for e in window.document.project.scenes()[0].entities() if e.name == "Astral Tyrant"
    )
    window.document.selection.set_single("entity", boss)
    window.refresh_all()
    programs = window.document.project.event_programs
    programs.replace(
        "boss_interaction_event", EventProgram([EventInstruction("END", {})], name="x")
    )
    window.refresh_all()
    monkeypatch.setattr(window, "_switch_dialog", lambda *a, **k: ("gate", True))
    window.event_editor.commands.clearSelection()
    window._event_add_command("switch")
    rows = programs.require("boss_interaction_event").instructions
    assert [x.opcode for x in rows] == ["SET_SWITCH", "END"]

    scene = window.document.project.scenes()[0]
    transfer = EventInstruction("WORLD", {"command": "TRANSFER", "args": {"scene_id": scene.id}})
    said = describe_instruction(transfer, record_names(window.document))
    assert scene.id not in said and "Scene: " in said


def test_a_sequence_step_is_edited_where_it_stands():
    from PySide6.QtWidgets import QApplication

    from asteria.editor.events.flow_widget import SequenceEditorDialog

    _app = QApplication.instance() or QApplication([])

    tracks = [
        {
            "name": "camera",
            "instructions": [
                {"opcode": "MOVE", "args": {"entity": "player", "x": 3, "y": 4, "note": "keep"}},
                {
                    "opcode": "WORLD",
                    "args": {
                        "command": "CAMERA_FOCUS",
                        "args": {"entity": "player", "zoom": 2.0},
                        "wait": 0.5,
                    },
                },
                {"opcode": "SOMETHING_ELSE", "args": {"a": 1}},
            ],
        }
    ]
    dialog = SequenceEditorDialog({"tracks": tracks})
    try:
        assert not dialog.update_step_button.isEnabled()  # nothing selected yet
        dialog.steps.setCurrentRow(0)
        assert dialog.opcode.currentText() == "MOVE" and dialog.fields["x"].text() == "3"
        dialog.fields["x"].setText(9)
        dialog._update_step_clicked()
        step = dialog.current_track["instructions"][0]
        assert step["args"]["x"] == 9 and step["args"]["y"] == 4 and step["args"]["note"] == "keep"
        assert dialog.steps.currentRow() == 0 and len(dialog.current_track["instructions"]) == 3

        dialog.steps.setCurrentRow(1)
        assert dialog.world.command_name() == "CAMERA_FOCUS"
        assert dialog.fields["wait"].text() == "0.5"
        dialog._update_step_clicked()  # unchanged: as it was
        assert dialog.current_track["instructions"][1] == tracks[0]["instructions"][1]

        dialog.steps.setCurrentRow(2)  # a kind the form doesn't have: left alone
        assert not dialog.update_step_button.isEnabled()
    finally:
        dialog.close()


def test_an_if_command_is_edited_and_keeps_its_jump():
    from types import SimpleNamespace

    from asteria.editor.shell import AsteriaEditorWindow

    edit = AsteriaEditorWindow._edited_event_command
    window = SimpleNamespace(_switch_dialog=lambda title, name, value: (name + "_2", not value))
    condition = {
        "source": "switch", "name": "door", "operator": "==", "value": True, "scope_id": None,
    }  # fmt: skip
    jump = EventInstruction("JUMP_IF", {"condition": condition, "label": "out"})
    edited = edit(window, jump)
    assert edited.opcode == "JUMP_IF" and edited.args["label"] == "out"
    assert edited.args["condition"] == dict(condition, name="door_2", value=False)
    other = dict(condition, source="variable", operator=">")
    assert edit(window, EventInstruction("JUMP_IF", {"condition": other, "label": "x"})) is None
    window._switch_dialog = lambda *_args: None  # cancelled
    assert not edit(window, jump)
