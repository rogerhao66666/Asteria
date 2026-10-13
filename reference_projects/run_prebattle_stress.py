"""Run from repository root:
PYTHONPATH=src python reference_projects/run_prebattle_stress.py
"""

from asteria.validation import ComplexPreBattleStressHarness

r = ComplexPreBattleStressHarness().report()
print("roster:", len(r.characters))
print("active:", r.active_ids)
print("reserve:", r.reserve_ids)
print("jobs:", r.job_ids)
print("inventory:", r.inventory_unique_items, "unique /", r.inventory_total_items, "total")
print("ability density:", r.min_ability_count, "to", r.max_ability_count)
for c in r.characters:
    print(
        c.actor_id,
        "Lv",
        c.level,
        c.main_job,
        "/",
        c.secondary_job,
        "abilities",
        len(c.abilities),
        "equipment",
        len(c.equipment_instance_ids),
        "resources",
        len(c.resources),
        "capabilities",
        c.capability_count,
    )
