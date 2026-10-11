"""CB10 / EDT-08: VFX tool — placement the battle renderer reads, import, usage, preview, GUI."""

from pathlib import Path

import pytest

from asteria.editor import EditorDocument
from asteria.editor.vfx_authoring import PREVIEW_BODY_HEIGHT, VFXAuthoringController, VFXAuthoringError
from asteria.project import Project
from asteria.runtime.battle_visuals import VFX_DEFAULTS, vfx_keyframe, vfx_placement, vfx_rect

REF = Path(__file__).parents[1] / "reference_projects/complex_reference_rpg/project.asteria.json"


@pytest.fixture
def api():
    document = EditorDocument()
    document.set_project(Project.load_json(REF, document.component_registry), file_path=REF)
    return VFXAuthoringController(document)


def test_placement_rule_defaults_keep_the_original_battle_look():
    placement = vfx_placement({})
    assert placement == {**VFX_DEFAULTS, "offset": [0.0, 0.0]}
    assert vfx_rect(placement, 100, 200, 80, 64, 64) == (100, 160, 64 * 0.6, 64 * 0.6)  # mid-body, 0.6 scale
    head = vfx_placement({"vfx": {"anchor": "head", "offset": [4, -2], "scale": 1}}, {"scale": 2})
    assert vfx_rect(head, 100, 200, 80, 10, 10) == (104, 118, 20, 20)  # beat payload overrides the sheet
    assert [vfx_keyframe(t, 1.0, 4) for t in (0, 0.26, 0.5, 0.99, 5)] == [0, 1, 2, 3, 3]


def test_vfx_list_usage_and_checks_on_the_reference_project(api):
    assert api.vfx_ids() == ("battle.fx.explosion", "battle.fx.flame", "battle.fx.heal", "battle.fx.slash")
    assert "fire_arc" in {sequence for sequence, _ in api.usages("battle.fx.flame")}
    assert all(api.problems(x) == [] for x in api.vfx_ids())


def test_placement_edits_are_undoable_and_validated(api):
    document = api.document
    assert api.set_placement("battle.fx.flame", anchor="feet", offset=(0, -12), scale=1.2, blend="add", opacity=0.8)
    assert api.placement("battle.fx.flame") == {
        "anchor": "feet",
        "offset": [0.0, -12.0],
        "scale": 1.2,
        "opacity": 0.8,
        "blend": "add",
    }
    preview = api.preview("battle.fx.flame", 0.0)
    assert preview.rect == (0.0, -12.0, 75 * 1.2, 90 * 1.2) and preview.keyframe == 0
    document.undo()
    assert api.placement("battle.fx.flame")["anchor"] == "center"
    for bad, match in (
        ({"anchor": "tail"}, "anchor"),
        ({"blend": "screen"}, "blend"),
        ({"scale": 0}, "scale"),
        ({"opacity": 2}, "opacity"),
        ({"glow": 1}, "unknown"),
    ):
        with pytest.raises(VFXAuthoringError, match=match):
            api.set_placement("battle.fx.flame", **bad)


def test_preview_follows_the_runtime_frame_rule(api):
    duration = api.duration("battle.fx.explosion")
    frames = api.animation.data("battle.fx.explosion")["clips"]["play"]["frames"]
    for age in (0.0, duration * 0.5, duration * 0.99):
        expected = frames[vfx_keyframe(age, duration, len(frames))]
        assert api.preview("battle.fx.explosion", age).frame_index == expected
    assert api.preview("battle.fx.explosion", 0.0).rect[1] == -PREVIEW_BODY_HEIGHT * 0.5


def _tmp_api(tmp_path):
    from PIL import Image

    project_dir, outside = tmp_path / "game", tmp_path / "downloads"
    project_dir.mkdir()
    outside.mkdir()
    Image.new("RGBA", (96, 32), (255, 200, 0, 255)).save(outside / "spark.png")
    document = EditorDocument()
    path = project_dir / "p.asteria.json"
    document.set_project(Project.load_json(REF, document.component_registry), file_path=path)
    return VFXAuthoringController(document), project_dir, outside


def test_import_copies_the_image_and_adds_a_play_once_vfx(tmp_path):
    api, project_dir, outside = _tmp_api(tmp_path)
    document = api.document
    api.import_sheet("battle.fx.spark", outside / "spark.png", 32, 32, frame_duration=0.05)
    assert (project_dir / "assets" / "vfx" / "spark.png").is_file()
    assert api.asset("battle.fx.spark").source.uri == "assets/vfx/spark.png"
    assert "battle.fx.spark" in api.vfx_ids() and api.problems("battle.fx.spark") == []
    assert api.duration("battle.fx.spark") == pytest.approx(0.15)
    assert [api.preview("battle.fx.spark", t).frame_index for t in (0, 0.06, 0.12)] == [0, 1, 2]
    with pytest.raises(VFXAuthoringError, match="whole grid"):
        api.import_sheet("battle.fx.bad", outside / "spark.png", 40, 32)
    with pytest.raises(VFXAuthoringError, match="already exists"):
        api.import_sheet("battle.fx.spark", outside / "spark.png", 32, 32)
    document.undo()
    assert "battle.fx.spark" not in api.vfx_ids()


