import pytest

from asteria.presentation.attachment_runtime import AttachmentRuntime, AttachmentState
from asteria.presentation.attachments import Attachment, Socket, SocketKey, SocketRig, Transform2D


def T(x=0, y=0, r=0, sx=1, sy=1, **kw):
    return Transform2D(x, y, r, sx, sy, **kw)


def rig():
    r = SocketRig()
    r.add(Socket("root", default=T(10, 20)))
    r.add(Socket("hand", parent="root", default=T(5, 0)))
    return r


def test_attach_and_resolve_world_chain():
    rt = AttachmentRuntime(rig(), root_transform=T(100, 200))
    rt.attach(Attachment("held", "asset.any", "hand", local=T(2, 3)))
    p = rt.resolve("held", 0).transform
    assert (p.x, p.y) == pytest.approx((117, 223))


def test_rotation_affects_child_position():
    r = SocketRig()
    r.add(Socket("root", default=T(0, 0, 90)))
    r.add(Socket("tip", parent="root", default=T(10, 0)))
    p = AttachmentRuntime(r).socket_world_transform("tip", 0)
    assert p.x == pytest.approx(0, abs=1e-7) and p.y == pytest.approx(10)


def test_scale_affects_child_position_and_scale():
    r = SocketRig()
    r.add(Socket("root", default=T(0, 0, 0, 2, 3)))
    r.add(Socket("tip", parent="root", default=T(4, 5)))
    p = AttachmentRuntime(r).socket_world_transform("tip", 0)
    assert (p.x, p.y, p.scale_x, p.scale_y) == pytest.approx((8, 15, 2, 3))


def test_keyed_socket_is_sampled_at_runtime():
    r = SocketRig()
    r.add(Socket("hand", keys=(SocketKey(0, T(0)), SocketKey(2, T(10)))))
    rt = AttachmentRuntime(r)
    rt.attach(Attachment("x", "asset", "hand"))
    assert rt.resolve("x", 1).transform.x == pytest.approx(5)


def test_generic_assets_not_equipment_specific():
    rt = AttachmentRuntime(rig())
    rt.attach_many([Attachment("hat", "sprite.hat", "root"), Attachment("aura", "vfx.aura", "root")])
    assert {x.asset_id for x in rt.resolve_all(0)} == {"sprite.hat", "vfx.aura"}


def test_duplicate_active_rejected():
    rt = AttachmentRuntime(rig())
    a = Attachment("x", "a", "root")
    rt.attach(a)
    with pytest.raises(ValueError):
        rt.attach(a)


def test_detach_lifecycle():
    rt = AttachmentRuntime(rig())
    rt.attach(Attachment("x", "a", "root"))
    out = rt.detach("x")
    assert out.state == AttachmentState.DETACHED
    with pytest.raises(KeyError):
        rt.resolve("x", 0)


def test_visibility_does_not_destroy_attachment():
    rt = AttachmentRuntime(rig())
    rt.attach(Attachment("x", "a", "root"))
    rt.set_visible("x", False)
    out = rt.resolve("x", 0)
    assert out.state == AttachmentState.HIDDEN and not out.transform.visible
    rt.set_visible("x", True)
    assert rt.resolve("x", 0).transform.visible


def test_swap_preserves_stable_id_and_changes_asset():
    rt = AttachmentRuntime(rig())
    rt.attach(Attachment("held", "sword", "hand"))
    rt.swap("held", Attachment("held", "lantern", "hand"))
    assert rt.resolve("held", 0).asset_id == "lantern"


def test_swap_rejects_id_change():
    rt = AttachmentRuntime(rig())
    rt.attach(Attachment("held", "sword", "hand"))
    with pytest.raises(ValueError):
        rt.swap("held", Attachment("other", "axe", "hand"))


def test_inheritance_can_be_disabled():
    r = SocketRig()
    r.add(Socket("s", default=T(50, 60, 90, 2, 2, opacity=0.5)))
    rt = AttachmentRuntime(r)
    rt.attach(
        Attachment(
            "x",
            "a",
            "s",
            local=T(3, 4, 10, 1, 1, opacity=0.8),
            inherit_position=False,
            inherit_rotation=False,
            inherit_scale=False,
            inherit_opacity=False,
        )
    )
    p = rt.resolve("x", 0).transform
    assert (p.x, p.y, p.rotation_deg, p.scale_x, p.opacity) == pytest.approx((3, 4, 10, 1, 0.8))


def test_z_sorted_resolution_is_deterministic():
    rt = AttachmentRuntime(rig())
    rt.attach(Attachment("back", "b", "root", local=T(z_offset=-2)))
    rt.attach(Attachment("front", "f", "root", local=T(z_offset=3)))
    assert [x.id for x in rt.resolve_all(0)] == ["back", "front"]


def test_callbacks_receive_lifecycle():
    rt = AttachmentRuntime(rig())
    events = []
    rt.on_attach(lambda x: events.append(("a", x.spec.id)))
    rt.on_detach(lambda x: events.append(("d", x.spec.id)))
    rt.attach(Attachment("x", "a", "root"))
    rt.detach("x")
    assert events == [("a", "x"), ("d", "x")]


def test_attach_many_preflight_is_transactional():
    rt = AttachmentRuntime(rig())
    rt.attach(Attachment("x", "old", "root"))
    with pytest.raises(ValueError):
        rt.attach_many([Attachment("y", "new", "root"), Attachment("x", "bad", "root")])
    assert "y" not in rt.instances


def test_snapshot_restore_runtime_visibility_and_data():
    rt = AttachmentRuntime(rig())
    i = rt.attach(Attachment("x", "a", "root"))
    i.runtime_data["phase"] = 3
    rt.set_visible("x", False)
    snap = rt.snapshot()
    rt2 = AttachmentRuntime(rig())
    rt2.attach(Attachment("x", "a", "root"))
    rt2.restore_runtime_state(snap)
    assert rt2.instances["x"].state == AttachmentState.HIDDEN and rt2.instances["x"].runtime_data == {"phase": 3}


def test_pivot_is_applied():
    r = SocketRig()
    r.add(Socket("s", pivot_x=2, pivot_y=3, default=T(10, 20)))
    p = AttachmentRuntime(r).socket_world_transform("s", 0)
    assert (p.x, p.y) == pytest.approx((12, 23))


def test_unknown_socket_rejected_on_attach():
    with pytest.raises(ValueError):
        AttachmentRuntime(rig()).attach(Attachment("x", "a", "missing"))


def test_detached_visibility_change_rejected():
    rt = AttachmentRuntime(rig())
    rt.attach(Attachment("x", "a", "root"))
    rt.detach("x")
    with pytest.raises(KeyError):
        rt.set_visible("x", True)
