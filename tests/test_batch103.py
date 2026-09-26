import inspect
from asteria.presentation.action_binding import ActionPresentationBinder, ActionPresentationRequest, AfterAction, VisualResource
from asteria.presentation.attachments import GripTransform
from asteria.presentation.equipment_presets import (
    ACTION_SCOPED_STARTER, PERSISTENT_ACTIVE_STARTER,
    EquipmentPresentationPolicy, IdleVisualMode,
)


def sword(asset="iron_sword"):
    return VisualResource(asset, "hand_r", GripTransform(x=8, y=3), render_layer="held")


def test_action_scoped_starter_hides_idle_and_after_action():
    p=ACTION_SCOPED_STARTER
    assert p.idle_commands(None)[0].action == "hide"
    req=p.action_request(ActionPresentationRequest("attack", "one_hand_slash", sword()))
    assert req.after_action is AfterAction.HIDE
    plan=ActionPresentationBinder().plan(req)
    assert plan.begin[0].action == "swap_or_attach"
    assert plan.end[0].action == "hide"


def test_action_scoped_selection_preview_can_swap_visual_without_gameplay_mutation():
    cmds=ACTION_SCOPED_STARTER.selection_preview_commands(sword("katana"))
    assert len(cmds)==1 and cmds[0].args["asset_id"] == "katana"


def test_persistent_starter_shows_idle_active_visual_and_keeps_it():
    p=PERSISTENT_ACTIVE_STARTER
    idle=p.idle_commands(sword())
    assert idle[0].action == "swap_or_attach" and idle[0].args["asset_id"] == "iron_sword"
    req=p.action_request(ActionPresentationRequest("attack", "one_hand_slash", sword()))
    assert req.after_action is AfterAction.KEEP
    assert ActionPresentationBinder().plan(req).end == ()


def test_policy_is_editable_not_engine_mode():
    custom=EquipmentPresentationPolicy("project.draw_on_action", IdleVisualMode.HIDDEN, AfterAction.RESTORE_PREVIOUS, False, "main_hand_visual")
    req=custom.action_request(ActionPresentationRequest("skill", "special", sword()))
    assert req.attachment_id == "main_hand_visual"
    assert req.after_action is AfterAction.RESTORE_PREVIOUS


def test_multi_weapon_skill_remains_generic_and_not_owned_by_preset():
    binder=ActionPresentationBinder()
    assets=("iron_sword","spear","bow")
    plans=[binder.plan(ACTION_SCOPED_STARTER.action_request(ActionPresentationRequest("multi", "motion", sword(a)))) for a in assets]
    assert [p.begin[0].args["asset_id"] for p in plans] == list(assets)


def test_presets_do_not_add_jrpg_arpg_branches_to_core_binding():
    import asteria.presentation.action_binding as core
    src=inspect.getsource(core.ActionPresentationBinder.plan).lower()
    assert "jrpg" not in src and "arpg" not in src
