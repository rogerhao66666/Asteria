from asteria.presentation.action_binding import (
    ActionPresentationBinder,
    ActionPresentationRequest,
    AfterAction,
    VisualResource,
)
from asteria.presentation.attachment_commands import AttachmentCommandExecutor
from asteria.presentation.attachment_runtime import AttachmentRuntime, AttachmentState
from asteria.presentation.attachments import GripTransform, Socket, SocketRig, Transform2D


def rig():
    r = SocketRig()
    r.add(Socket("hand_r", default=Transform2D(x=24, y=20, rotation_deg=30)))
    return r


def sword(asset="iron_sword", x=8):
    return VisualResource(asset, "hand_r", GripTransform(x=x, y=3, rotation_deg=15), render_layer="held")


def run_attachment_commands(rt, commands):
    ex = AttachmentCommandExecutor(rt)
    for i, c in enumerate(commands):
        if c.channel == "attachment":
            ex.dispatch(str(i), c)


def test_action_can_select_visual_and_motion_without_gameplay_semantics():
    p = ActionPresentationBinder().plan(ActionPresentationRequest("basic_attack", "one_hand_slash", sword()))
    assert [(c.channel, c.action) for c in p.begin] == [("attachment", "swap_or_attach"), ("animation", "play")]
    assert p.begin[0].args["asset_id"] == "iron_sword"


def test_different_action_visual_swaps_same_slot_without_body_animation_rewrite():
    b = ActionPresentationBinder()
    rt = AttachmentRuntime(rig())
    a = b.plan(ActionPresentationRequest("a", "one_hand_slash", sword("iron_sword", 8)))
    run_attachment_commands(rt, a.begin)
    first = rt.instances["active_visual"].spec
    k = b.plan(ActionPresentationRequest("b", "one_hand_slash", sword("katana", 17)))
    run_attachment_commands(rt, k.begin)
    second = rt.instances["active_visual"].spec
    assert first.asset_id == "iron_sword" and second.asset_id == "katana"
    assert a.begin[1].args["animation_id"] == k.begin[1].args["animation_id"] == "one_hand_slash"


def test_action_only_policy_can_hide_visual_after_action():
    b = ActionPresentationBinder()
    rt = AttachmentRuntime(rig())
    p = b.plan(ActionPresentationRequest("attack", "one_hand_slash", sword(), after_action=AfterAction.HIDE))
    run_attachment_commands(rt, p.begin)
    assert rt.instances["active_visual"].state is AttachmentState.ACTIVE
    run_attachment_commands(rt, p.end)
    assert rt.instances["active_visual"].state is AttachmentState.HIDDEN


def test_persistent_policy_keeps_visual():
    p = ActionPresentationBinder().plan(
        ActionPresentationRequest("attack", "one_hand_slash", sword(), after_action=AfterAction.KEEP)
    )
    assert p.end == ()


def test_skill_can_temporarily_override_and_restore_previous_visual():
    b = ActionPresentationBinder()
    rt = AttachmentRuntime(rig())
    previous = sword("iron_sword", 8)
    run_attachment_commands(rt, b.plan(ActionPresentationRequest("ready", visual=previous)).begin)
    temp = sword("staff", 5)
    p = b.plan(
        ActionPresentationRequest("cast", "staff_cast", temp, after_action=AfterAction.RESTORE_PREVIOUS),
        current=previous,
    )
    run_attachment_commands(rt, p.begin)
    assert rt.instances["active_visual"].spec.asset_id == "staff"
    run_attachment_commands(rt, p.end)
    assert rt.instances["active_visual"].spec.asset_id == "iron_sword"


def test_restore_previous_with_no_previous_visual_hides_temporary_visual():
    b = ActionPresentationBinder()
    rt = AttachmentRuntime(rig())
    p = b.plan(
        ActionPresentationRequest("skill", "special", sword(), after_action=AfterAction.RESTORE_PREVIOUS), current=None
    )
    run_attachment_commands(rt, p.begin)
    run_attachment_commands(rt, p.end)
    assert rt.instances["active_visual"].state is AttachmentState.HIDDEN


def test_multi_visual_skill_is_composable_as_multiple_action_phases():
    b = ActionPresentationBinder()
    rt = AttachmentRuntime(rig())
    phases = [("sword", "slash"), ("spear", "thrust"), ("bow", "shoot")]
    for asset, motion in phases:
        p = b.plan(ActionPresentationRequest("multi", motion, sword(asset)))
        run_attachment_commands(rt, p.begin)
        assert rt.instances["active_visual"].spec.asset_id == asset
    assert [m for _, m in phases] == ["slash", "thrust", "shoot"]


def test_binding_contains_no_jrpg_or_arpg_branch():
    import inspect

    import asteria.presentation.action_binding as mod

    src = inspect.getsource(mod).lower()
    assert "if jrpg" not in src and "if arpg" not in src
