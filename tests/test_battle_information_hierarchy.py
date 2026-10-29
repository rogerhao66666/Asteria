from asteria.presentation import (
    BattleInformationItem,
    BattleInformationPolicy,
    BattleInformationRuntime,
    BattleRosterDensityPolicy,
)


def test_seven_resources_do_not_require_seven_full_persistent_bars():
    r = BattleInformationRuntime(BattleInformationPolicy(persistent_limit=3, compact_limit=3))
    items = (
        BattleInformationItem("vitality", "resource", "Vitality", priority=100),
        BattleInformationItem("technique", "resource", "Technique", priority=90),
        BattleInformationItem(
            "momentum", "resource", "Momentum", priority=80, visibility="compact", compact=True
        ),
        BattleInformationItem(
            "shield", "resource", "Shield", priority=70, visibility="compact", compact=True
        ),
        BattleInformationItem(
            "rage", "resource", "Rage", priority=60, visibility="contextual", group="rage"
        ),
        BattleInformationItem(
            "charge", "resource", "Charge", priority=50, visibility="contextual", group="charge"
        ),
        BattleInformationItem(
            "resolve", "resource", "Resolve", priority=40, visibility="focused", member_id="hero"
        ),
    )
    v = r.resolve(items)
    assert tuple(x.info_id for x in v.persistent) == ("vitality", "technique")
    assert tuple(x.info_id for x in v.compact) == ("momentum", "shield")
    assert v.contextual == ()
    assert v.focused == ()


def test_contextual_resource_appears_only_when_mechanic_is_active():
    r = BattleInformationRuntime()
    item = BattleInformationItem("rage", "resource", "Rage", visibility="contextual", group="rage")
    assert r.resolve((item,)).contextual == ()
    assert r.resolve((item,), active_contexts=("rage",)).contextual[0].info_id == "rage"


def test_focused_detail_is_revealed_only_for_focused_member():
    r = BattleInformationRuntime()
    items = tuple(
        BattleInformationItem(
            f"detail.{i}", "resource", f"R{i}", visibility="focused", member_id=f"p{i}"
        )
        for i in range(6)
    )
    v = r.resolve(items, focus_member_id="p4")
    assert tuple(x.info_id for x in v.focused) == ("detail.4",)
    assert len(v.overflow) == 5


def test_many_statuses_use_priority_and_overflow_instead_of_full_rows():
    r = BattleInformationRuntime(BattleInformationPolicy(compact_limit=4))
    items = tuple(
        BattleInformationItem(
            f"status.{i}", "status", f"S{i}", priority=20 - i, visibility="compact", compact=True
        )
        for i in range(12)
    )
    v = r.resolve(items)
    assert len(v.compact) == 4
    assert len(v.overflow) == 8
    assert tuple(x.info_id for x in v.compact) == ("status.0", "status.1", "status.2", "status.3")


def test_hidden_information_does_not_consume_overflow_space():
    r = BattleInformationRuntime()
    v = r.resolve(
        (
            BattleInformationItem("debug", "debug", "Debug", visibility="hidden"),
            BattleInformationItem(
                "dormant", "resource", "Dormant", visibility="contextual", group="phase2"
            ),
        )
    )
    assert v.overflow == ()
    assert v.hidden_count == 2


def test_twelve_member_roster_uses_primary_compact_and_overflow_groups():
    p = BattleRosterDensityPolicy(primary_limit=4, compact_limit=4)
    v = p.resolve(tuple(f"p{i}" for i in range(12)))
    assert v.primary_member_ids == ("p0", "p1", "p2", "p3")
    assert v.compact_member_ids == ("p4", "p5", "p6", "p7")
    assert v.overflow_member_ids == ("p8", "p9", "p10", "p11")


def test_focus_is_kept_visible_even_when_member_would_normally_overflow():
    p = BattleRosterDensityPolicy(primary_limit=4, compact_limit=4)
    v = p.resolve(tuple(f"p{i}" for i in range(12)), focus_member_id="p10")
    assert "p10" in v.primary_member_ids
    assert len(v.primary_member_ids) == 4
    assert set(v.primary_member_ids + v.compact_member_ids + v.overflow_member_ids) == set(
        f"p{i}" for i in range(12)
    )


def test_boss_adds_and_summon_can_have_different_information_priorities():
    r = BattleInformationRuntime(BattleInformationPolicy(persistent_limit=4, compact_limit=4))
    v = r.resolve(
        (
            BattleInformationItem(
                "boss.vitality", "resource", "Boss Vitality", priority=100, member_id="boss"
            ),
            BattleInformationItem(
                "boss.phase", "state", "Boss Phase", priority=95, member_id="boss"
            ),
            BattleInformationItem(
                "add.a",
                "combatant",
                "Add A",
                priority=30,
                visibility="compact",
                compact=True,
                member_id="add.a",
            ),
            BattleInformationItem(
                "add.b",
                "combatant",
                "Add B",
                priority=30,
                visibility="compact",
                compact=True,
                member_id="add.b",
            ),
            BattleInformationItem(
                "summon",
                "combatant",
                "Summon",
                priority=50,
                visibility="compact",
                compact=True,
                member_id="summon",
            ),
        )
    )
    assert tuple(x.info_id for x in v.persistent) == ("boss.vitality", "boss.phase")
    assert tuple(x.info_id for x in v.compact) == ("summon", "add.a", "add.b")


def test_dense_timeline_can_show_focus_and_move_lower_priority_entries_to_overflow():
    r = BattleInformationRuntime(BattleInformationPolicy(compact_limit=6))
    items = tuple(
        BattleInformationItem(
            f"turn.{i}", "timeline", f"T{i}", priority=100 - i, visibility="compact", compact=True
        )
        for i in range(18)
    )
    v = r.resolve(items)
    assert len(v.compact) == 6
    assert len(v.overflow) == 12


def test_project_can_choose_different_visibility_grammar_without_party_rpg_semantics():
    r = BattleInformationRuntime()
    v = r.resolve(
        (
            BattleInformationItem("moon", "project.resource", "Moon", visibility="persistent"),
            BattleInformationItem(
                "echo", "project.resource", "Echo", visibility="contextual", group="ritual"
            ),
            BattleInformationItem(
                "sigil", "project.state", "Sigil", visibility="focused", member_id="x"
            ),
        ),
        focus_member_id="x",
        active_contexts=("ritual",),
    )
    assert v.persistent[0].info_id == "moon"
    assert v.contextual[0].info_id == "echo"
    assert v.focused[0].info_id == "sigil"
