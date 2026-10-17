"""Build content of the ARPG demo: three skill trees per class (three builds each), the skills,
projectiles and states behind them, and the keystones that make a build.

Everything is ordinary project data made with the same helpers as the rest of the demo (attacks,
projectiles, action timelines, abilities, states, progression graphs). A skill is one row of
``SKILLS``; a build is one row of ``BRANCHES``.
"""

from __future__ import annotations

from asteria.gameplay import Effect, EffectOperation
from asteria.gameplay.abilities import AbilityCost, AbilityDefinition
from asteria.gameplay.action_timeline import ActionCue, ActionTimeline
from asteria.gameplay.attacks import AttackDefinition
from asteria.gameplay.formulas import FormulaTerm, ValueFormula
from asteria.gameplay.modifiers import StatModifier
from asteria.gameplay.projectiles import ProjectileDefinition
from asteria.gameplay.states import PeriodicEffect, StateDefinition
from asteria.rpg import (
    ProgressionGraphDefinition,
    ProgressionNodeDefinition,
    ProgressionNodeRequirement,
    ProgressionNodeReward,
)

# stats the builds and the gear share: a skill of an element adds its stat to the damage
ELEMENT_STATS = ("fire_dmg", "cold_dmg", "shock_dmg", "poison_dmg")
BUILD_STATS = ("crit", *ELEMENT_STATS)


def scaled(stat, coefficient, *, defense=0.5, extra=None):
    terms = [FormulaTerm("source_stat", stat, coefficient)]
    terms += [FormulaTerm("source_stat", s, c) for s, c in (extra or {}).items()]
    terms.append(FormulaTerm("target_stat", "defense", -defense))
    return ValueFormula(terms, minimum=1)


def _cue(kind, name, at, **payload):
    return ActionCue(f"{name}_{at}", at, kind, payload)


def hit(attack, at, *, length=0.12, **shape):
    return ActionCue(
        f"{attack}_{at}", at, "hitbox", {"duration": length, "hit_tag": attack, **shape}
    )


def shoot(name, at, projectile, **extra):
    return ActionCue(
        f"{name}_{at}", at, "projectile", {"projectile_id": projectile, **extra, "aim": True}
    )


def move(name, at, speed, duration, *, x=1, relative="aim"):
    payload = {"x": x, "y": 0, "relative": relative, "speed": speed, "duration": duration}
    return ActionCue(f"{name}_{at}", at, "movement", payload)


# -- states ---------------------------------------------------------------------------------------
def _dot(state_id, name, seconds, tick, damage, tag):
    effect = Effect(f"{state_id}.tick", (EffectOperation("resource_delta", "hp", -damage),))
    return StateDefinition(
        state_id,
        seconds,
        periodic=(PeriodicEffect(tick, effect),),
        contributed_tags=(f"status.{tag}",),
        display_name=name,
    )


def _buff(state_id, name, seconds, mods, tag, *, heal=0):
    periodic = ()
    if heal:
        effect = Effect(f"{state_id}.tick", (EffectOperation("resource_delta", "hp", heal),))
        periodic = (PeriodicEffect(0.5, effect),)
    return StateDefinition(
        state_id,
        seconds,
        modifiers=tuple(
            StatModifier(f"{state_id}.{stat}", stat, kind, value) for stat, kind, value in mods
        ),
        periodic=periodic,
        contributed_tags=(f"status.{tag}",),
        display_name=name,
    )


def states():
    return (
        _dot("poisoned", "Poisoned", 5.0, 0.5, 7, "poisoned"),
        _buff("shocked", "Shocked", 4.0, [("defense", "add", -5)], "shocked"),
        _buff(
            "frenzy", "Frenzy", 8.0, [("power", "multiply", 1.3), ("crit", "add", 10)], "frenzy"
        ),
        _buff("fortify", "Fortify", 8.0, [("defense", "add", 6)], "fortify"),
        _buff("bulwark", "Bulwark", 6.0, [("defense", "add", 4)], "bulwark", heal=10),
        _buff(
            "deadeye", "Deadeye", 8.0, [("crit", "add", 25), ("dexterity", "add", 6)], "deadeye"
        ),
        _buff(
            "overload",
            "Overload",
            10.0,
            [("magic", "multiply", 1.35), ("crit", "add", 15)],
            "overload",
        ),
    )


# -- skills ---------------------------------------------------------------------------------------
class Skill:
    """One ability: its damage, how it is cast and what it costs."""

    def __init__(
        self,
        ability_id,
        name,
        mp,
        cooldown,
        cues,
        *,
        attack=None,
        projectile=None,
        tags=(),
        interrupts=False,
        buff="",
    ):
        self.ability_id, self.name, self.mp, self.cooldown = ability_id, name, mp, cooldown
        self.cues, self.attack, self.projectile = cues, attack, projectile
        self.tags, self.interrupts, self.buff = tags, interrupts, buff


def _end(ability_id, at):
    return ActionCue(f"{ability_id}_end", at, "gameplay_event", {"name": "end"})


def _anim(at=0.0):
    return ActionCue(f"anim_{at}", at, "animation", {"clip": "attack"})


def _armor(seconds):
    return ActionCue("armor", 0.0, "armor", {"duration": seconds})


def _iframes(seconds):
    return ActionCue("iframes", 0.0, "iframe", {"duration": seconds})


def _fire(ability_id, **kw):
    return AttackDefinition(ability_id, tags=["Element.Fire"], **kw)


