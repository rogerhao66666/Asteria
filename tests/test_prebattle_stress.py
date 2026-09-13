from asteria.validation import ComplexPreBattleStressHarness


def report():
    return ComplexPreBattleStressHarness().report()


def test_roster_is_large_and_split_active_reserve():
    r=report()
    assert len(r.characters)==12
    assert len(r.active_ids)==4
    assert len(r.reserve_ids)==8
    assert set(r.active_ids).isdisjoint(r.reserve_ids)


def test_eight_distinct_jobs_are_present():
    r=report()
    assert len(r.job_ids)==8
    used={x.main_job for x in r.characters}|{x.secondary_job for x in r.characters}
    assert set(r.job_ids)<=used


def test_every_character_has_primary_and_secondary_jobs():
    r=report()
    for c in r.characters:
        assert c.main_job
        assert c.secondary_job
        assert c.main_job != c.secondary_job


def test_every_character_has_dense_ability_surface():
    r=report()
    assert r.min_ability_count >= 15
    assert r.max_ability_count > r.min_ability_count


def test_every_character_has_passives_weapon_accessories_attachment():
    r=report()
    for c in r.characters:
        assert len(c.active_passives)==2
        assert len(c.equipment_instance_ids)==3
        assert len(c.attachment_ids)==1


def test_every_character_has_multiple_resources():
    r=report()
    for c in r.characters:
        assert "vitality" in c.resources
        assert "technique" in c.resources
        assert "boost_like" in c.resources
        assert any(x.startswith("unique_resource_") for x in c.resources)
        assert len(c.resources)>=6


def test_inventory_is_stress_sized():
    r=report()
    assert r.inventory_unique_items==64
    assert r.inventory_total_items > 250
    assert r.recipe_count==16


def test_builds_are_materially_different():
    r=report()
    ability_sets={c.actor_id:frozenset(c.abilities) for c in r.characters}
    assert len(set(ability_sets.values()))==12
    stat_sets={tuple(c.stats) for c in r.characters}
    assert len(stat_sets)==12


def test_progression_and_equipment_contribute_capabilities():
    r=report()
    for c in r.characters:
        assert c.capability_count >= 5


def test_report_is_deterministic():
    assert report()==report()
