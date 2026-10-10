import pytest

from asteria.presentation.attachment_commands import AttachmentCommandExecutor
from asteria.presentation.attachment_runtime import AttachmentRuntime, AttachmentState
from asteria.presentation.attachments import Socket, SocketRig
from asteria.presentation.bridge import ExecutorRegistry, PresentationRunner
from asteria.presentation.canonical import Command, Kind, Node, Sequence
from asteria.presentation.runtime import Runtime


def rig_runtime():
    rig = SocketRig()
    rig.add(Socket("root"))
    rig.add(Socket("hand", parent="root"))
    rig.add(Socket("head", parent="root"))
    return AttachmentRuntime(rig)


def cmd(action, **args):
    return Command("attachment", action, args)


def dispatch(ex, action, **args):
    return ex.dispatch("n", cmd(action, **args))


def test_attach_generic_visual():
    rt = rig_runtime()
    ex = AttachmentCommandExecutor(rt)
    dispatch(ex, "attach", attachment_id="visual", asset_id="project.anything", socket_id="hand")
    assert rt.resolve("visual", 0).asset_id == "project.anything"


def test_attach_local_transform_and_metadata():
    rt = rig_runtime()
    ex = AttachmentCommandExecutor(rt)
    dispatch(
        ex,
        "attach",
        attachment_id="a",
        asset_id="x",
        socket_id="head",
        local={"x": 3, "rotation_deg": 20, "opacity": 0.5},
        metadata={"tag": "demo"},
    )
    r = rt.resolve("a", 0)
    assert (
        r.transform.x == 3
        and r.transform.rotation_deg == 20
        and r.transform.opacity == 0.5
        and r.metadata["tag"] == "demo"
    )


def test_hide_show():
    rt = rig_runtime()
    ex = AttachmentCommandExecutor(rt)
    dispatch(ex, "attach", attachment_id="a", asset_id="x", socket_id="hand")
    dispatch(ex, "hide", attachment_id="a")
    assert rt.instances["a"].state == AttachmentState.HIDDEN
    dispatch(ex, "show", attachment_id="a")
    assert rt.instances["a"].state == AttachmentState.ACTIVE


def test_detach():
    rt = rig_runtime()
    ex = AttachmentCommandExecutor(rt)
    dispatch(ex, "attach", attachment_id="a", asset_id="x", socket_id="hand")
    dispatch(ex, "detach", attachment_id="a")
    assert rt.instances["a"].state == AttachmentState.DETACHED


def test_swap_preserves_stable_id_and_changes_asset_socket():
    rt = rig_runtime()
    ex = AttachmentCommandExecutor(rt)
    dispatch(ex, "attach", attachment_id="slot", asset_id="old", socket_id="hand")
    dispatch(ex, "swap", attachment_id="slot", asset_id="new", socket_id="head")
    r = rt.resolve("slot", 0)
    assert (r.id, r.asset_id, r.socket_id) == ("slot", "new", "head")


def test_replace_attach_supported_explicitly():
    rt = rig_runtime()
    ex = AttachmentCommandExecutor(rt)
    dispatch(ex, "attach", attachment_id="a", asset_id="old", socket_id="hand")
    dispatch(ex, "attach", attachment_id="a", asset_id="new", socket_id="head", replace=True)
    assert rt.resolve("a", 0).asset_id == "new"


def test_duplicate_attach_rejected_without_replace():
    rt = rig_runtime()
    ex = AttachmentCommandExecutor(rt)
    dispatch(ex, "attach", attachment_id="a", asset_id="old", socket_id="hand")
    with pytest.raises(ValueError):
        dispatch(ex, "attach", attachment_id="a", asset_id="new", socket_id="hand")


def test_unknown_action_rejected():
    with pytest.raises(ValueError):
        dispatch(AttachmentCommandExecutor(rig_runtime()), "equip_magic_hat", attachment_id="a")


def test_missing_required_attach_fields_rejected():
    ex = AttachmentCommandExecutor(rig_runtime())
    with pytest.raises(ValueError):
        dispatch(ex, "attach", asset_id="x", socket_id="hand")
    with pytest.raises(ValueError):
        dispatch(ex, "attach", attachment_id="a", socket_id="hand")
    with pytest.raises(ValueError):
        dispatch(ex, "attach", attachment_id="a", asset_id="x")


def test_blocking_command_completes_immediately():
    ex = AttachmentCommandExecutor(rig_runtime())
    signals = ex.dispatch(
        "node42",
        Command("attachment", "attach", {"attachment_id": "a", "asset_id": "x", "socket_id": "hand"}, blocking=True),
    )
    assert [s.name for s in signals] == ["command.completed:node42"]


def test_executor_update_is_idle_and_validates_dt():
    ex = AttachmentCommandExecutor(rig_runtime())
    assert ex.update(16) == ()
    with pytest.raises(ValueError):
        ex.update(-1)


def test_presentation_runner_end_to_end_attach_then_swap_then_hide():
    rt = rig_runtime()
    ex = AttachmentCommandExecutor(rt)
    reg = ExecutorRegistry()
    reg.register("attachment", ex)
    nodes = (
        Node("attach", Kind.COMMAND, command=cmd("attach", attachment_id="held", asset_id="sword", socket_id="hand")),
        Node("swap", Kind.COMMAND, command=cmd("swap", attachment_id="held", asset_id="staff", socket_id="hand")),
        Node("hide", Kind.COMMAND, command=cmd("hide", attachment_id="held")),
    )
    seq = Sequence("composition", Node("root", Kind.SEQUENCE, children=nodes))
    runner = PresentationRunner(Runtime(seq), reg)
    runner.update(0)
    assert (
        runner.completed
        and rt.instances["held"].spec.asset_id == "staff"
        and rt.instances["held"].state == AttachmentState.HIDDEN
    )


def test_context_binding_can_choose_asset_at_runtime():
    from asteria.presentation.canonical import Context

    rt = rig_runtime()
    ex = AttachmentCommandExecutor(rt)
    reg = ExecutorRegistry()
    reg.register("attachment", ex)
    node = Node(
        "a", Kind.COMMAND, command=cmd("attach", attachment_id="held", asset_id="$param.visual", socket_id="hand")
    )
    runner = PresentationRunner(
        Runtime(Sequence("s", node), context=Context(parameters={"visual": "project.dynamic"})), reg
    )
    runner.update(0)
    assert rt.resolve("held", 0).asset_id == "project.dynamic"


def test_commands_have_no_gameplay_specific_vocabulary():
    rt = rig_runtime()
    ex = AttachmentCommandExecutor(rt)
    for asset in ("hat.blue", "wing.left", "vfx.aura", "prop.lantern"):
        aid = asset.replace(".", "_")
        dispatch(ex, "attach", attachment_id=aid, asset_id=asset, socket_id="head")
    assert {r.asset_id for r in rt.resolve_all(0)} == {"hat.blue", "wing.left", "vfx.aura", "prop.lantern"}