def build_skills(looks):
    """Every skill of the three class trees that is not already in the demo."""
    arrow = looks["arrow"]
    big_fire = looks["fx_fire_ball"]
    ice, bolt = looks["fx_ice_bolt"], looks["fx_bolt_ball"]
    skills = []
    add = skills.append

    def buff_skill(ability_id, name, mp, cooldown, state, length=0.45):
        cues = [
            _anim(),
            ActionCue(
                f"{ability_id}_cast",
                0.1,
                "gameplay_event",
                {"name": ability_id, "apply_state": state},
            ),
            _end(ability_id, length),
        ]
        add(Skill(ability_id, name, mp, cooldown, cues, buff=state))

    def melee(
        ability_id,
        name,
        mp,
        cooldown,
        hits,
        attack,
        *,
        length=0.5,
        armor=0.0,
        lunge=None,
        iframes=0.0,
        tags=(),
    ):
        cues = [_anim()]
        if armor:
            cues.append(_armor(armor))
        if iframes:
            cues.append(_iframes(iframes))
        if lunge:
            cues.extend(move("lunge", at, speed, 0.1, relative="facing") for at, speed in lunge)
        cues.extend(hit(ability_id, at, **shape) for at, shape in hits)
        cues.append(_end(ability_id, length))
        add(
            Skill(
                ability_id,
                name,
                mp,
                cooldown,
                cues,
                attack=attack,
                tags=tags,
                interrupts=bool(iframes),
            )
        )

    def caster(
        ability_id,
        name,
        mp,
        cooldown,
        shots,
        attack,
        projectile,
        *,
        length=0.5,
        armor=0.0,
        tags=(),
    ):
        cues = [_anim()]
        if armor:
            cues.append(_armor(armor))
        cues.extend(
            shoot(ability_id, at, projectile.projectile_id, **extra) for at, extra in shots
        )
        cues.append(_end(ability_id, length))
        add(
            Skill(
                ability_id,
                name,
                mp,
                cooldown,
                cues,
                attack=attack,
                projectile=projectile,
                tags=tags,
            )
        )

    # -- warrior: berserker (bleed, crit), guardian (defence, control), warlord (shouts, area) --
    melee(
        "w_rend",
        "Rend",
        5,
        2.0,
        [(0.08, dict(width=28, height=24, offset_x=14))],
        AttackDefinition(
            "w_rend",
            damage=scaled("power", 1.3),
            knockback=60,
            hitstun=0.15,
            critical_chance_stat="crit",
            critical_multiplier=1.8,
            apply_states=[{"state": "bleeding", "chance": 1.0}],
        ),
        length=0.35,
        lunge=[(0.0, 130)],
    )
    buff_skill("w_frenzy", "Frenzy", 10, 14.0, "frenzy")
    melee(
        "w_execute",
        "Execute",
        14,
        5.0,
        [(0.18, dict(width=34, height=28, offset_x=18))],
        AttackDefinition(
            "w_execute",
            damage=scaled("power", 2.9),
            knockback=240,
            knockdown=True,
            poise_damage=40,
            hitstop=0.08,
            critical_chance_stat="crit",
            critical_multiplier=2.2,
        ),
        length=0.55,
        armor=0.4,
        lunge=[(0.1, 210)],
    )
    melee(
        "w_rampage",
        "Rampage",
        20,
        9.0,
        [
            (0.08, dict(width=32, height=26, offset_x=16)),
            (0.28, dict(width=32, height=26, offset_x=16)),
            (0.48, dict(width=40, height=30, offset_x=18)),
        ],
        AttackDefinition(
            "w_rampage",
            damage=scaled("power", 1.2),
            knockback=100,
            hitstun=0.2,
            critical_chance_stat="crit",
            critical_multiplier=1.8,
            apply_states=[{"state": "bleeding", "chance": 0.5}],
        ),
        length=0.8,
        armor=0.75,
        lunge=[(0.0, 160), (0.2, 160), (0.4, 160)],
    )
    melee(
        "w_shield_bash",
        "Shield Bash",
        6,
        3.0,
        [(0.1, dict(width=30, height=28, offset_x=14))],
        AttackDefinition(
            "w_shield_bash",
            damage=scaled("power", 0.8, extra={"defense": 0.8}),
            knockback=220,
            knockdown=True,
            poise_damage=60,
            hitstun=0.8,
            hitstop=0.06,
        ),
        length=0.4,
    )
    buff_skill("w_fortify", "Fortify", 12, 16.0, "fortify")
    melee(
        "w_ground_slam",
        "Ground Slam",
        14,
        5.0,
        [(0.4, dict(width=72, height=72))],
        AttackDefinition(
            "w_ground_slam",
            damage=scaled("power", 1.4, extra={"defense": 0.6}),
            knockback=200,
            knockdown=True,
            poise_damage=50,
            hitstop=0.08,
            hitstop_scope="global",
        ),
        length=0.7,
        armor=0.6,
    )
    melee(
        "w_retribution",
        "Retribution",
        16,
        8.0,
        [(0.15, dict(width=84, height=84)), (0.35, dict(width=84, height=84))],
        AttackDefinition(
            "w_retribution",
            damage=scaled("defense", 2.2, extra={"power": 0.6}),
            knockback=180,
            hitstun=0.25,
            hitstop=0.05,
        ),
        length=0.6,
        armor=0.55,
    )
    buff_skill("w_bulwark", "Bulwark", 18, 22.0, "bulwark")
    melee(
        "w_cleave",
        "Cleave",
        4,
        1.2,
        [(0.08, dict(width=46, height=42, offset_x=14))],
        AttackDefinition("w_cleave", damage=scaled("power", 1.1), knockback=100, hitstun=0.2),
        length=0.4,
    )
    melee(
        "w_thunderclap",
        "Thunderclap",
        12,
        6.0,
        [(0.15, dict(width=92, height=92))],
        AttackDefinition(
            "w_thunderclap",
            damage=scaled("power", 1.0, extra={"shock_dmg": 1.0}),
            tags=["Element.Lightning"],
            knockback=120,
            hitstun=0.3,
            apply_states=[{"state": "shocked", "chance": 1.0}],
        ),
        length=0.5,
        tags=("magic",),
    )
    melee(
        "w_earthquake",
        "Earthquake",
        24,
        11.0,
        [
            (0.2, dict(width=104, height=104)),
            (0.5, dict(width=104, height=104)),
            (0.8, dict(width=104, height=104)),
        ],
        AttackDefinition(
            "w_earthquake",
            damage=scaled("power", 1.5),
            knockback=160,
            knockdown=True,
            poise_damage=40,
            hitstop=0.06,
        ),
        length=1.1,
        armor=1.0,
    )

    # -- ranger: marksman (crit, pierce), venomancer (poison), skirmisher (volleys, mobility) --
    def arrow_def(pid, attack, speed=380.0, lifetime=0.9, **kw):
        return ProjectileDefinition(
            pid, attack_id=attack.attack_id, speed=speed, lifetime=lifetime, sprite=arrow, **kw
        )

    aimed = AttackDefinition(
        "r_aimed",
        damage=scaled("dexterity", 1.7, extra={"power": 0.3}),
        knockback=90,
        critical_chance_stat="crit",
        critical_multiplier=2.2,
    )
    caster(
        "r_aimed",
        "Aimed Shot",
        5,
        1.2,
        [(0.2, {})],
        aimed,
        arrow_def("aimed_arrow", aimed),
        length=0.45,
        armor=0.25,
    )
    buff_skill("r_deadeye", "Deadeye", 10, 14.0, "deadeye")
    snipe = AttackDefinition(
        "r_snipe",
        damage=scaled("dexterity", 3.4, extra={"power": 0.5}),
        knockback=240,
        knockdown=True,
        critical_chance_stat="crit",
        critical_multiplier=2.5,
    )
    caster(
        "r_snipe",
        "Snipe",
        14,
        5.0,
        [(0.55, {})],
        snipe,
        arrow_def("snipe_bolt", snipe, 620.0, 1.0, pierce=-1, width=10, height=10),
        length=0.8,
        armor=0.6,
    )
    rail = AttackDefinition(
        "r_railshot",
        damage=scaled("dexterity", 5.0, extra={"power": 0.8}),
        knockback=280,
        knockdown=True,
        critical_chance_stat="crit",
        critical_multiplier=2.0,
        hitstop=0.06,
    )
    caster(
        "r_railshot",
        "Rail Shot",
        24,
        10.0,
        [(0.7, {})],
        rail,
        arrow_def("rail", rail, 820.0, 1.0, pierce=-1, width=16, height=16),
        length=1.0,
        armor=0.85,
    )
    poison = {"state": "poisoned", "chance": 1.0}
    venom = AttackDefinition(
        "r_poison_arrow",
        damage=scaled("dexterity", 0.9, extra={"poison_dmg": 1.0}),
        tags=["damage.dark"],
        knockback=40,
        apply_states=[poison],
    )
    caster(
        "r_poison_arrow",
        "Poison Arrow",
        4,
        1.0,
        [(0.1, {})],
        venom,
        arrow_def("poison_arrow", venom, 320.0),
        length=0.35,
        tags=("damage.dark",),
    )
    melee(
        "r_caltrops",
        "Caltrops",
        8,
        5.0,
        [(0.2, dict(width=72, height=52))],
        AttackDefinition(
            "r_caltrops",
            damage=scaled("dexterity", 0.6, extra={"poison_dmg": 1.0}),
            tags=["damage.dark"],
            knockback=30,
            apply_states=[poison],
        ),
        length=0.45,
        iframes=0.25,
        tags=("damage.dark",),
    )
    skills[-1].cues.insert(1, move("back", 0.0, 210, 0.18, x=-1))
    melee(
        "r_toxic_cloud",
        "Toxic Cloud",
        14,
        7.0,
        [(at, dict(width=64, height=64, offset_x=30)) for at in (0.2, 0.5, 0.8)],
        AttackDefinition(
            "r_toxic_cloud",
            damage=scaled("dexterity", 0.5, extra={"poison_dmg": 1.2}),
            tags=["damage.dark"],
            knockback=20,
            apply_states=[poison],
        ),
        length=1.1,
        tags=("damage.dark",),
    )
    rain = AttackDefinition(
        "r_venom_rain",
        damage=scaled("dexterity", 0.7, extra={"poison_dmg": 0.8}),
        tags=["damage.dark"],
        apply_states=[{"state": "poisoned", "chance": 0.7}],
    )
    caster(
        "r_venom_rain",
        "Venom Rain",
        16,
        6.0,
        [(0.15, dict(count=9, spread=100))],
        rain,
        arrow_def("venom_arrow", rain, 300.0),
        length=0.55,
        tags=("damage.dark",),
    )
    melee(
        "r_plague",
        "Plague",
        22,
        12.0,
        [(0.2, dict(width=124, height=124))],
        AttackDefinition(
            "r_plague",
            damage=scaled("dexterity", 1.2, extra={"poison_dmg": 2.0}),
            tags=["damage.dark"],
            knockback=60,
            hitstun=0.3,
            apply_states=[poison, {"state": "shocked", "chance": 1.0}],
        ),
        length=0.6,
        armor=0.5,
        tags=("damage.dark",),
    )
    fan = AttackDefinition(
        "r_fan",
        damage=scaled("dexterity", 0.7, extra={"power": 0.2}),
        knockback=50,
        critical_chance_stat="crit",
        critical_multiplier=1.8,
    )
    caster(
        "r_fan",
        "Fan of Arrows",
        6,
        1.6,
        [(0.1, dict(count=5, spread=90))],
        fan,
        arrow_def("fan_arrow", fan),
        length=0.4,
    )
    shadow = AttackDefinition(
        "r_shadow_step",
        damage=scaled("dexterity", 0.8),
        knockback=60,
        critical_chance_stat="crit",
        critical_multiplier=2.0,
    )
    caster(
        "r_shadow_step",
        "Shadow Step",
        8,
        3.0,
        [(0.18, dict(count=3, spread=20))],
        shadow,
        arrow_def("shadow_arrow", shadow),
        length=0.4,
    )
    skills[-1].cues[:0] = [_iframes(0.35), move("step", 0.0, 300, 0.15)]
    skills[-1].interrupts = True
    rapid = AttackDefinition(
        "r_rapid_fire",
        damage=scaled("dexterity", 0.8, extra={"power": 0.2}),
        knockback=30,
        critical_chance_stat="crit",
        critical_multiplier=1.9,
    )
    caster(
        "r_rapid_fire",
        "Rapid Fire",
        18,
        8.0,
        [(0.05 + 0.1 * i, dict(spread=14)) for i in range(7)],
        rapid,
        arrow_def("rapid_arrow", rapid, 420.0, 0.8),
        length=0.85,
        armor=0.75,
    )

    # -- mage: pyromancer (fire, burn), cryomancer (ice, control), stormcaller (lightning) -----
    burn = {"state": "burning", "chance": 0.6}
    chill = {"state": "chilled", "chance": 1.0}
    shock = {"state": "shocked", "chance": 0.7}
    magic = ("magic",)
    melee(
        "m_flame_wave",
        "Flame Wave",
        8,
        1.8,
        [
            (0.15, dict(width=56, height=42, offset_x=22)),
            (0.3, dict(width=56, height=42, offset_x=22)),
        ],
        _fire(
            "m_flame_wave",
            damage=scaled("magic", 1.0, defense=0.2, extra={"fire_dmg": 1.0}),
            knockback=60,
            apply_states=[burn],
        ),
        length=0.5,
        tags=magic,
    )
    ball = _fire(
        "m_fireball",
        damage=scaled("magic", 1.8, defense=0.2, extra={"fire_dmg": 1.0}),
        knockback=140,
        hitstun=0.25,
        apply_states=[{"state": "burning", "chance": 0.5}],
    )
    caster(
        "m_fireball",
        "Fireball",
        12,
        2.5,
        [(0.25, {})],
        ball,
        ProjectileDefinition(
            "fireball_shot",
            attack_id="m_fireball",
            speed=200,
            lifetime=1.2,
            width=22,
            height=22,
            sprite=big_fire,
        ),
        length=0.55,
        armor=0.3,
        tags=magic,
    )
    melee(
        "m_inferno",
        "Inferno",
        22,
        9.0,
        [(0.1 + 0.2 * i, dict(width=78, height=78)) for i in range(4)],
        _fire(
            "m_inferno",
            damage=scaled("magic", 0.8, defense=0.2, extra={"fire_dmg": 1.0}),
            knockback=40,
            apply_states=[{"state": "burning", "chance": 0.8}],
        ),
        length=0.95,
        armor=0.85,
        tags=magic,
    )
    storm = _fire(
        "m_firestorm",
        damage=scaled("magic", 1.6, defense=0.2, extra={"fire_dmg": 1.2}),
        knockback=200,
        knockdown=True,
        poise_damage=40,
        apply_states=[{"state": "burning", "chance": 1.0}],
    )
    caster(
        "m_firestorm",
        "Firestorm",
        34,
        14.0,
        [(0.3, dict(count=5, spread=120))],
        storm,
        ProjectileDefinition(
            "firestorm_meteor",
            attack_id="m_firestorm",
            speed=160,
            lifetime=1.3,
            width=24,
            height=24,
            pierce=-1,
            sprite=big_fire,
        ),
        length=0.8,
        armor=0.9,
        tags=magic,
    )
    bolt = AttackDefinition(
        "m_frost_bolt",
        damage=scaled("magic", 1.0, defense=0.2, extra={"cold_dmg": 1.0}),
        tags=["Element.Ice"],
        knockback=60,
        apply_states=[chill],
    )
    caster(
        "m_frost_bolt",
        "Frost Bolt",
        3,
        0.5,
        [(0.1, {})],
        bolt,
        ProjectileDefinition(
            "frost_bolt", attack_id="m_frost_bolt", speed=260, lifetime=1.2, sprite=ice
        ),
        length=0.3,
        tags=magic,
    )
    spike = AttackDefinition(
        "m_ice_spike",
        damage=scaled("magic", 1.2, defense=0.2, extra={"cold_dmg": 1.0}),
        tags=["Element.Ice"],
        knockback=100,
        apply_states=[chill],
    )
    caster(
        "m_ice_spike",
        "Ice Spikes",
        9,
        2.0,
        [(0.15, dict(count=3, spread=12))],
        spike,
        ProjectileDefinition(
            "ice_spike", attack_id="m_ice_spike", speed=340, lifetime=0.9, pierce=-1, sprite=ice
        ),
        length=0.45,
        tags=magic,
    )
    melee(
        "m_blizzard",
        "Blizzard",
        24,
        10.0,
        [(0.1 + 0.2 * i, dict(width=92, height=92, offset_x=36)) for i in range(5)],
        AttackDefinition(
            "m_blizzard",
            damage=scaled("magic", 0.7, defense=0.2, extra={"cold_dmg": 1.0}),
            tags=["Element.Ice"],
            knockback=30,
            apply_states=[chill],
        ),
        length=1.2,
        armor=1.0,
        tags=magic,
    )
    orbit = AttackDefinition(
        "m_frozen_orb",
        damage=scaled("magic", 1.4, defense=0.2, extra={"cold_dmg": 1.2}),
        tags=["Element.Ice"],
        knockback=50,
        apply_states=[chill],
    )
    caster(
        "m_frozen_orb",
        "Frozen Orb",
        28,
        12.0,
        [(0.3, {})],
        orbit,
        ProjectileDefinition(
            "frozen_orb",
            attack_id="m_frozen_orb",
            speed=110,
            lifetime=2.6,
            width=34,
            height=34,
            pierce=-1,
            sprite=ice,
        ),
        length=0.7,
        armor=0.7,
        tags=magic,
    )
    chain = AttackDefinition(
        "m_chain_lightning",
        damage=scaled("magic", 1.2, defense=0.2, extra={"shock_dmg": 1.0}),
        tags=["Element.Lightning"],
        knockback=40,
        critical_chance_stat="crit",
        critical_multiplier=1.8,
        apply_states=[shock],
    )
    caster(
        "m_chain_lightning",
        "Chain Lightning",
        7,
        1.2,
        [(0.1, {})],
        chain,
        ProjectileDefinition(
            "lightning_bolt",
            attack_id="m_chain_lightning",
            speed=340,
            lifetime=1.0,
            homing_turn=420,
            homing_range=170,
            pierce=3,
            sprite=bolt,
        ),
        length=0.35,
        tags=magic,
    )
    melee(
        "m_lightning_strike",
        "Lightning Strike",
        12,
        3.0,
        [(0.3, dict(width=46, height=46, offset_x=62))],
        AttackDefinition(
            "m_lightning_strike",
            damage=scaled("magic", 2.4, defense=0.2, extra={"shock_dmg": 1.2}),
            tags=["Element.Lightning"],
            knockback=160,
            knockdown=True,
            critical_chance_stat="crit",
            critical_multiplier=2.0,
            apply_states=[{"state": "shocked", "chance": 1.0}],
        ),
        length=0.55,
        tags=magic,
    )
    offsets = ((46, -30), (-46, -30), (46, 30), (-46, 30))
    melee(
        "m_thunderstorm",
        "Thunderstorm",
        24,
        10.0,
        [
            (0.15 + 0.2 * i, dict(width=52, height=52, offset_x=x, offset_y=y))
            for i, (x, y) in enumerate(offsets)
        ],
        AttackDefinition(
            "m_thunderstorm",
            damage=scaled("magic", 1.3, defense=0.2, extra={"shock_dmg": 1.0}),
            tags=["Element.Lightning"],
            knockback=90,
            hitstun=0.2,
            critical_chance_stat="crit",
            critical_multiplier=1.8,
            apply_states=[shock],
        ),
        length=1.0,
        armor=0.9,
        tags=magic,
    )
    buff_skill("m_overload", "Overload", 20, 20.0, "overload")
    return skills


