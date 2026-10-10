import copy

import pytest

from asteria.rpg import (
    ActorDefinition,
    ClassAssignment,
    ClassDefinition,
    ProgressionMilestone,
    ProgressionTrackDefinition,
    RpgDatabase,
)


def build_db():
    db = RpgDatabase()
    db.add_class(
        ClassDefinition(
            "warrior",
            "Warrior",
            stat_bonuses={"attack": 10, "defense": 4},
            resource_bonuses={"hp": 20},
            granted_tags=["class.warrior", "capability.weapon.sword"],
            granted_abilities=["power_strike"],
        )
    )
    db.add_class(
        ClassDefinition(
            "scholar",
            "Scholar",
            stat_bonuses={"magic": 12, "speed": 2},
            resource_bonuses={"mp": 15},
            granted_tags=["class.scholar", "capability.weapon.staff"],
            granted_abilities=["fireball"],
        )
    )
    db.add_class(
        ClassDefinition(
            "hunter",
            "Hunter",
            stat_bonuses={"speed": 7},
            granted_tags=["class.hunter", "capability.weapon.bow"],
            granted_abilities=["aimed_shot"],
        )
    )
    for track_id in ("warrior_rank", "scholar_rank", "hunter_rank"):
        db.add_progression_track(
            ProgressionTrackDefinition(
                track_id,
                track_id,
                milestones=[ProgressionMilestone(1, 0)],
            )
        )
    return db


def test_actor_supports_arbitrary_simultaneous_class_assignments():
    db = build_db()
    actor = ActorDefinition(
        "aria",
        "Aria",
        class_assignments=[
            ClassAssignment(
                "scholar",
                assignment_id="job.scholar",
                role="secondary",
                priority=20,
                progression_track_ids=["scholar_rank"],
                tags=["build.magic_side"],
            ),
            ClassAssignment(
                "warrior",
                assignment_id="job.warrior",
                role="primary",
                priority=10,
                progression_track_ids=["warrior_rank"],
            ),
            ClassAssignment(
                "hunter",
                assignment_id="job.hunter",
                role="special",
                priority=30,
                progression_track_ids=["hunter_rank"],
            ),
        ],
        base_stats={"attack": 20, "defense": 10, "magic": 8, "speed": 5},
        base_resources={"hp": 100, "mp": 10},
        abilities=["basic_attack"],
    )
    db.add_actor(actor)
    runtime = db.build_actor("aria")

    assert [x.class_id for x in runtime.class_assignments] == [
        "warrior",
        "scholar",
        "hunter",
    ]
    assert runtime.stats.get("attack") == 30
    assert runtime.stats.get("magic") == 20
    assert runtime.stats.get("speed") == 14
    assert runtime.resources.get("hp").maximum == 120
    assert runtime.resources.get("mp").maximum == 25
    assert runtime.tags.contains("class.warrior")
    assert runtime.tags.contains("class.scholar")
    assert runtime.tags.contains("class.hunter")
    assert runtime.tags.contains("build.magic_side")
    assert runtime.abilities == (
        "basic_attack",
        "power_strike",
        "fireball",
        "aimed_shot",
    )


def test_disabled_assignment_does_not_contribute_and_legacy_class_id_is_view_only():
    db = build_db()
    actor = ActorDefinition(
        "aria",
        class_assignments=[
            ClassAssignment("warrior", assignment_id="warrior", priority=10),
            ClassAssignment(
                "scholar", assignment_id="scholar", enabled=False, priority=0
            ),
        ],
        base_stats={"attack": 1, "magic": 1},
    )
    db.add_actor(actor)
    runtime = db.build_actor("aria")

    assert actor.class_id == "warrior"
    assert runtime.stats.get("attack") == 11
    assert runtime.stats.get("magic") == 1
    assert "fireball" not in runtime.abilities


def test_actor_v1_single_class_migrates_to_v2_assignment():
    old = ActorDefinition(
        "hero", class_id="warrior", base_stats={"attack": 5}
    ).to_data()
    old["version"] = 1
    old["class_id"] = "warrior"
    del old["class_assignments"]

    loaded = ActorDefinition.from_data(old)
    assert loaded.class_id == "warrior"
    assert len(loaded.class_assignments) == 1
    assert loaded.class_assignments[0].role == "primary"
    assert loaded.to_data()["version"] == 2


def test_class_assignment_roundtrip_and_order_are_deterministic():
    actor = ActorDefinition(
        "hero",
        class_assignments=[
            ClassAssignment("b", assignment_id="z", priority=0),
            ClassAssignment("a", assignment_id="a", priority=0),
            ClassAssignment("c", assignment_id="c", priority=-1),
        ],
    )
    roundtrip = ActorDefinition.from_data(copy.deepcopy(actor.to_data()))
    assert [x.class_id for x in roundtrip.enabled_class_assignments()] == ["c", "a", "b"]


def test_duplicate_assignment_ids_are_rejected():
    with pytest.raises(ValueError, match="assignment ids"):
        ActorDefinition(
            "hero",
            class_assignments=[
                ClassAssignment("warrior", assignment_id="same"),
                ClassAssignment("scholar", assignment_id="same"),
            ],
        )


def test_database_validates_class_and_job_progression_references():
    db = RpgDatabase()
    db.add_class(ClassDefinition("warrior"))
    db.add_actor(
        ActorDefinition(
            "hero",
            class_assignments=[
                ClassAssignment(
                    "warrior", progression_track_ids=["missing_job_rank"]
                )
            ],
        )
    )
    with pytest.raises(ValueError, match="missing_job_rank"):
        db.validate()


def test_database_schema_v6_roundtrip_preserves_multiclass():
    db = build_db()
    db.add_actor(
        ActorDefinition(
            "hero",
            class_assignments=[
                ClassAssignment("warrior", role="primary"),
                ClassAssignment(
                    "scholar",
                    assignment_id="scholar.secondary",
                    role="secondary",
                    priority=1,
                ),
            ],
        )
    )
    raw = db.to_data()
    assert raw["version"] == 25
    loaded = RpgDatabase.from_data(raw)
    assert [x.class_id for x in loaded.actors["hero"].enabled_class_assignments()] == [
        "warrior",
        "scholar",
    ]


def test_job_assignments_scope_progression_contributions_to_their_tracks():
    from asteria.rpg import ProgressionRuntime

    db = build_db()
    # Give scholar and hunter visibly different progression bonuses.
    db.progression_tracks["scholar_rank"] = ProgressionTrackDefinition(
        "scholar_rank",
        milestones=[
            ProgressionMilestone(1, 0),
            ProgressionMilestone(2, 10, stat_bonuses={"magic": 50}),
        ],
    )
    db.progression_tracks["hunter_rank"] = ProgressionTrackDefinition(
        "hunter_rank",
        milestones=[
            ProgressionMilestone(1, 0),
            ProgressionMilestone(2, 10, stat_bonuses={"speed": 99}),
        ],
    )
    actor = ActorDefinition(
        "mage",
        class_assignments=[
            ClassAssignment(
                "scholar",
                progression_track_ids=["scholar_rank"],
            )
        ],
        base_stats={"magic": 1, "speed": 1},
    )
    db.add_actor(actor)
    runtime = db.build_actor("mage")
    progression = ProgressionRuntime(
        db.progression_tracks.values(),
        totals={"scholar_rank": 10, "hunter_rank": 10},
    )

    effective = runtime.effective_stats(progression=progression)
    assert effective.get("magic") == 63  # base 1 + class 12 + scholar rank 50
    assert effective.get("speed") == 3  # base 1 + class 2; hunter track excluded
