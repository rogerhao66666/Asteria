"""Authoring edits replace validated Skeleton snapshots and support one-step undo."""

import json

import pytest

from asteria.editor.commands import CommandStack, SetSkeletonCommand
from asteria.graphics.skeleton import Bone, Key, Skeleton, SkeletonClip, Slot
from asteria.graphics.skeleton_data import load_skeleton, save_skeleton


def sample_skeleton():
    clip = SkeletonClip(
        "walk",
        1.0,
        tracks={("arm", "rotation"): (Key(0.0, 0), Key(1.0, 30, "ease_out"))},
    )
    return Skeleton(
        "hero",
        (Bone("root"), Bone("arm", "root", length=12)),
        (Slot("body", "root", "sheet", frame=0),),
        {"walk": clip},
    )


class SkeletonTarget:
    def __init__(self, skeleton):
        self.skeleton = skeleton

    def set_skeleton(self, skeleton):
        self.skeleton = skeleton


def test_skeleton_json_round_trip_uses_native_asteria_format(tmp_path):
    path = tmp_path / "hero.skeleton.json"
    original = sample_skeleton()

    save_skeleton(path, original)
    loaded = load_skeleton(path)

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["schema"] == "asteria.skeleton"
    assert loaded.skeleton_id == "hero"
    assert loaded.bones == original.bones
    assert loaded.slots == original.slots
    assert loaded.clips == original.clips


def test_bone_edit_commands_apply_undo_and_redo_as_single_steps():
    from asteria.editor.skeleton_editing import (
        add_bone,
        delete_bone,
        edit_bone,
    )

    original = sample_skeleton()
    target = SkeletonTarget(original)
    stack = CommandStack()

    added = add_bone(original, Bone("hand", "arm", x=2, length=4))
    target.skeleton = added
    stack.record_applied(SetSkeletonCommand(target, added, original, "Add bone"))
    assert target.skeleton.bones[-1].bone_id == "hand"
    assert stack.undo() and target.skeleton is original
    assert stack.redo() and target.skeleton is added

    edited = edit_bone(added, "arm", bone_id="upper_arm", x=8, scale_y=1.5)
    assert edited.bones[1].bone_id == "upper_arm"
    assert edited.bones[2].parent == "upper_arm"
    assert edited.clips["walk"].tracks[0][0][0] == "upper_arm"
    assert edited.bones[1].x == 8 and edited.bones[1].scale_y == 1.5

    deleted = delete_bone(edited, "upper_arm")
    assert [bone.bone_id for bone in deleted.bones] == ["root"]
    assert not deleted.slots or all(slot.bone_id in {"root"} for slot in deleted.slots)


def test_keyframe_edit_can_add_move_edit_easing_and_delete():
    from asteria.editor.skeleton_editing import set_key

    original = sample_skeleton()
    moved = set_key(original, "walk", "arm", "rotation", 1.0, time=0.5)
    clip = moved.clips["walk"]
    assert [
        (key.time, key.value, key.easing) for key in dict(clip.tracks)[("arm", "rotation")]
    ] == [
        (0.0, 0.0, "linear"),
        (0.5, 30.0, "ease_out"),
    ]

    changed = set_key(moved, "walk", "arm", "rotation", 0.5, value=45, easing="ease_in")
    assert dict(changed.clips["walk"].tracks)[("arm", "rotation")][-1] == Key(0.5, 45, "ease_in")
    deleted = set_key(changed, "walk", "arm", "rotation", 0.5, delete=True)
    assert len(dict(deleted.clips["walk"].tracks)[("arm", "rotation")]) == 1


def test_reparent_reorders_bones_and_rejects_parent_that_would_make_a_cycle():
    from asteria.editor.skeleton_editing import edit_bone

    original = sample_skeleton()
    moved = edit_bone(original, "arm", parent="")
    assert [bone.bone_id for bone in moved.bones] == ["root", "arm"]
    assert moved.bones[1].parent == ""
    with pytest.raises(ValueError, match="parent is missing or creates a cycle"):
        edit_bone(original, "root", parent="arm")


