"""Jobs of the companions: each walks a three-tier line (MapleStory style) and keeps a sub job.

    Mira    Cleric      -> Priest (Lv 5)  -> Bishop (Lv 10)        sub job: Mystic
    Vesper  Necromancer -> Lich (Lv 5)    -> Death Lord (Lv 10)    sub job: Knight
    Cael    Cultist     -> Zealot (Lv 5)  -> Heretic (Lv 10)       sub job: Duelist

A job asks for its level and the job before it (``unlock_level`` / ``unlock_classes``); the Job
Hall in Hearthfold advances a companion and trains them for gold. Every companion job has a
skill tree (a ranked core, its skills, two exclusive keystones, a mastery passive) paid for with
that job's points. Roger keeps his own lines (Knight -> Guardian -> Hero, Duelist -> Weapon
Master / Rogue, Mystic -> Sage).
"""

from __future__ import annotations

import trial_content as tc

from asteria.events.conditions import EventCondition
from asteria.events.program import EventInstruction
from asteria.rpg import ClassDefinition, ProgressionGraphDefinition
from asteria.rpg.ability_build import PassiveDefinition

HP, SP = tc.HP, tc.SP
ability, op, damage, healing = tc.ability, tc.op, tc.damage, tc.healing
_hits, _state, _with_self = tc._hits, tc._state, tc._with_self

LINES = {  # actor: (name, (tier 1, tier 2, tier 3), sub job)
    "hero_02": ("Mira", ("cleric", "priest", "bishop"), "mystic"),
    "hero_03": ("Vesper", ("necromancer", "lich", "death_lord"), "knight"),
    "hero_04": ("Cael", ("cultist", "zealot", "heretic"), "duelist"),
}
TIER_LEVEL = {1: 5, 2: 10}  # tier index -> the level that job asks for

NEW = {  # job: (name, stats, resources, growth, weapons)
    "priest": ("Priest", {"magic": 14, "defense": 6}, {SP: 80}, {"magic": 2.6}, ("staff",)),
    "bishop": (
        "Bishop",
        {"magic": 24, "defense": 10},
        {HP: 400, SP: 140},
        {"magic": 3.4, "defense": 1.2},
        ("staff",),
    ),
    "lich": ("Lich", {"magic": 18, "speed": 4}, {SP: 120}, {"magic": 3.0}, ("staff",)),
    "death_lord": (
        "Death Lord",
        {"magic": 28, "power": 8},
        {HP: 500, SP: 160},
        {"magic": 3.6, "power": 1.0},
        ("staff", "sword"),
    ),
    "zealot": (
        "Zealot",
        {"power": 14, "speed": 8, "crit": 6},
        {SP: 60},
        {"power": 2.4, "speed": 1.0},
        ("dagger", "axe"),
    ),
    "heretic": (
        "Heretic",
        {"power": 18, "magic": 12, "crit": 10},
        {HP: 400, SP: 100},
        {"power": 2.8, "magic": 2.0},
        ("dagger", "staff"),
    ),
}

PASSIVES = {  # job: (passive id, name, stat bonuses)
    "cleric": ("devotion", "Devotion", {"magic": 10, "defense": 6}),
    "priest": ("serenity", "Serenity", {"magic": 16}),
    "bishop": ("saints_grace", "Saint's Grace", {"magic": 24, "defense": 12}),
    "necromancer": ("grave_chill", "Grave Chill", {"magic": 12}),
    "lich": ("phylactery", "Phylactery", {"magic": 18, "defense": 8}),
    "death_lord": ("dominion", "Dominion", {"magic": 26, "power": 10}),
    "cultist": ("zeal", "Zeal", {"power": 8, "speed": 6}),
    "zealot": ("fervent_soul", "Fervent Soul", {"power": 14, "crit": 6}),
    "heretic": ("forbidden_lore", "Forbidden Lore", {"power": 18, "magic": 14}),
}