# damage of each build relative to the others (set by scripts/arpg_balance.py)
BUILD_DAMAGE = {
    "berserker": 0.26,
    "guardian": 1.32,
    "warlord": 1.65,
    "marksman": 1.89,
    "venomancer": 3.61,
    "skirmisher": 0.65,
    "pyromancer": 0.75,
    "cryomancer": 1.05,
    "stormcaller": 1.4,
}


def _build_of():
    return {a: b[0] for branches in BRANCHES.values() for b in branches for a in b[2]}


def _tuned(attack, factor):
    """``attack`` with its stat-scaled damage terms multiplied by ``factor``."""
    from dataclasses import replace

    if factor == 1.0 or attack.damage is None:
        return attack
    terms = [
        FormulaTerm(t.source, t.key, t.coefficient * factor) if t.source == "source_stat" else t
        for t in attack.damage.terms
    ]
    return replace(attack, damage=ValueFormula(terms, minimum=1))


def register(library, looks):
    """Add the states, attacks, projectiles, timelines and abilities; returns ``{id: name}``."""
    for state in states():
        library.add_state(state)
    labels = {}
    build_of = _build_of()
    for skill in build_skills(looks):
        if skill.attack is not None:
            library.add_attack(_tuned(skill.attack, BUILD_DAMAGE[build_of[skill.ability_id]]))
        if skill.projectile is not None:
            library.add_projectile(skill.projectile)
        library.add_timeline(ActionTimeline(skill.ability_id, skill.cues))
        costs = [AbilityCost("mp", skill.mp)] if skill.mp else []
        library.add_ability(
            AbilityDefinition(
                skill.ability_id,
                timeline_id=skill.ability_id,
                cooldown_seconds=skill.cooldown,
                costs=costs,
                interrupts_actions=skill.interrupts,
                tags=skill.tags,
                display_name=skill.name,
            )
        )
        labels[skill.ability_id] = skill.name
    return labels


