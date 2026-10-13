from asteria.presentation import (
    BattleActionEntry,
    BattleCombatantVisualProfile,
    BattleCombatantVisualRuntime,
    BattleInformationItem,
    BattleInformationPolicy,
    BattleInformationRuntime,
    BattleInteractionLayer,
    BattleInteractionProfile,
    BattleInteractionRuntime,
    BattleRosterDensityPolicy,
    BattleUiAssemblyRuntime,
    BattleVisualAssetSet,
    BattleVisualTransform,
    default_jrpg_visual_states,
)


def make_visual(member_id, *, battlefield=True, hud=True, z=0, scale=1.0):
    return BattleCombatantVisualProfile(
        member_id,
        BattleVisualAssetSet(
            f"{member_id}.battle",
            f"{member_id}.portrait",
            f"{member_id}.small",
            f"{member_id}.icon",
        ),
        default_jrpg_visual_states(),
        BattleVisualTransform(scale_x=scale, scale_y=scale, z_order=z),
        battlefield_visible=battlefield,
        hud_visible=hud,
    )


def make_interaction():
    r = BattleInteractionRuntime(
        BattleInteractionProfile(
            (
                BattleInteractionLayer("weapon", "Weapon", order=0),
                BattleInteractionLayer("skills", "Skills", order=1),
                BattleInteractionLayer("items", "Items", order=2),
                BattleInteractionLayer("compose", "Compose", order=3),
                BattleInteractionLayer("special", "Special", order=4),
                BattleInteractionLayer("swap", "Swap", order=5),
                BattleInteractionLayer("stance", "Stance", order=6),
            ),
            page_size=8,
            max_primary_layers=6,
        )
    )
    r.set_actions(
        tuple(BattleActionEntry(f"skill.{i}", f"Skill {i}", category="skills") for i in range(20))
    )
    return r


def make_information(focus="p0"):
    r = BattleInformationRuntime(
        BattleInformationPolicy(
            persistent_limit=4, compact_limit=4, focused_limit=4, contextual_limit=4
        )
    )
    items = [
        BattleInformationItem("battle.turn", "timeline", "Turn", priority=100),
        BattleInformationItem("battle.wave", "meta", "Wave", priority=90),
    ]
    for i in range(12):
        items.append(
            BattleInformationItem(
                f"{i}.vitality",
                "resource",
                f"P{i} Vitality",
                priority=70,
                member_id=f"p{i}",
            )
        )
        items.append(
            BattleInformationItem(
                f"{i}.status",
                "status",
                f"P{i} Status",
                priority=40,
                member_id=f"p{i}",
                visibility="compact",
                compact=True,
            )
        )
        items.append(
            BattleInformationItem(
                f"{i}.detail",
                "resource",
                f"P{i} Detail",
                priority=30,
                member_id=f"p{i}",
                visibility="focused",
            )
        )
    return r.resolve(items, focus_member_id=focus)


def make_visuals():
    r = BattleCombatantVisualRuntime()
    for i in range(12):
        r.register(f"p{i}", make_visual(f"p{i}", battlefield=(i < 4), hud=True, z=i))
    r.register("boss", make_visual("boss", z=40, scale=2.8))
    r.register("add", make_visual("add", z=20))
    r.register("summon", make_visual("summon", z=10))
    return tuple(r.state(x) for x in [*(f"p{i}" for i in range(12)), "boss", "add", "summon"])


def test_assembled_frame_uses_full_compact_and_overflow_roster_density():
    roster = BattleRosterDensityPolicy(primary_limit=4, compact_limit=4).resolve(
        tuple(f"p{i}" for i in range(12)), focus_member_id="p2"
    )
    frame = BattleUiAssemblyRuntime().assemble(
        interaction=make_interaction().view,
        information=make_information("p2"),
        roster=roster,
        visuals=make_visuals(),
    )
    assert tuple(x.member_id for x in frame.member_cards[:4]) == ("p0", "p1", "p2", "p3")
    assert all(x.density == "full" for x in frame.member_cards[:4])
    assert all(x.density == "compact" for x in frame.member_cards[4:])
    assert frame.reserve_overflow_ids == ("p8", "p9", "p10", "p11")


