"""Battle presentation, skill slots and field strikes of the Full Verification (phase 5): the last
empty
Battle and Game Data categories, each used by the campaign.

* **Side-View Positions**: the catacomb guards stand in a staggered rank against the party's
  (the ``crypt_guard`` fight carries ``stage:crypt_ranks``).
* **Portrait Party Layout**: the Acolytes' Vigil is fought the old dungeon way - the party only
  in its HUD, the three acolytes in one line (``stage:vigil_portrait``).
* **Command Menu Pages**: the top-level commands in a set order with shorter names (Fight, Bag,
  Run); past six of them the rest wait on a More page.
* **Command Input Steps**: Vesper's Elemental Weave asks an element, then up to two focuses
  (Overcharge, Echo) that raise its power for more technique or Soul.
* **Ability Slots**: the Old Master teaches Aldric four secret arts; only the ones set in his
  slots (two, three from level 10, four from level 18) are usable.
* **Attacks / Projectiles**: Aldric swings (J) and slings a stone (1) on the map; hitting a foe
  in view first starts its fight preemptive.
"""

from __future__ import annotations

import dataclasses

import trial_content as tc

from asteria.gameplay.action_timeline import ActionCue, ActionTimeline
from asteria.gameplay.attacks import AttackDefinition
from asteria.gameplay.projectiles import ProjectileDefinition
from asteria.presentation.battle_action_workflow import (
    BattleActionWorkflowDefinition,
    BattleWorkflowOption,
    BattleWorkflowStep,
)
from asteria.presentation.battle_interaction import (
    BattleInteractionLayer,
    BattleInteractionProfile,
)
from asteria.presentation.battle_portrait_party_template import (
    BattlePortraitPartyTemplateProfile,
    BattlePortraitPartyZone,
)
from asteria.presentation.battle_sideview_template import (
    BattleSideviewTemplateProfile,
    BattleSideviewZone,
)
from asteria.rpg.ability_loadout import AbilityLoadoutRules

SP = tc.SP
ability, op, damage = tc.ability, tc.op, tc.damage
ARTS = ("art_rending_gale", "art_whirlwind", "art_dawn_edge", "art_iron_vow")
# the top-level commands: (command, shown as, order)
COMMANDS = (
    ("Attack", "Fight", 0),
    ("Skills", "Skills", 1),
    ("Arts", "Arts", 2),
    ("Limit", "Limit", 3),
    ("Combo", "Combos", 4),
    ("Rites", "Rites", 5),
    ("Beast", "Beast", 6),
    ("Items", "Bag", 7),
    ("Escape", "Run", 8),
)


def abilities(c):
    """Elemental Weave and its input steps, the four arts and the slots that hold them, and the
    field strike's attacks, projectile, timelines and abilities."""
    weave(c)
    arts(c)
    field_strike(c)


def weave(c):
    db = c.db
    c.add(
        ability(
            "elemental_weave",
            tags=("magic",),
            sp=8,
            effect=op(damage("magic", 12)),
            hits=tc._hits(1.0),
            input_workflow="elemental_weave",  # the element and focus come from its steps
        ),
        "enemy",
    )
    c.skill_names["elemental_weave"] = "Elemental Weave"
    tc.FX_BY_ABILITY["elemental_weave"] = ("spirit",)
    actor = db.actors["hero_03"]
    db.actors["hero_03"] = dataclasses.replace(
        actor, abilities=(*actor.abilities, "elemental_weave")
    )