# -- the trees ------------------------------------------------------------------------------------
def node(
    node_id,
    name,
    *,
    ranks=1,
    cost=1,
    stats=None,
    resources=None,
    abilities=(),
    needs=(),
    group=None,
):
    reward = ProgressionNodeReward(
        stat_bonuses=stats or {}, resource_bonuses=resources or {}, granted_abilities=abilities
    )
    requirements = [
        ProgressionNodeRequirement(*(n if isinstance(n, tuple) else (n,))) for n in needs
    ]
    return ProgressionNodeDefinition(
        node_id,
        name,
        max_rank=ranks,
        rank_costs={"ap": cost},
        rewards=reward,
        prerequisites=requirements,
        exclusive_group=group,
    )


# (class, branch id, title, five skills in order, three passives, keystone)
BRANCHES = {
    "warrior": (
        (
            "berserker",
            "Berserker",
            ["w_rend", "w_whirl", "w_frenzy", "w_execute", "w_rampage"],
            [
                ("w_might", "Might", 5, {"power": 3}, None),
                ("w_rage", "Bloodlust", 3, {"power": 5, "dexterity": 2}, None),
                ("w_savage", "Savagery", 5, {"crit": 2}, None),
            ],
            ("w_pact", "Blood Pact", {"power": 12, "crit": 8}, None),
        ),
        (
            "guardian",
            "Guardian",
            ["w_shield_bash", "w_fortify", "w_ground_slam", "w_retribution", "w_bulwark"],
            [
                ("w_skin", "Iron Skin", 5, {"defense": 2}, None),
                ("w_vigor", "Vigor", 3, {}, {"hp": 30}),
                ("w_bastion", "Bastion", 3, {"defense": 2}, {"hp": 20}),
            ],
            ("w_unbreakable", "Unbreakable", {"defense": 8}, {"hp": 80}),
        ),
        (
            "warlord",
            "Warlord",
            ["w_cleave", "w_leap", "w_shout", "w_thunderclap", "w_earthquake"],
            [
                ("w_command", "Command", 5, {"power": 2, "defense": 1}, None),
                ("w_mettle", "Mettle", 3, {"defense": 2}, {"mp": 10}),
                ("w_storm", "Stormcalling", 5, {"shock_dmg": 3}, None),
            ],
            ("w_mantle", "Warlord's Mantle", {"power": 6, "defense": 6}, {"mp": 30}),
        ),
    ),
    "ranger": (
        (
            "marksman",
            "Marksman",
            ["r_aimed", "r_pierce", "r_deadeye", "r_snipe", "r_railshot"],
            [
                ("r_eye", "Eagle Eye", 5, {"dexterity": 3}, None),
                ("r_focus", "Focus", 5, {"crit": 2}, None),
                ("r_steady", "Steady Hands", 3, {"power": 3, "dexterity": 2}, None),
            ],
            ("r_dead_aim", "Dead Aim", {"crit": 12, "dexterity": 10}, None),
        ),
        (
            "venomancer",
            "Venomancer",
            ["r_poison_arrow", "r_caltrops", "r_toxic_cloud", "r_venom_rain", "r_plague"],
            [
                ("r_toxins", "Toxins", 5, {"poison_dmg": 3}, None),
                ("r_potency", "Potency", 3, {"poison_dmg": 4, "dexterity": 2}, None),
                ("r_resist", "Antivenom", 3, {"defense": 3}, {"hp": 25}),
            ],
            ("r_plaguebearer", "Plaguebearer", {"poison_dmg": 16}, None),
        ),
        (
            "skirmisher",
            "Skirmisher",
            ["r_volley", "r_fan", "r_tumble", "r_shadow_step", "r_rapid_fire"],
            [
                ("r_multi", "Multishot", 2, {"multishot": 1}, None),
                ("r_hunt", "Hunter", 3, {"power": 3, "dexterity": 2}, None),
                ("r_wind", "Second Wind", 3, {}, {"mp": 15}),
            ],
            ("r_windrunner", "Windrunner", {"multishot": 1, "dexterity": 8}, None),
        ),
    ),
    "mage": (
        (
            "pyromancer",
            "Pyromancer",
            ["m_flame_wave", "m_fireball", "m_meteor", "m_inferno", "m_firestorm"],
            [
                ("m_focus", "Focus", 5, {"magic": 3}, None),
                ("m_ignite", "Ignite", 5, {"fire_dmg": 3}, None),
                ("m_ember", "Embers", 3, {"fire_dmg": 3, "crit": 2}, None),
            ],
            ("m_phoenix", "Phoenix Heart", {"fire_dmg": 16, "magic": 8}, None),
        ),
        (
            "cryomancer",
            "Cryomancer",
            ["m_frost_bolt", "m_nova", "m_ice_spike", "m_blizzard", "m_frozen_orb"],
            [
                ("m_mana", "Deep Mana", 5, {}, {"mp": 20}),
                ("m_chill", "Chill", 5, {"cold_dmg": 3}, None),
                ("m_shatter", "Shatter", 3, {"cold_dmg": 3, "crit": 2}, None),
            ],
            ("m_winter", "Winter's Grasp", {"cold_dmg": 16, "defense": 5}, {"hp": 40}),
        ),
        (
            "stormcaller",
            "Stormcaller",
            ["m_chain_lightning", "m_lightning_strike", "m_blink", "m_thunderstorm", "m_overload"],
            [
                ("m_power", "Archmage", 3, {"magic": 6}, None),
                ("m_static", "Static", 5, {"shock_dmg": 3}, None),
                ("m_ward", "Mana Shield", 3, {"defense": 3}, {"hp": 20}),
            ],
            ("m_tempest", "Tempest Core", {"shock_dmg": 16, "magic": 8}, {"mp": 30}),
        ),
    ),
}
TREE_NAMES = {"warrior": "Warrior Arts", "ranger": "Ranger Craft", "mage": "Arcane Lore"}