def _magic(ability_id, element, power_, *, hits=(1.0,), targets=1, sp=0, states=()):
    tags = ("magic", f"damage.{element}")
    return ability(
        ability_id,
        tags=tags,
        effect=op(damage("magic", power_)),
        hits=_hits(*hits, tags=(f"damage.{element}",)),
        targets=targets,
        sp=sp,
        apply_states=[_state(s) for s in states],
    )


def _weapon(ability_id, weapon, power_, *, hits=(1.0,), sp=0, states=()):
    tags = (f"weapon.{weapon}",)
    return ability(
        ability_id,
        tags=tags,
        effect=op(damage("power", power_)),
        hits=_hits(*hits, tags=tags),
        sp=sp,
        apply_states=[_state(s) for s in states],
    )


def _support(ability_id, states, *, heal=0.0, sp=0, to="targets"):
    effect = op(healing(heal)) if heal else None
    return ability(
        ability_id,
        tags=("magic", "support"),
        effect=effect,
        sp=sp,
        allies=True,
        apply_states=[_state(s, to) for s in states],
    )


def skills():
    """``{job: [(ability id, label, targeting, definition)]}``: four skills per new job."""
    return {
        "priest": [
            ("holy_nova", "Holy Nova", "allies", _support("holy_nova", (), heal=6.0, sp=18)),
            ("sanctuary", "Sanctuary", "allies", _support("sanctuary", ("regen",), sp=16)),
            ("smite", "Smite", "enemy", _magic("smite", "light", 7.0, sp=10)),
            ("blessing", "Blessing", "ally", _support("blessing", ("magic_up", "ward"), sp=12)),
        ],
        "bishop": [
            (
                "divine_aegis",
                "Divine Aegis",
                "allies",
                _support("divine_aegis", ("ward", "armor_up"), sp=24),
            ),
            (
                "holy_judgment",
                "Holy Judgment",
                "enemies",
                _magic("holy_judgment", "light", 6.0, hits=(1.0, 1.0, 1.2), targets=6, sp=32),
            ),
            ("mass_cure", "Mass Cure", "allies", _support("mass_cure", (), heal=10.0, sp=30)),
            (
                "grace_of_dawn",
                "Grace of Dawn",
                "allies",
                _support("grace_of_dawn", ("regen", "haste"), sp=28),
            ),
        ],
        "lich": [
            (
                "frost_nova",
                "Frost Nova",
                "enemies",
                _magic("frost_nova", "ice", 5.0, targets=6, sp=22, states=("slow",)),
            ),
            (
                "soul_siphon",
                "Soul Siphon",
                "enemy",
                _with_self(_magic("soul_siphon", "dark", 6.0, sp=14), op(healing(4.0))),
            ),
            ("bone_armor", "Bone Armor", "self", _support("bone_armor", ("stoneskin",), sp=10)),
            (
                "plague",
                "Plague",
                "enemies",
                _magic("plague", "dark", 3.0, targets=6, sp=20, states=("poison", "magic_down")),
            ),
        ],
        "death_lord": [
            (
                "death_coil",
                "Death Coil",
                "enemy",
                _magic("death_coil", "dark", 11.0, sp=26, states=("doom",)),
            ),
            (
                "dread_aura",
                "Dread Aura",
                "enemies",
                _magic(
                    "dread_aura",
                    "dark",
                    2.0,
                    targets=6,
                    sp=24,
                    states=("power_down", "defense_down"),
                ),
            ),
            (
                "soul_harvest",
                "Soul Harvest",
                "enemies",
                _with_self(
                    _magic("soul_harvest", "dark", 5.0, hits=(1.0, 1.1), targets=6, sp=34),
                    op(healing(5.0)),
                ),
            ),
            (
                "unholy_pact",
                "Unholy Pact",
                "self",
                _support("unholy_pact", ("berserk", "magic_up"), sp=12),
            ),
        ],
        "zealot": [
            (
                "fanatic_strike",
                "Fanatic Strike",
                "enemy",
                _weapon(
                    "fanatic_strike", "dagger", 6.0, hits=(1.0, 1.0), sp=10, states=("bleed",)
                ),
            ),
            (
                "blood_rite",
                "Blood Rite",
                "self",
                _support("blood_rite", ("attack_up", "lifelink"), sp=12),
            ),
            ("fervor", "Fervor", "allies", _support("fervor", ("haste",), sp=20)),
            (
                "brand",
                "Brand",
                "enemy",
                _magic("brand", "fire", 6.0, sp=14, states=("burn", "defense_down")),
            ),
        ],
        "heretic": [
            (
                "forbidden_rite",
                "Forbidden Rite",
                "enemies",
                _magic("forbidden_rite", "dark", 5.0, hits=(1.0, 1.0, 1.0), targets=6, sp=30),
            ),
            (
                "hex_storm",
                "Hex Storm",
                "enemies",
                _magic("hex_storm", "dark", 2.0, targets=6, sp=24, states=("confuse", "blind")),
            ),
            (
                "martyrdom",
                "Martyrdom",
                "allies",
                _support("martyrdom", (), heal=9.0, sp=26),
            ),
            (
                "apostasy",
                "Apostasy",
                "enemy",
                _weapon("apostasy", "dagger", 9.0, hits=(1.0, 1.4), sp=22, states=("silence",)),
            ),
        ],
    }