def test_a_cued_vfx_cannot_be_unmarked_but_an_unused_one_can(tmp_path):
    api, _, outside = _tmp_api(tmp_path)
    with pytest.raises(VFXAuthoringError, match="cued by action timelines"):
        api.mark_as_vfx("battle.fx.flame", False)
    unused = api.import_sheet("battle.fx.spark", outside / "spark.png", 32, 32).asset_id
    api.mark_as_vfx(unused, False)
    assert unused in api.other_sheets()
    api.mark_as_vfx(unused, True)
    assert unused in api.vfx_ids()


def test_the_battle_renderer_draws_with_the_authored_placement(resource_root, monkeypatch):
    pytest.importorskip("pygame")
    from dataclasses import replace

    from test_canonical_battle_presentation import _settle, _use
    from test_playable_battle_loop import _boss_runtime

    from asteria.runtime.battle_presentation_adapters import CanonicalBattleAdapter

    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    runtime = _boss_runtime(resource_root)
    try:
        assets = runtime.game.project.assets
        flame = assets.resolve("battle.fx.flame")
        meta = {**flame.meta(), "vfx": {"anchor": "feet", "scale": 1.2, "opacity": 0.5, "blend": "add"}}
        assets.register(replace(flame, metadata=tuple(sorted(meta.items()))), replace=True)
        runtime._battle_presentation = adapter = CanonicalBattleAdapter(runtime)
        runtime.game.start_encounter("boss_room")
        adapter.begin()
        runtime._advance_to_hero_turn()
        runtime._present_battle(0.016)
        _settle(runtime)
        drawn = []
        original = adapter.textures.blit_region

        def record(asset_id, source, x, y, width, height, **kwargs):
            if asset_id == "battle.fx.flame":
                drawn.append((width, height, kwargs))
            return original(asset_id, source, x, y, width, height, **kwargs)

        adapter.textures.blit_region = record
        _use(runtime, "fire_arc")
        runtime._present_battle(0.0)  # the frame that consumes the action
        clock = 0.0
        while adapter.busy() and clock < 2.0 and not drawn:
            runtime._present_battle(0.02)
            clock += 0.02
        assert drawn, "the flame VFX was never drawn"
        width, height, kwargs = drawn[0]
        assert (width, height) == pytest.approx((75 * 1.2, 90 * 1.2))
        assert kwargs == {"opacity": 0.5, "blend": "add"}
    finally:
        runtime.close()


@pytest.fixture
def window():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from asteria.editor.shell import AsteriaEditorWindow

    app = QApplication.instance() or QApplication([])
    value = AsteriaEditorWindow(None)
    value.document.set_project(Project.load_json(REF, value.document.component_registry), file_path=REF)
    value.refresh_all()
    yield value
    value.document.mark_saved()
    value.close()
    app.processEvents()


def test_vfx_tab_previews_applies_and_links_to_the_timeline_and_animation_editor(window):
    widget = window.vfx_editor
    assert window.ui_workspace.tabText(window.ui_workspace.indexOf(widget)) == "Battle Effects"
    assert widget.select_vfx("battle.fx.flame")
    assert widget.problems.item(0).text() == "No problems" and widget.usages.count() >= 1
    widget.anchor.setCurrentText("head")
    widget.scale.setValue(1.0)
    rect = widget._render()  # unsaved form values preview immediately
    assert rect == (0.0, -PREVIEW_BODY_HEIGHT, 75.0, 90.0)
    assert widget.api.placement("battle.fx.flame")["anchor"] == "center"
    assert widget.apply_placement() and widget.api.placement("battle.fx.flame")["anchor"] == "head"
    widget.scrub.setValue(500)
    assert "frame" in widget.time_label.text() and not widget.stage.pixmap.isNull()
    widget.toggle_play()
    widget.tick(0.1)
    assert widget.playing and widget.scrub.value() != 500
    widget.toggle_play()
    sequence = widget.usages.item(0).text().split(".", 1)[0]
    widget.openTimeline.emit(sequence)
    assert window.action_timeline_editor.sequence_id == sequence
    widget.openAnimation.emit("battle.fx.flame")
    assert window.animation_editor.sheet == "battle.fx.flame"
    window.document.undo()
    assert widget.api.placement("battle.fx.flame")["anchor"] == "center"