def trees(skill_names):
    """``{graph id: (name, [(node, (x, y))])}`` for the three classes: each build is a column of
    five skills and three passives, closed by an exclusive keystone; nodes lead to each other."""
    result = {}
    for class_id, branches in BRANCHES.items():
        nodes = []
        for column, (_branch, _title, skills, passives, keystone) in enumerate(branches):
            x = (column - 1) * 400
            p1, p2, p3 = passives

            def need(spec, rank):  # a passive's own rank limit caps the rank asked for
                return (spec[0], min(rank, spec[2]))

            s1, s2, s3, s4, s5 = skills
            costs = (1, 1, 2, 2, 3)

            def skill_node(index, needs=(), s=skills, costs=costs):
                ability = s[index]
                return node(
                    ability,
                    skill_names[ability],
                    cost=costs[index],
                    abilities=(ability,),
                    needs=needs,
                )

            def passive(spec, needs=(), cost=1):
                pid, name, ranks, stats, resources = spec
                return node(
                    pid,
                    name,
                    ranks=ranks,
                    cost=cost,
                    stats=stats,
                    resources=resources,
                    needs=needs,
                )

            rows = [  # skills down the left column, passives and the keystone down the right
                (skill_node(0), (x, 0)),
                (skill_node(1, [s1]), (x, 90)),
                (skill_node(2, [s1, need(p1, 2)]), (x, 180)),
                (skill_node(3, [s2, s3]), (x, 270)),
                (skill_node(4, [s4, need(p2, 3)]), (x, 360)),
                (passive(p1), (x + 170, 0)),
                (passive(p2, [need(p1, 3)]), (x + 170, 90)),
                (passive(p3, [need(p2, 3)], cost=2), (x + 170, 180)),
            ]
            kid, kname, kstats, kres = keystone
            rows.append(
                (
                    node(
                        kid,
                        kname,
                        cost=3,
                        stats=kstats,
                        resources=kres,
                        needs=[s4, need(p1, 4)],
                        group=f"{class_id}_keystone",
                    ),
                    (x + 170, 270),
                )
            )
            nodes.extend(rows)
        result[f"{class_id}_tree"] = (TREE_NAMES[class_id], class_id, nodes)
    return result


