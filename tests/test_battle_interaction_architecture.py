from asteria.presentation import (
    BattleActionEntry,
    BattleActionWorkflowDefinition,
    BattleInteractionLayer,
    BattleInteractionProfile,
    BattleInteractionRuntime,
    BattleWorkflowOption,
    BattleWorkflowStep,
)

def profile():
    return BattleInteractionProfile((
        BattleInteractionLayer("weapon","Weapon",order=0),
        BattleInteractionLayer("skills","Skills",order=1),
        BattleInteractionLayer("items","Items",order=2),
        BattleInteractionLayer("compose","Compose",order=3),
        BattleInteractionLayer("special","Special",order=4),
        BattleInteractionLayer("swap","Swap",order=5),
        BattleInteractionLayer("stance","Stance",order=6),
        BattleInteractionLayer("boost","Boost",role="modifier",contextual=True,order=7),
    ),page_size=8,max_primary_layers=6)

def many_actions():
    values=[]
    # 4 weapons and 80 skill-like actions coexist, but are paged/category routed.
    for w in range(4):
        values.append(BattleActionEntry(
            f"weapon.{w}",f"Weapon {w}",category="weapon",kind="weapon",order=w
        ))
    for i in range(80):
        values.append(BattleActionEntry(
            f"skill.{i:02d}",f"Skill {i:02d}",category="skills",kind="ability",
            order=i,tags=(f"school.{i%5}",f"weapon.{i%4}")
        ))
    values.extend((
        BattleActionEntry("item.potion","Potion",category="items",kind="item"),
        BattleActionEntry("workflow.alchemy","Alchemy",category="compose",kind="workflow"),
        BattleActionEntry("mode.overdrive","Overdrive",category="special",kind="mode"),
        BattleActionEntry("summon.echo","Echo",category="special",kind="summon"),
        BattleActionEntry("swap.reserve","Swap",category="swap",kind="swap"),
        BattleActionEntry("stance.guard","Guard",category="stance",kind="stance"),
    ))
    return tuple(values)

def test_root_limits_primary_layers_and_moves_extra_to_overflow():
    r=BattleInteractionRuntime(profile())
    v=r.view
    assert len(v.primary_layers)==6
    assert tuple(x.layer_id for x in v.primary_layers)==("weapon","skills","items","compose","special","swap")
    assert tuple(x.layer_id for x in v.overflow_layers)==("stance",)

def test_eighty_skills_are_paged_not_dumped_as_eighty_buttons():
    r=BattleInteractionRuntime(profile())
    r.set_actions(many_actions())
    v=r.open_layer("skills")
    assert v.menu_view.total_count==80
    assert len(v.menu_view.entries)==8
    assert v.menu_view.page_count==10

def test_four_weapons_are_a_layer_not_four_giant_parallel_panels():
    r=BattleInteractionRuntime(profile())
    r.set_actions(many_actions())
    v=r.open_layer("weapon")
    assert v.menu_view.total_count==4
    assert tuple(x.action_id for x in v.menu_view.entries)==tuple(f"weapon.{i}" for i in range(4))

def test_project_defined_categories_and_kinds_are_opaque():
    r=BattleInteractionRuntime(BattleInteractionProfile((
        BattleInteractionLayer("runes","Runes"),
    )))
    r.set_actions((BattleActionEntry("x","X",category="runes",kind="project.custom"),))
    assert r.open_layer("runes").menu_view.entries[0].kind=="project.custom"

def test_disabled_action_cannot_be_selected_by_presentation_router():
    r=BattleInteractionRuntime(profile())
    r.set_actions((BattleActionEntry("locked","Locked",category="special",enabled=False),))
    r.open_layer("special")
    r.choose_action("locked")
    assert r.view.selected_action_id is None

def test_contextual_modifier_is_hidden_until_relevant_action_requests_it():
    r=BattleInteractionRuntime(profile())
    r.set_actions(many_actions())
    r.open_layer("skills")
    r.choose_action("skill.00")
    assert all(x.layer_id!="boost" for x in r.view.primary_layers+r.view.overflow_layers)
    r.set_contextual_entries((
        BattleActionEntry("boost.1","Boost x1",category="modifier",kind="modifier"),
        BattleActionEntry("boost.2","Boost x2",category="modifier",kind="modifier"),
    ))
    v=r.begin_modifiers()
    assert tuple(x.action_id for x in v.contextual_entries)==("boost.1","boost.2")
    r.choose_modifier("boost.2")
    assert r.view.modifier_ids==("boost.2",)

def test_alchemy_like_workflow_uses_existing_generic_multistep_runtime():
    r=BattleInteractionRuntime(profile())
    r.set_actions(many_actions())
    r.open_layer("compose")
    r.choose_action("workflow.alchemy")
    definition=BattleActionWorkflowDefinition(
        "field_mix","Field Mix",(
            BattleWorkflowStep("base","Base"),
            BattleWorkflowStep("reagent","Reagent"),
        )
    )
    r.begin_workflow(definition,(BattleWorkflowOption("herb","Herb"),))
    assert r.view.stage=="workflow"
    r.workflow.select("herb")
    r.workflow.advance((BattleWorkflowOption("crystal","Crystal"),))
    r.workflow.select("crystal")
    r.workflow.advance()
    r.begin_targeting("hero")
    r.set_targets(("enemy",))
    assert r.view.can_confirm
    assert r.context.workflow_payload==( ("base",("herb",)), ("reagent",("crystal",)) )

def test_transform_summon_swap_are_actions_not_permanent_hud_sections():
    r=BattleInteractionRuntime(profile())
    r.set_actions(many_actions())
    special=r.open_layer("special").menu_view
    ids={x.action_id for x in special.entries}
    assert {"mode.overdrive","summon.echo"} <= ids
    swap=r.open_layer("swap").menu_view
    assert swap.entries[0].action_id=="swap.reserve"

def test_targeting_and_confirmation_are_separate_layers():
    r=BattleInteractionRuntime(profile())
    r.set_actions(many_actions())
    r.open_layer("skills")
    r.choose_action("skill.03")
    r.begin_targeting("hero")
    assert r.view.stage=="target" and not r.view.can_confirm
    r.set_targets(("boss",))
    assert r.view.stage=="confirm" and r.view.can_confirm

def test_reset_returns_to_root_and_clears_contextual_state():
    r=BattleInteractionRuntime(profile())
    r.set_actions(many_actions())
    r.open_layer("skills")
    r.choose_action("skill.01")
    r.set_contextual_entries((BattleActionEntry("m","M",category="m"),))
    r.begin_modifiers()
    r.choose_modifier("m")
    r.reset()
    assert r.view.stage=="root"
    assert r.view.selected_action_id is None
    assert r.view.modifier_ids==()
