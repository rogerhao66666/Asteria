import pytest

from asteria.editor.asset_attachment import AssetAttachmentController, AssetDragPayload, AttachmentDropRequest
from asteria.editor.attachment_authoring import AttachmentAuthoringModel
from asteria.presentation.attachments import Socket, Transform2D


def setup():
    m = AttachmentAuthoringModel()
    m.add_socket(Socket("hand"))
    m.add_socket(Socket("head"))
    return m, AssetAttachmentController(m, lambda aid: aid in {"asset.sword", "asset.hat", "asset.vfx"})


def test_drop_asset_reference_on_socket():
    m, c = setup()
    a = c.drop(AttachmentDropRequest(AssetDragPayload("asset.sword", "sprite"), "hand", "held"))
    assert a.asset_id == "asset.sword" and m.preview()[0].socket_id == "hand"


def test_drop_preserves_local_transform_and_inheritance():
    m, c = setup()
    a = c.drop(
        AttachmentDropRequest(
            AssetDragPayload("asset.hat"), "head", "hat", local=Transform2D(x=2), inherit_rotation=False
        )
    )
    assert a.local.x == 2 and not a.inherit_rotation


def test_payload_metadata_and_drop_metadata_merge():
    m, c = setup()
    a = c.drop(
        AttachmentDropRequest(
            AssetDragPayload("asset.vfx", "vfx", {"source": "browser"}), "hand", "fx", metadata={"project": "x"}
        )
    )
    assert a.metadata["source"] == "browser" and a.metadata["project"] == "x" and a.metadata["asset_kind"] == "vfx"


def test_unknown_socket_rejected_without_mutation():
    m, c = setup()
    with pytest.raises(ValueError):
        c.drop(AttachmentDropRequest(AssetDragPayload("asset.sword"), "missing", "x"))
    assert not m.preview()


def test_unknown_asset_rejected_when_registry_check_available():
    m, c = setup()
    with pytest.raises(ValueError):
        c.drop(AttachmentDropRequest(AssetDragPayload("missing"), "hand", "x"))


def test_controller_can_operate_without_registry_callback():
    m = AttachmentAuthoringModel()
    m.add_socket(Socket("x"))
    c = AssetAttachmentController(m)
    assert c.can_drop(AssetDragPayload("project.custom"), "x") == (True, None)


def test_move_attachment_between_sockets():
    m, c = setup()
    c.drop(AttachmentDropRequest(AssetDragPayload("asset.hat"), "head", "x"))
    c.move_attachment("x", "hand")
    assert m.preview()[0].socket_id == "hand"


def test_move_is_undoable():
    m, c = setup()
    c.drop(AttachmentDropRequest(AssetDragPayload("asset.hat"), "head", "x"))
    c.move_attachment("x", "hand")
    assert m.undo()
    assert m.preview()[0].socket_id == "head"


def test_drop_is_undoable():
    m, c = setup()
    c.drop(AttachmentDropRequest(AssetDragPayload("asset.sword"), "hand", "x"))
    assert m.undo() and not m.preview()


def test_asset_kind_is_advisory_not_hardcoded():
    m, c = setup()
    a = c.drop(AttachmentDropRequest(AssetDragPayload("asset.vfx", "totally_custom_kind"), "hand", "x"))
    assert a.metadata["asset_kind"] == "totally_custom_kind"