def _tree(job, label, skill_ids, growth, passive):
    """core (ranked) -> skills -> two exclusive keystones -> mastery passive."""
    core = f"{job}_core"
    jp = f"jp.{job}"
    nodes = [tc._node(core, f"{label} Training", 5, {jp: 1}, {"stat_bonuses": growth})]
    for index, skill in enumerate(skill_ids):
        needs = [core] if index == 0 else [(core, min(5, index + 1)), f"{job}_{skill_ids[0]}"]
        nodes.append(
            tc._node(
                f"{job}_{skill}",
                skill.replace("_", " ").title(),
                1,
                {jp: 1 + index},
                {"granted_abilities": (skill,)},
                needs=needs,
            )
        )
    for key, name, reward in (
        ("keyA", "Path of Might", {"stat_bonuses": {k: v * 6 for k, v in growth.items()}}),
        ("keyB", "Path of Resilience", {"resource_bonuses": {HP: 500}}),
    ):
        nodes.append(
            tc._node(
                f"{job}_{key}",
                name,
                1,
                {jp: 4},
                reward,
                needs=[(core, 3)],
                group=f"{job}_path",
                tags=("keystone",),
            )
        )
    nodes.append(
        tc._node(
            f"{job}_passive",
            "Mastery",
            1,
            {jp: 6},
            {"unlocked_passives": (passive,)},
            needs=[(core, 5)],
        )
    )
    return ProgressionGraphDefinition(
        f"{job}_tree", label, nodes=tuple(nodes), tags=(f"job.{job}",)
    )