@pytest.fixture(scope="module")
def app():
    widgets = pytest.importorskip("PySide6.QtWidgets")
    return widgets.QApplication.instance() or widgets.QApplication([])


def test_skeleton_widget_edits_bones_and_keys_through_command_stack(app):
    from asteria.editor.skeleton_widget import SkeletonViewerWidget

    widget = SkeletonViewerWidget()
    widget.set_skeleton(sample_skeleton())
    try:
        widget.bone_combo.setCurrentText("arm")
        widget.bone_name.setText("upper_arm")
        widget.bone_x.setValue(8)
        widget.bone_scale_y.setValue(1.5)
        widget.apply_bone_button.click()
        assert widget.skeleton.bones[1].bone_id == "upper_arm"
        assert widget.command_stack.can_undo
        assert widget.command_stack.undo()
        assert widget.skeleton.bones[1].bone_id == "arm"
        assert widget.command_stack.redo()

        widget.track_bone.setCurrentText("upper_arm")
        widget.track_channel.setCurrentText("rotation")
        widget.key_time.setValue(0.5)
        widget.key_value.setValue(40)
        widget.key_easing.setCurrentText("ease_in")
        widget.save_key_button.click()
        keys = dict(widget.skeleton.clips["walk"].tracks)[("upper_arm", "rotation")]
        assert Key(0.5, 40, "ease_in") in keys
        assert widget.command_stack.undo()
        assert (
            Key(0.5, 40, "ease_in")
            not in dict(widget.skeleton.clips["walk"].tracks)[("upper_arm", "rotation")]
        )
    finally:
        widget.close()


def test_skeleton_widget_saves_and_reopens_native_project_json(app, tmp_path):
    from asteria.editor.skeleton_widget import SkeletonViewerWidget

    path = tmp_path / "hero.asteria.skeleton.json"
    widget = SkeletonViewerWidget()
    loaded = SkeletonViewerWidget()
    widget.set_skeleton(sample_skeleton())
    try:
        assert widget.save_rig(path)
        assert loaded.open_rig(path)
        assert loaded.skeleton.clips == widget.skeleton.clips
        assert loaded.skeleton.slots == widget.skeleton.slots
    finally:
        widget.close()
        loaded.close()


def test_skeleton_preview_draws_slot_sprite_through_runtime_adapter(app, tmp_path):
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QColor, QImage, QPainter

    from asteria.assets import AssetRecord, AssetRef
    from asteria.editor.model import EditorDocument
    from asteria.editor.skeleton_widget import SkeletonViewerWidget
    from asteria.graphics import SpriteFrame, SpriteSheet

    texture = QImage(4, 4, QImage.Format_ARGB32)
    texture.fill(QColor("lime"))
    assert texture.save(str(tmp_path / "sprite.png"))
    from asteria.project import Project

    project = Project("Rig preview")
    record = project.assets.add(
        AssetRecord.create(kind="texture", source_path="sprite.png", name="Sprite")
    )
    document = EditorDocument(project, file_path=tmp_path / "project.asteria")
    document.asset_views.set_sprite_sheet(
        "sheet", SpriteSheet(AssetRef(record.id), [SpriteFrame(0, 0, 4, 4)])
    )
    rig = Skeleton("preview", (Bone("root", length=10),), (Slot("body", "root", "sheet"),))
    widget = SkeletonViewerWidget(document=document)
    widget.resize(320, 500)
    widget.set_skeleton(rig)
    widget.canvas.resize(300, 200)
    widget.show()
    app.processEvents()
    try:
        draws = widget.canvas.texture_draws()
        assert len(draws) == 1
        assert draws[0].texture_asset_id == record.id
        assert draws[0].source == (0, 0, 4, 4)

        output = QImage(widget.canvas.size(), QImage.Format_ARGB32)
        output.fill(QColor("black"))
        painter = QPainter(output)
        widget.canvas.render(painter, QPoint())
        painter.end()
        sample_x = round(draws[0].screen_x + 4)
        sample_y = round(draws[0].screen_y + draws[0].height / 2)
        assert output.pixelColor(sample_x, sample_y) == QColor("lime")
    finally:
        widget.close()