def test_focus_member_card_is_marked_without_expanding_every_member():
    roster = BattleRosterDensityPolicy(primary_limit=4, compact_limit=4).resolve(
        tuple(f"p{i}" for i in range(12)), focus_member_id="p10"
    )
    frame = BattleUiAssemblyRuntime().assemble(
        interaction=make_interaction().view,
        information=make_information("p10"),
        roster=roster,
        visuals=make_visuals(),
    )
    focused = [x for x in frame.member_cards if x.focused]
    assert len(focused) == 1
    assert focused[0].member_id == "p10"
    assert len(frame.member_cards) == 8


def test_action_surface_pages_many_skills_instead_of_dumping_all():
    interaction = make_interaction()
    interaction.open_layer("skills")
    roster = BattleRosterDensityPolicy().resolve(("p0",))
    frame = BattleUiAssemblyRuntime().assemble(
        interaction=interaction.view,
        information=make_information("p0"),
        roster=roster,
        visuals=make_visuals(),
    )
    assert len(frame.action_surface.entry_ids) == 8
    assert frame.action_surface.stage == "action"


def test_action_surface_keeps_root_overflow_for_extra_categories():
    interaction = make_interaction()
    roster = BattleRosterDensityPolicy().resolve(("p0",))
    frame = BattleUiAssemblyRuntime().assemble(
        interaction=interaction.view,
        information=make_information("p0"),
        roster=roster,
        visuals=make_visuals(),
    )
    assert frame.action_surface.root_layer_ids == (
        "weapon",
        "skills",
        "items",
        "compose",
        "special",
        "swap",
    )
    assert frame.action_surface.overflow_layer_ids == ("stance",)


def test_hidden_battlefield_bodies_still_have_hud_cards():
    roster = BattleRosterDensityPolicy(primary_limit=4, compact_limit=4).resolve(
        tuple(f"p{i}" for i in range(12))
    )
    frame = BattleUiAssemblyRuntime().assemble(
        interaction=make_interaction().view,
        information=make_information(),
        roster=roster,
        visuals=make_visuals(),
    )
    assert any(x.member_id == "p4" for x in frame.member_cards)
    assert all(x.member_id != "p4" for x in frame.battlefield_visuals)


def test_boss_add_and_summon_share_battlefield_visual_pipeline():
    roster = BattleRosterDensityPolicy().resolve(("p0",))
    frame = BattleUiAssemblyRuntime().assemble(
        interaction=make_interaction().view,
        information=make_information(),
        roster=roster,
        visuals=make_visuals(),
    )
    ids = {x.member_id for x in frame.battlefield_visuals}
    assert {"boss", "add", "summon"} <= ids


def test_large_boss_transform_survives_assembly_and_z_order_sorts():
    roster = BattleRosterDensityPolicy().resolve(("p0",))
    frame = BattleUiAssemblyRuntime().assemble(
        interaction=make_interaction().view,
        information=make_information(),
        roster=roster,
        visuals=make_visuals(),
    )
    boss = next(x for x in frame.battlefield_visuals if x.member_id == "boss")
    assert boss.scale_x == 2.8
    assert frame.battlefield_visuals[-1].member_id == "boss"


def test_information_hierarchy_remains_separate_in_final_frame():
    roster = BattleRosterDensityPolicy().resolve(("p0",))
    frame = BattleUiAssemblyRuntime().assemble(
        interaction=make_interaction().view,
        information=make_information(),
        roster=roster,
        visuals=make_visuals(),
    )
    assert "battle.turn" in frame.persistent_information_ids
    assert any(x.endswith(".status") for x in frame.compact_information_ids)
    assert any(x.endswith(".detail") for x in frame.focused_information_ids)
    assert len(frame.information_overflow_ids) > 0


def test_member_card_uses_portrait_small_portrait_and_icon_assets():
    roster = BattleRosterDensityPolicy().resolve(("p0",))
    frame = BattleUiAssemblyRuntime().assemble(
        interaction=make_interaction().view,
        information=make_information(),
        roster=roster,
        visuals=make_visuals(),
    )
    card = frame.member_cards[0]
    assert card.portrait_asset_id == "p0.portrait"
    assert card.small_portrait_asset_id == "p0.small"
    assert card.icon_asset_id == "p0.icon"


def test_assembly_is_presentation_only_and_does_not_require_battle_runtime():
    interaction = make_interaction()
    roster = BattleRosterDensityPolicy().resolve(("p0",))
    assembly = BattleUiAssemblyRuntime()
    frame = assembly.assemble(
        interaction=interaction.view,
        information=make_information(),
        roster=roster,
        visuals=make_visuals(),
    )
    assert frame.revision == 1
    assert assembly.frame is frame