def add_trees(db, skill_names):
    for graph_id, (name, class_id, nodes) in trees(skill_names).items():
        db.add_progression_graph(
            ProgressionGraphDefinition(
                graph_id,
                name,
                nodes=[n for n, _ in nodes],
                tags=(f"class:{class_id}",),
                editor_view="graph",
                node_positions={n.node_id: p for n, p in nodes},
            )
        )


# -- picture effects ------------------------------------------------------------------------------
# ability id: [(effect, at, offset_x, offset_y, scale, flags)]; ``rotate`` turns the picture to
# the aim, ``follow`` keeps it on the user, offsets run along the aim
SKILL_FX = {
    "w_slash1": [("wind", 0.06, 16, 0, 0.6, "rotate")],
    "w_slash2": [("wind", 0.06, 16, 0, 0.6, "rotate")],
    "w_slash3": [("blood_arc", 0.1, 20, 0, 0.9, "rotate")],
    "w_whirl": [("wind", 0.05, 0, 0, 1.8, ""), ("wind", 0.25, 0, 0, 1.8, "")],
    "w_leap": [("spike", 0.25, 12, 0, 1.1, "")],
    "w_shout": [("gold_burst", 0.1, 0, 0, 1.2, "follow")],
    "w_rend": [("blood_arc", 0.08, 16, 0, 0.7, "rotate")],
    "w_frenzy": [("blood_arc", 0.1, 0, 0, 1.2, "follow")],
    "w_execute": [("blood_arc", 0.18, 22, 0, 1.0, "rotate")],
    "w_rampage": [("blood_arc", at, 18, 0, 0.8, "rotate") for at in (0.08, 0.28, 0.48)],
    "w_shield_bash": [("gold_burst", 0.1, 18, 0, 0.5, "")],
    "w_fortify": [("gold_burst", 0.1, 0, 0, 1.0, "follow")],
    "w_ground_slam": [("spike", 0.4, 0, 0, 1.5, ""), ("rocks", 0.4, 0, 0, 1.5, "")],
    "w_retribution": [("gold_burst", at, 0, 0, 1.8, "") for at in (0.15, 0.35)],
    "w_bulwark": [("gold_burst", 0.1, 0, 0, 1.4, "follow")],
    "w_cleave": [("wind", 0.08, 18, 0, 1.0, "rotate")],
    "w_thunderclap": [("bolt_burst", 0.15, 0, 0, 2.0, "")],
    "w_earthquake": [("spike", at, 0, 0, 2.0, "") for at in (0.2, 0.5, 0.8)],
    "r_aimed": [("spark_arc", 0.2, 12, 0, 0.5, "rotate")],
    "r_pierce": [("spark_arc", 0.25, 12, 0, 0.7, "rotate")],
    "r_snipe": [("spark_arc", 0.55, 14, 0, 0.9, "rotate")],
    "r_railshot": [("spark_arc", 0.7, 16, 0, 1.2, "rotate")],
    "r_deadeye": [("gold_burst", 0.1, 0, 0, 1.0, "follow")],
    "r_tumble": [("wind", 0.0, -8, 0, 0.8, "rotate")],
    "r_caltrops": [("rocks", 0.2, 0, 0, 1.4, "")],
    "r_toxic_cloud": [("poison_cloud", at, 30, 0, 1.3, "") for at in (0.2, 0.5, 0.8)],
    "r_venom_rain": [("poison_cloud", 0.15, 40, 0, 0.9, "")],
    "r_plague": [("poison_burst", 0.2, 0, 0, 2.6, "")],
    "r_shadow_step": [
        ("shadow_portal", 0.0, 0, 0, 0.9, ""),
        ("shadow_portal", 0.15, 40, 0, 0.9, ""),
    ],
    "m_flame_wave": [("ember_arc", at, 24, 0, 1.1, "rotate") for at in (0.15, 0.3)],
    "m_inferno": [("explosion", 0.1 + 0.2 * i, 0, 0, 1.8, "") for i in range(4)],
    "m_nova": [("ice_burst", 0.08, 0, 0, 2.2, "")],
    "m_blizzard": [("geyser", 0.1 + 0.2 * i, 36, (-1) ** i * 24, 1.4, "") for i in range(5)],
    "m_blink": [("shadow_portal", 0.0, 0, 0, 0.9, ""), ("shadow_portal", 0.12, 70, 0, 0.9, "")],
    "m_lightning_strike": [("bolt_strike", 0.3, 62, 0, 1.3, "")],
    "m_thunderstorm": [
        ("bolt_strike", 0.15 + 0.2 * i, x, y, 1.1, "")
        for i, (x, y) in enumerate(((46, -30), (-46, -30), (46, 30), (-46, 30)))
    ],
    "m_overload": [("bolt_burst", 0.1, 0, 0, 1.4, "follow")],
    "cyclops_smash": [("spike", 0.55, 16, 0, 1.6, "")],
    "golem_slam": [("spike", 0.45, 12, 0, 1.8, "")],
}