def jobs(c):
    """The six new jobs, their skills, passives, unlock rules and the companion job trees."""
    import dataclasses

    db = c.db
    by_job = {}
    for job, rows in skills().items():
        by_job[job] = []
        for ability_id, label, target, definition in rows:
            c.add(definition, target)
            c.skill_names[ability_id] = label
            by_job[job].append(ability_id)
    for _actor, (_name, line, _sub) in LINES.items():
        for tier, job in enumerate(line):
            if job in NEW:
                name, stats, res, grow, weapons = NEW[job]
                db.add_class(
                    ClassDefinition(
                        job,
                        name,
                        stat_bonuses=stats,
                        resource_bonuses=res,
                        granted_tags=(
                            f"class.{job}",
                            *(f"capability.weapon.{w}" for w in weapons),
                        ),
                        granted_abilities=(by_job[job][0],),
                        level_growth=grow,
                        unlock_level=TIER_LEVEL[tier],
                        unlock_classes=(line[tier - 1],),
                    )
                )
    for pid, name, stats in PASSIVES.values():
        db.add_passive(
            PassiveDefinition(
                pid,
                name,
                modifiers=tuple(tc._modifier(k, v, f"{pid}.{k}") for k, v in stats.items()),
            )
        )
    for _actor, (_name, line, _sub) in LINES.items():
        for job in line:
            definition = db.classes[job]
            skill_ids = by_job.get(job) or list(definition.granted_abilities)
            growth = dict(definition.level_growth) or {"magic": 2.0}
            db.add_progression_graph(
                _tree(job, definition.display_name, skill_ids, growth, PASSIVES[job][0])
            )
    # every companion carries a sub job beside the main one
    from asteria.rpg import ClassAssignment

    for actor_id, (_name, line, sub) in LINES.items():
        actor = db.actors[actor_id]
        db.actors[actor_id] = dataclasses.replace(
            actor,
            class_assignments=(
                ClassAssignment(
                    line[0], assignment_id=f"{actor_id}.main", role="main", priority=10
                ),
                ClassAssignment(sub, assignment_id=f"{actor_id}.sub", role="sub", priority=5),
            ),
        )
    return by_job


# -- the Job Hall -----------------------------------------------------------------------------
def _when(condition_name, operator, value, steps_true, steps_false, label):
    """``steps_true`` when the ``rpg`` condition holds, else ``steps_false`` (unique labels)."""
    condition = EventCondition("rpg", condition_name, operator, value, None).to_data()
    return [
        EventInstruction("JUMP_IF", {"condition": condition, "label": f"{label}.yes"}),
        *steps_false,
        EventInstruction("JUMP", {"label": f"{label}.end"}),
        EventInstruction("LABEL", {"name": f"{label}.yes"}),
        *steps_true,
        EventInstruction("LABEL", {"name": f"{label}.end"}),
    ]


TRAIN_COST = 300


def job_hall_steps(say, world, menu):
    """The Job Hall's menu: advance a companion to the next job of their line, or train them."""
    options = []
    for actor_id, (name, line, sub) in LINES.items():
        for tier in (1, 2):
            job, before, level = line[tier], line[tier - 1], TIER_LEVEL[tier]
            title = job.replace("_", " ").title()
            advance = [
                world("SET_CLASSES", actor_id=actor_id, class_ids=f"{job},{sub}"),
                world("SHOW_POPUP", text=f"{name} is now a {title}!", kind="item"),
            ]
            options.append(
                (
                    f"{name}: become a {title}",
                    _when(
                        f"party:{actor_id}",
                        "==",
                        True,
                        _when(
                            f"job:{actor_id}:{before}",
                            "==",
                            True,
                            _when(
                                f"level:{actor_id}",
                                ">=",
                                level,
                                advance,
                                [say("Job Master", f"{name} needs level {level}.")],
                                f"{actor_id}.{job}.lv",
                            ),
                            [say("Job Master", f"{name} must be a {before.title()} first.")],
                            f"{actor_id}.{job}.job",
                        ),
                        [say("Job Master", f"{name} has not joined you yet.")],
                        f"{actor_id}.{job}.party",
                    ),
                )
            )
        options.append(
            (
                f"Train {name} ({TRAIN_COST} G)",
                _when(
                    "gold",
                    ">=",
                    TRAIN_COST,
                    [
                        world("CHANGE_CURRENCY", currency_id="gold", amount=-TRAIN_COST),
                        world(
                            "GRANT_EXPERIENCE",
                            actor_id=actor_id,
                            amount=4000,
                            level_track="level_curve",
                            points="skill_points=2",  # skill books (phase 2)
                        ),
                        say("Job Master", f"{name} trains hard."),
                    ],
                    [say("Job Master", "Not enough gold.")],
                    f"{actor_id}.train",
                ),
            )
        )
    options.append(("Leave", [say("Job Master", "Walk your path.")]))
    return menu("Job Master", "Whose path shall we walk?", options)
