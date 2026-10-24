"""A creature party laid over the Full Verification demo at run time (tests and the live
check), so the engine's Pet Rules can be exercised without changing the demo's own data.

``install(project)`` adds Pet Rules (a party of two, one creature on the stage, storage, the
characters stay out, creatures decide the outcome, experience split among the creatures that
fought, two moves at once, stat formulas with rolled genes), two species that fight as units
with the demo's pet moves (Sling Shot keeps three uses), two capture items, a ``*`` capture
rule in rate mode and a wild encounter of two creatures (the second waits on the bench).
A creature with no move uses left uses Struggle (a hit that also costs the user a quarter of
its top health, defined here as ordinary ability data).
"""

from __future__ import annotations

import copy

from asteria.gameplay.abilities import AbilityDefinition
from asteria.rpg.capture import CaptureRule
from asteria.rpg.enemies import EncounterDefinition, EncounterMember
from asteria.rpg.items import ItemDefinition
from asteria.rpg.pets import (
    PetExpCurve,
    PetMove,
    PetRules,
    PetSpeciesDefinition,
    PetStatFormula,
)

HP = "vitality"
FORMULA = PetStatFormula(gene_terms={"iv": 1.0}, multiplier_gene="nature")
HP_FORMULA = PetStatFormula(gene_terms={"iv": 1.0}, level_term=1.0, flat=10.0)
SPECIES = (
    ("cub", "Cub", {"power": 14, "magic": 30, "defense": 10, "speed": 110, HP: 45}),
    ("wolf", "Wolf", {"power": 20, "magic": 60, "defense": 20, "speed": 40, HP: 60}),
)
ITEMS = ("pet_ball", "great_ball")


def struggle(project):
    """Struggle: Sling Shot's hit plus a self-targeted loss of a quarter of the user's top
    health. Ordinary data: the engine has no such move of its own."""
    from asteria.rpg.targeting import BattleTargetingDefinition

    library = project.gameplay_library.abilities
    if library.get("struggle") is not None:
        return "struggle"
    data = library.require("pet_shot").to_data()
    data.update(ability_id="struggle", display_name="Struggle")
    data.pop("max_uses", None)
    hit = data["effects"][0]
    hit["effect"]["effect_id"] = "struggle.effect"
    recoil = copy.deepcopy(hit)
    recoil["mode"] = "self"
    recoil["effect"]["effect_id"] = "struggle.recoil"
    recoil["effect"]["operations"] = [
        {
            "kind": "resource_delta",
            "target": HP,
            "value": {
                "schema": "asteria.value_formula",
                "version": 1,
                "terms": [{"source": "source_resource_max", "key": HP, "coefficient": -0.25}],
                "multipliers": [],
                "minimum": None,
                "maximum": -1.0,
            },
        }
    ]
    data["effects"] = [hit, recoil]
    library.register(AbilityDefinition.from_data(data))
    targeting = project.rpg_database.battle_targeting["pet_shot"].to_data()
    targeting["ability_id"] = "struggle"
    project.rpg_database.battle_targeting["struggle"] = BattleTargetingDefinition.from_data(
        targeting
    )
    return "struggle"


def install(project, **rules):
    """Add the creature party to a loaded Full Verification project; ``rules`` override the
    Pet Rules fields. Returns the rules record."""
    db = project.rpg_database
    library = project.gameplay_library.abilities
    shot = library.require("pet_shot")
    library._definitions["pet_shot"] = AbilityDefinition.from_data(
        {**shot.to_data(), "max_uses": 3}
    )
    base = {
        "party_size": 2,
        "battle_slots": 1,
        "storage": True,
        "actors_fight": False,
        "pets_decide_outcome": True,
        "exp_share": "split",
        "max_moves": 2,
        "stat_formulas": {"*": FORMULA, HP: HP_FORMULA},
        "gene_ranges": {"iv": [0, 31]},
        "out_of_uses_ability": struggle(project),
    }
    base.update(rules)
    record = PetRules("creature", **base)
    db.pet_rules.clear()
    db.add_pet_rules(record)
    for species_id, name, stats in SPECIES:
        db.pet_species.pop(species_id, None)
        db.add_pet_species(
            PetSpeciesDefinition(
                species_id,
                name,
                stats=stats,
                growth={},
                max_level=50,
                battle_unit=True,
                resources={HP: 1},
                battle_abilities=("pet_shot", "pet_bandage"),
                learnset=(PetMove("pet_volley", level=6),),
                exp_curve=PetExpCurve(cubic=(1, 0, 0, 0)),
                exp_yield=50,
                capture_rate=255,
                visual_profile_id="pet",
                back_visual_profile_id="pet",
            )
        )
    for item_id in ITEMS:
        if item_id not in db.items:
            db.add_item(ItemDefinition(item_id, item_id.replace("_", " ").title()))
    db.capture_rules.clear()
    db.add_capture_rule(
        CaptureRule("*", mode="rate", item_id="pet_ball", item_bonuses={"great_ball": 1.5})
    )
    db.encounters.pop("wild_cubs", None)
    db.add_encounter(
        EncounterDefinition(
            "wild_cubs",
            members=[
                EncounterMember(pet_species_id="cub", level=5),
                EncounterMember(pet_species_id="wolf", level=6, reserve=True),
            ],
        )
    )
    assert db.reference_errors() == []
    return record