def fx_cues(looks, ability_id):
    """The ``vfx`` cues of one ability."""
    cues = []
    for index, (name, at, ox, oy, scale, flags) in enumerate(SKILL_FX.get(ability_id, ())):
        payload = {
            "effect": looks[f"fx_{name}"],
            "offset_x": ox,
            "offset_y": oy,
            "scale": scale,
            "frame_duration": 0.05,
            "aim": True,
        }
        if "rotate" in flags:
            payload["rotate"] = True
        if "follow" in flags:
            payload["follow"] = True
        cues.append(ActionCue(f"vfx_{name}_{index}", at, "vfx", payload))
    return cues


def add_effects(library, looks):
    """Give every ability that has effects its ``vfx`` cues (adds to the timeline)."""
    for ability_id in SKILL_FX:
        ability = library.abilities.get(ability_id)
        timeline = library.timelines.get(ability.timeline_id) if ability is not None else None
        if timeline is None:
            continue
        cues = [*timeline.cues, *fx_cues(looks, ability_id)]
        library.timelines[timeline.timeline_id] = ActionTimeline(timeline.timeline_id, cues)


# -- the body's animation ---------------------------------------------------------------------
# which of the three attack strips (or the jump) each skill plays: a combo's hits and the skills
# do not all swing the same way
ANIMATION = {
    # buffs and spells are cast: the second strip
    **dict.fromkeys(
        (
            "w_slash2",
            "w_shout",
            "w_frenzy",
            "w_fortify",
            "w_bulwark",
            "w_thunderclap",
            "r_deadeye",
            "r_volley",
            "r_fan",
            "r_venom_rain",
            "r_toxic_cloud",
            "m_bolt",
            "m_fireball",
            "m_frost_bolt",
            "m_nova",
            "m_flame_wave",
            "m_ice_spike",
            "m_chain_lightning",
            "m_lightning_strike",
            "m_overload",
        ),
        "attack2",
    ),
    # the finishers and the heavy blows: the third strip
    **dict.fromkeys(
        (
            "w_slash3",
            "w_whirl",
            "w_execute",
            "w_rampage",
            "w_shield_bash",
            "w_retribution",
            "w_cleave",
            "r_pierce",
            "r_snipe",
            "r_railshot",
            "r_plague",
            "r_rapid_fire",
            "m_meteor",
            "m_inferno",
            "m_firestorm",
            "m_blizzard",
            "m_frozen_orb",
            "m_thunderstorm",
        ),
        "attack3",
    ),
    **dict.fromkeys(("w_leap", "w_ground_slam", "w_earthquake"), "jump"),
    **dict.fromkeys(("r_tumble", "r_caltrops", "r_shadow_step"), "jump"),
    "m_blink": "jump",
}


def assign_animations(library):
    """Point each listed skill's animation cue at its strip (one is added when it has none)."""
    for ability_id, role in ANIMATION.items():
        ability = library.abilities.get(ability_id)
        timeline = library.timelines.get(ability.timeline_id) if ability is not None else None
        if timeline is None:
            continue
        cues = [c for c in timeline.cues if c.kind.value != "animation"]
        cues.append(ActionCue(f"anim_{role}", 0.0, "animation", {"clip": role}))
        library.timelines[timeline.timeline_id] = ActionTimeline(timeline.timeline_id, cues)