def arts(c):
    db = c.db
    for art in (
        ability(
            "art_rending_gale",
            tags=("weapon.sword",),
            sp=10,
            menu_category="Arts",
            effect=op(damage("power", 18)),
            hits=tc._hits(0.6, 0.6, tags=("weapon.sword",)),
        ),
        ability(
            "art_whirlwind",
            tags=("weapon.sword",),
            sp=14,
            targets=6,
            menu_category="Arts",
            effect=op(damage("power", 10)),
            hits=tc._hits(1.0, tags=("weapon.sword",)),
        ),
        ability(
            "art_dawn_edge",
            tags=("damage.light",),
            sp=12,
            menu_category="Arts",
            effect=op(damage("power", 15)),
            hits=tc._hits(1.0, tags=("damage.light",)),
        ),
    ):
        c.add(art, "enemies" if art.ability_id == "art_whirlwind" else "enemy")
    c.add(
        ability(
            "art_iron_vow",
            tags=("support",),
            sp=6,
            menu_category="Arts",
            apply_states=[{"state": "ward", "to": "self"}],
        ),
        "self",
    )
    c.skill_names.update(
        {
            "art_rending_gale": "Rending Gale",
            "art_whirlwind": "Whirlwind",
            "art_dawn_edge": "Dawn Edge",
            "art_iron_vow": "Iron Vow",
        }
    )
    tc.FX_BY_ABILITY.update(
        {
            "art_rending_gale": ("slash2", "cutx"),
            "art_whirlwind": ("circ",),
            "art_dawn_edge": ("spirit",),
            "art_iron_vow": ("shield",),
        }
    )
    # learned arts are the slot-limited ones: class, tree and gear skills stay free
    db.add_ability_loadout_rules(
        AbilityLoadoutRules(
            "trial_slots",
            2,
            capacity_by_level={10: 3, 18: 4},
            limited_sources=("learned",),
        )
    )


def field_strike(c):
    library = c.library
    library.add_attack(AttackDefinition("field_slash", display_name="Field Slash"))
    library.add_attack(AttackDefinition("stone_hit", display_name="Sling Stone"))
    library.add_projectile(
        ProjectileDefinition(
            "sling_stone",
            "Sling Stone",
            attack_id="stone_hit",
            speed=220.0,
            lifetime=0.7,
            width=6.0,
            height=6.0,
        )
    )
    library.add_timeline(
        ActionTimeline(
            "field_slash",
            [
                ActionCue(
                    "swing",
                    0.05,
                    "hitbox",
                    {"hit_tag": "field_slash", "duration": 0.18, "width": 22.0, "height": 16.0},
                ),
                ActionCue("end", 0.35, "gameplay_event", {"name": "end"}),
            ],
        )
    )
    library.add_timeline(
        ActionTimeline(
            "sling_throw",
            [
                ActionCue("throw", 0.1, "projectile", {"projectile_id": "sling_stone"}),
                ActionCue("end", 0.4, "gameplay_event", {"name": "end"}),
            ],
        )
    )
    for ability_id, timeline, cooldown in (
        ("field_slash", "field_slash", 0.4),
        ("sling_throw", "sling_throw", 1.2),
    ):
        c.abilities._definitions[ability_id] = ability(
            ability_id, timeline_id=timeline, cooldown_seconds=cooldown
        )
    c.skill_names.update({"field_slash": "Field Slash", "sling_throw": "Sling Stone"})


def arm_the_field(builders):
    """The hero swings and slings on the map; foes in view can be struck (they carry a hurtbox,
    and a hit first opens their fight preemptive)."""
    from asteria.runtime.action_combat import ActionCombatComponent
    from asteria.runtime.character_control import (
        CharacterController2DComponent,
        Hitbox2DComponent,
        Hurtbox2DComponent,
    )
    from asteria.runtime.field_ai import VisibleEncounterComponent

    hero = builders["town"].find_entity("Player")
    combat = hero.add_component(ActionCombatComponent())
    combat.bindings = "attack=field_slash; skill_1=sling_throw"
    combat.aim, combat.face_target = "facing", False
    hit = hero.add_component(Hitbox2DComponent())
    hit.team, hit.width, hit.height, hit.offset_x, hit.follow_facing = (
        "hero",
        22.0,
        16.0,
        12.0,
        True,
    )
    hurt = hero.add_component(Hurtbox2DComponent())
    hurt.team, hurt.width, hurt.height = "hero", 10.0, 12.0
    if not hero.has(CharacterController2DComponent):  # it keeps the facing the swing turns with
        controller = hero.add_component(CharacterController2DComponent())
        controller.mode, controller.speed, controller.facing = "topdown", 0.0, "down"
        controller.half_width, controller.half_height = 5.0, 4.0
    for builder in builders.values():
        for entity in builder.scene.entities():
            if entity.has(VisibleEncounterComponent) and not entity.has(Hurtbox2DComponent):
                box = entity.add_component(Hurtbox2DComponent())
                box.team, box.width, box.height = "foe", 14.0, 16.0


