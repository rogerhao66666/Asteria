from asteria.validation import NonPartyRpgGeneralityHarness


def report():
    return NonPartyRpgGeneralityHarness().run()


def by_id(value, archetype_id):
    return next(x for x in value.archetypes if x.archetype_id == archetype_id)


def test_four_materially_different_archetypes_share_generic_mechanisms():
    value = report()
    assert tuple(x.archetype_id for x in value.archetypes) == (
        "solo_reactive",
        "atb_squad",
        "monster_roster",
        "tactical_raid",
    )
    assert value.no_reference_game_ids_required


def test_solo_archetype_does_not_require_party_or_job_shape():
    x = by_id(report(), "solo_reactive")
    assert x.roster_size == 1
    assert x.primary_count == 1
    assert x.overflow_count == 0
    assert x.action_count == 7


def test_atb_squad_uses_six_members_and_non_reference_command_roles():
    x = by_id(report(), "atb_squad")
    assert x.roster_size == 6
    assert x.primary_count == 3
    assert x.compact_count == 3
    assert set(x.primary_layer_ids) == {"tech", "item", "stance", "wait"}


def test_monster_collection_roster_can_be_large_without_gameplay_cap():
    x = by_id(report(), "monster_roster")
    assert x.roster_size == 18
    assert x.primary_count == 2
    assert x.compact_count == 5
    assert x.overflow_count == 11
    assert x.action_count == 60


def test_tactical_raid_accepts_24_units_and_96_actions():
    x = by_id(report(), "tactical_raid")
    assert x.roster_size == 24
    assert x.action_count == 96
    assert x.primary_count == 6
    assert x.compact_count == 6
    assert x.overflow_count == 12


def test_command_layer_overflow_is_presentation_only():
    x = by_id(report(), "tactical_raid")
    assert len(x.primary_layer_ids) == 5
    assert len(x.overflow_layer_ids) == 3
    assert x.action_count == 96


def test_information_density_is_bounded_without_losing_overflow():
    x = by_id(report(), "tactical_raid")
    assert x.persistent_info_count <= 8
    assert x.compact_info_count <= 8
    assert x.focused_info_count <= 8
    assert x.contextual_info_count <= 6
    assert x.info_overflow_count > 0


def test_custom_layouts_keep_all_members_in_projection():
    value = report()
    for x in value.archetypes:
        assert x.layout_member_count == x.roster_size


def test_layout_visibility_cap_does_not_remove_members():
    x = by_id(report(), "monster_roster")
    assert x.layout_member_count == 18
    assert x.layout_overflow_count == 12


def test_shared_mechanisms_are_reference_game_neutral():
    value = report()
    text = " ".join(value.shared_mechanisms).casefold()
    assert "party_rpg" not in text
    assert "break" not in text
    assert "bp" not in text


def test_report_is_deterministic():
    assert report() == report()
