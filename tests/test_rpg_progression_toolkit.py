from asteria.rpg import (
    ProgressionMilestone,
    ProgressionRuntime,
    ProgressionTrackDefinition,
    RpgDatabase,
    simple_rpg_database,
)


def test_progression_track_roundtrip_and_rank():
    track = ProgressionTrackDefinition(
        "mastery",
        milestones=[
            ProgressionMilestone(1, 0),
            ProgressionMilestone(2, 10),
            ProgressionMilestone(3, 25),
        ],
    )
    assert ProgressionTrackDefinition.from_data(track.to_data()) == track
    assert track.rank_for(0) == 1 and track.rank_for(24) == 2 and track.rank_for(25) == 3


def test_runtime_crosses_multiple_milestones_deterministically():
    track = ProgressionTrackDefinition(
        "job",
        milestones=[
            ProgressionMilestone(1, 0),
            ProgressionMilestone(2, 10),
            ProgressionMilestone(3, 20, granted_abilities=["skill"]),
        ],
    )
    runtime = ProgressionRuntime([track])
    result = runtime.add("job", 25)
    assert result.old_rank == 1 and result.new_rank == 3
    assert [x.rank for x in result.crossed] == [2, 3]
    assert runtime.total("job") == 25


def test_progression_is_not_hardcoded_to_character_level():
    track = ProgressionTrackDefinition(
        "alchemy_mastery",
        milestones=[
            ProgressionMilestone(1, 0),
            ProgressionMilestone(2, 100, granted_tags=["alchemy.adept"]),
        ],
    )
    runtime = ProgressionRuntime([track])
    runtime.add("alchemy_mastery", 100)
    assert runtime.rank("alchemy_mastery") == 2


def test_runtime_snapshot_roundtrip():
    track = ProgressionTrackDefinition(
        "x", milestones=[ProgressionMilestone(1, 0), ProgressionMilestone(2, 5)]
    )
    runtime = ProgressionRuntime([track])
    runtime.add("x", 7)
    restored = ProgressionRuntime.from_data(runtime.to_data(), [track])
    assert restored.total("x") == 7 and restored.rank("x") == 2


def test_database_v4_roundtrip_and_v3_backward_read():
    db = simple_rpg_database()
    assert RpgDatabase.from_data(db.to_data()).to_data() == db.to_data()
    raw = db.to_data()
    raw["version"] = 3
    raw.pop("progression_tracks")
    old = RpgDatabase.from_data(raw)
    assert old.progression_tracks == {}


def test_simple_rpg_level_default_is_editable_data():
    db = simple_rpg_database()
    track = db.progression_tracks["level"]
    runtime = ProgressionRuntime([track])
    result = runtime.add("level", 55)
    assert result.new_rank == 3
    assert "power_strike" in result.crossed[-1].granted_abilities