def old_master(builders, looks, maps):
    """The Old Master in Hearthfold teaches Aldric the four secret arts (LEARN_ABILITY)."""
    town = builders["town"]
    name = "Old Master"
    town.npc(name, maps.world_xy(26, 19), looks["necromancer"])
    world = maps.world
    lessons = [world("LEARN_ABILITY", actor_id="hero_01", ability_id=art) for art in ARTS]
    town.program(
        town.find_entity(name),
        "story.old_master",
        maps.menu(
            name,
            "Four arts, Aldric. Your slots hold only so many at once.",
            [
                (
                    "Learn the arts",
                    [
                        *lessons,
                        world("SHOW_POPUP", text="Learned four secret arts", kind="item"),
                    ],
                ),
                ("Not now", []),
            ],
        ),
    )


def presentation(c):
    """The staging templates, the command pages, the weave's input steps; the layout names the
    pages and two fights name their staging."""
    library = c.project.battle_presentation_library
    db = c.db
    library.set(
        "sideview_templates",
        "crypt_ranks",
        BattleSideviewTemplateProfile(
            "crypt_ranks",
            # foes on the left, each next one up and to the back; the party a rank to the right,
            # every one of its five (with the pet) on the floor below the wall
            BattleSideviewZone("ranks.foes", 150.0, 236.0, -40.0, "right", 0.2, 0.01, -34.0),
            BattleSideviewZone("ranks.party", 246.0, 136.0, 30.0, "left", 0.2, 0.01, 20.0),
        ),
    )
    library.set(
        "portrait_templates",
        "vigil_portrait",
        BattlePortraitPartyTemplateProfile(
            "vigil_portrait",
            BattlePortraitPartyZone("vigil.line", 56.0, 214.0, 0.0, "right", 0.2, 0.01, 88.0),
            hide_portrait_party_bodies=True,
        ),
    )
    library.set(
        "interaction",
        "trial_commands",
        BattleInteractionProfile(
            tuple(
                BattleInteractionLayer(command, label, role="command", order=order)
                for command, label, order in COMMANDS
            ),
            page_size=6,
            max_primary_layers=5,  # past five commands the rest wait on a More page
        ),
    )
    library.set(
        "action_workflows",
        "elemental_weave",
        BattleActionWorkflowDefinition(
            "elemental_weave",
            "Elemental Weave",
            (
                BattleWorkflowStep(
                    "element",
                    "Element",
                    options=(
                        BattleWorkflowOption("fire", "Fire", tags=("damage.fire",)),
                        BattleWorkflowOption("frost", "Frost", tags=("damage.ice",)),
                        BattleWorkflowOption("storm", "Storm", tags=("damage.lightning",)),
                    ),
                ),
                BattleWorkflowStep(
                    "focus",
                    "Focus",
                    selection_mode="multiple",
                    minimum_selections=0,
                    maximum_selections=2,
                    optional=True,
                    options=(
                        BattleWorkflowOption(
                            "overcharge",
                            "Overcharge",
                            detail="x1.5 power",
                            payload={"power": 1.5, "resource_costs": {SP: 12}},
                        ),
                        BattleWorkflowOption(
                            "echo",
                            "Echo",
                            detail="x1.25 power",
                            payload={"power": 1.25, "battle_costs": {"soul": 1}},
                        ),
                    ),
                ),
            ),
            confirmation_label="Weave",
        ),
    )
    layout = library.require("ui_layout", "adaptive")
    paged = dataclasses.replace(layout, command_pages="trial_commands")
    library.set("ui_layout", "adaptive", paged)
    for encounter_id, stage in (
        ("crypt_guard", "crypt_ranks"),
        ("acolyte_vigil", "vigil_portrait"),
    ):
        encounter = db.encounters[encounter_id]
        db.encounters[encounter_id] = dataclasses.replace(
            encounter, tags=(*encounter.tags, f"stage:{stage}")
        )
