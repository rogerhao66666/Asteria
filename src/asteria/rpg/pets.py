"""Pets: creatures the player owns, names, levels up and sends out (Pokemon-style).

A **species** (:class:`PetSpeciesDefinition`, project data) gives base stats and growth per level;
an **owned pet** (:class:`PetRecord`, save data) is one creature: its species, a nickname, a level
and experience. A pet is not a battle unit: abilities that name it (``requires_pet``) are sent out
by a character and read its stats as ``pet_<stat>`` (plus ``pet_level``) in their formulas, so a
higher-level pet hits harder. Which pet is sent is the *active pet*.

A project can also run a **creature party** (:class:`PetRules`, Game Systems > Pet Rules): pets
fight as units in a party of at most ``party_size`` with ``battle_slots`` on the stage and the
rest on the bench, the others waiting in storage; each owned pet then keeps its own resources,
states, moves, uses (PP), held item and *genes* (individual numbers a stat formula reads).
Nothing here is a rule of one game: every number and name is project data.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


def _text(value, label, *, required=True):
    value = str(value or "").strip()
    if required and not value:
        raise ValueError(f"{label} is required")
    return value


@dataclass(frozen=True, slots=True)
class PetEvolution:
    """One way a species turns into another. A pet qualifies when every set condition holds:
    ``min_level``, ``min_affinity`` and the bag item ``item_id`` (spent when ``consume_item``).
    ``automatic`` evolutions happen as soon as the conditions hold (after a battle); others
    wait for ``evolve_pet`` (an item, a menu)."""

    to_species_id: str
    min_level: int = 0
    min_affinity: float = 0.0
    item_id: str = ""
    consume_item: bool = True
    automatic: bool = True

    def __post_init__(self):
        object.__setattr__(self, "to_species_id", _text(self.to_species_id, "to_species_id"))
        object.__setattr__(self, "min_level", max(0, int(self.min_level)))
        object.__setattr__(self, "min_affinity", max(0.0, float(self.min_affinity)))
        object.__setattr__(self, "item_id", _text(self.item_id, "item_id", required=False))

    def to_data(self):
        return {
            "to_species_id": self.to_species_id,
            **({"min_level": self.min_level} if self.min_level else {}),
            **({"min_affinity": self.min_affinity} if self.min_affinity else {}),
            **({"item_id": self.item_id} if self.item_id else {}),
            **({"consume_item": False} if not self.consume_item else {}),
            **({"automatic": False} if not self.automatic else {}),
        }

    @classmethod
    def from_data(cls, data):
        return cls(
            data["to_species_id"],
            data.get("min_level", 0),
            data.get("min_affinity", 0.0),
            data.get("item_id", ""),
            data.get("consume_item", True),
            data.get("automatic", True),
        )


@dataclass(frozen=True, slots=True)
class PetMove:
    """An ability a pet learns: at ``level`` (and ``min_affinity``) it joins the pet's known
    abilities. An ability that appears in a species' learnset can only be used while the active
    pet of that species knows it."""

    ability_id: str
    level: int = 1
    min_affinity: float = 0.0

    def __post_init__(self):
        object.__setattr__(self, "ability_id", _text(self.ability_id, "ability_id"))
        object.__setattr__(self, "level", max(1, int(self.level)))
        object.__setattr__(self, "min_affinity", max(0.0, float(self.min_affinity)))

    def to_data(self):
        return {
            "ability_id": self.ability_id,
            **({"level": self.level} if self.level != 1 else {}),
            **({"min_affinity": self.min_affinity} if self.min_affinity else {}),
        }

    @classmethod
    def from_data(cls, data):
        return cls(data["ability_id"], data.get("level", 1), data.get("min_affinity", 0.0))


def _numbers(values, label):
    result = {}
    for key, value in dict(values or {}).items():
        key = _text(key, f"{label} name")
        value = float(value)
        if not isfinite(value):
            raise ValueError(f"{label} {key} must be finite")
        result[key] = value
    return result


@dataclass(frozen=True, slots=True)
class PetStatFormula:
    """How a pet stat grows when the project does not use the species' linear growth::

        stat = floor((base_scale x base + sum(gene_terms[k] x genes[k.stat])) x level
                     / level_divisor) + level_term x level + flat
        stat = stat x genes[multiplier_gene.stat]   (when ``multiplier_gene`` is set, default 1)

    ``base`` is the species' stat (``PetSpeciesDefinition.stats``); ``genes`` are the owned
    pet's own numbers (``PetRecord.genes``, e.g. ``iv.attack``, ``ev.attack``,
    ``nature.attack``). ``round_down`` floors the first part. Generation-IV style creature
    games set base_scale 2, gene_terms {iv: 1, ev: 0.25}, level_divisor 100, flat 5 and, for
    hit points, level_term 1 and flat 10 - but any coefficients are allowed."""

    base_scale: float = 2.0
    gene_terms: dict = None
    level_divisor: float = 100.0
    level_term: float = 0.0
    flat: float = 5.0
    multiplier_gene: str = ""
    round_down: bool = True

    def __init__(
        self,
        base_scale=2.0,
        gene_terms=None,
        level_divisor=100.0,
        level_term=0.0,
        flat=5.0,
        multiplier_gene="",
        round_down=True,
    ):
        s = object.__setattr__
        for name, value in (
            ("base_scale", base_scale),
            ("level_divisor", level_divisor),
            ("level_term", level_term),
            ("flat", flat),
        ):
            value = float(value)
            if not isfinite(value):
                raise ValueError(f"{name} must be finite")
            s(self, name, value)
        if self.level_divisor <= 0:
            raise ValueError("level_divisor must be > 0")
        s(self, "gene_terms", _numbers(gene_terms, "gene term"))
        s(self, "multiplier_gene", _text(multiplier_gene, "multiplier_gene", required=False))
        s(self, "round_down", bool(round_down))

    def value(self, base, level, stat_name, genes=None):
        genes = genes or {}
        total = self.base_scale * float(base)
        for gene, coefficient in self.gene_terms.items():
            total += coefficient * float(genes.get(f"{gene}.{stat_name}", 0.0))
        total = total * max(1, int(level)) / self.level_divisor
        if self.round_down:
            total = float(int(total))
        total += self.level_term * max(1, int(level)) + self.flat
        if self.multiplier_gene:
            total *= float(genes.get(f"{self.multiplier_gene}.{stat_name}", 1.0))
            if self.round_down:
                total = float(int(total))
        return total

    def to_data(self):
        return {
            "base_scale": self.base_scale,
            "gene_terms": dict(self.gene_terms),
            "level_divisor": self.level_divisor,
            "level_term": self.level_term,
            "flat": self.flat,
            **({"multiplier_gene": self.multiplier_gene} if self.multiplier_gene else {}),
            **({"round_down": False} if not self.round_down else {}),
        }

    @classmethod
    def from_data(cls, data):
        return cls(
            data.get("base_scale", 2.0),
            data.get("gene_terms"),
            data.get("level_divisor", 100.0),
            data.get("level_term", 0.0),
            data.get("flat", 5.0),
            data.get("multiplier_gene", ""),
            data.get("round_down", True),
        )


@dataclass(frozen=True, slots=True)
class PetExpCurve:
    """Total experience needed to *be* at a level, instead of ``exp_base x level`` per level:
    a cubic ``a L^3 + b L^2 + c L + d`` (floored, never below 0) or a ``table`` of totals by
    level (index 1 = level 1; levels past its end keep growing by its last step)."""

    cubic: tuple = ()
    table: tuple = ()

    def __init__(self, cubic=(), table=()):
        cubic = tuple(float(x) for x in cubic)
        table = tuple(float(x) for x in table)
        if bool(cubic) == bool(table):
            raise ValueError("an exp curve needs a cubic (a, b, c, d) or a table, not both")
        if cubic and (len(cubic) != 4 or not all(isfinite(x) for x in cubic)):
            raise ValueError("cubic must be four finite coefficients (a, b, c, d)")
        if table and (len(table) < 2 or any(y < x for x, y in zip(table, table[1:]))):
            raise ValueError("table must list at least two non-decreasing totals")
        object.__setattr__(self, "cubic", cubic)
        object.__setattr__(self, "table", table)

    def total_at(self, level):
        level = max(1, int(level))
        if self.cubic:
            a, b, c, d = self.cubic
            return max(0.0, float(int(a * level**3 + b * level**2 + c * level + d)))
        if level <= len(self.table):
            return self.table[level - 1]
        step = self.table[-1] - self.table[-2]
        return self.table[-1] + step * (level - len(self.table))

    def to_next(self, level):
        return max(1.0, self.total_at(level + 1) - self.total_at(level))

    def to_data(self):
        return {"cubic": list(self.cubic)} if self.cubic else {"table": list(self.table)}

    @classmethod
    def from_data(cls, data):
        return cls(data.get("cubic", ()), data.get("table", ()))


@dataclass(frozen=True, slots=True)
class PetSpeciesDefinition:
    """``stats[name] + growth[name] * (level - 1)`` is a pet stat at ``level``; reaching the next
    level takes ``exp_base * level`` experience; ``max_level`` stops growth; a pet sent out in a
    won battle gains ``exp_per_battle``."""

    species_id: str
    display_name: str
    stats: dict
    growth: dict
    max_level: int = 50
    exp_base: float = 40.0
    exp_per_battle: float = 30.0
    icon_id: str = ""
    tags: tuple = ()
    evolutions: tuple = ()
    learnset: tuple = ()
    affinity_per_battle: float = 0.0
    max_affinity: float = 100.0
    battle_unit: bool = False
    resources: dict = None
    battle_abilities: tuple = ()
    # creature-party options (PetRules): the experience curve, what defeating one of this
    # species is worth, how hard it is to capture (CaptureRule mode "rate"), and the battle
    # visual profiles (the back one is used when the pet fights on the player's side)
    exp_curve: object = None
    exp_yield: float = 0.0
    capture_rate: float = 0.0
    visual_profile_id: str = ""
    back_visual_profile_id: str = ""
    teachable: tuple = ()  # abilities an item tagged ``teaches:<ability>`` can teach it

    def __init__(
        self,
        species_id,
        display_name="",
        *,
        stats=None,
        growth=None,
        max_level=50,
        exp_base=40.0,
        exp_per_battle=30.0,
        icon_id="",
        tags=(),
        evolutions=(),
        learnset=(),
        affinity_per_battle=0.0,
        max_affinity=100.0,
        battle_unit=False,
        resources=None,
        battle_abilities=(),
        exp_curve=None,
        exp_yield=0.0,
        capture_rate=0.0,
        visual_profile_id="",
        back_visual_profile_id="",
        teachable=(),
    ):
        species_id = _text(species_id, "species_id")
        max_level, exp_base = int(max_level), float(exp_base)
        if max_level < 1:
            raise ValueError("max_level must be >= 1")
        if not isfinite(exp_base) or exp_base <= 0:
            raise ValueError("exp_base must be > 0")
        object.__setattr__(self, "species_id", species_id)
        object.__setattr__(self, "display_name", _text(display_name or species_id, "display_name"))
        object.__setattr__(self, "stats", _numbers(stats, "stat"))
        object.__setattr__(self, "growth", _numbers(growth, "growth"))
        object.__setattr__(self, "max_level", max_level)
        object.__setattr__(self, "exp_base", exp_base)
        exp_per_battle = float(exp_per_battle)
        if not isfinite(exp_per_battle) or exp_per_battle < 0:
            raise ValueError("exp_per_battle must be >= 0")
        object.__setattr__(self, "exp_per_battle", exp_per_battle)
        object.__setattr__(self, "icon_id", _text(icon_id, "icon_id", required=False))
        object.__setattr__(self, "tags", tuple(sorted({str(t).strip() for t in tags if str(t)})))
        evolutions = tuple(
            e if isinstance(e, PetEvolution) else PetEvolution.from_data(e) for e in evolutions
        )
        learnset = tuple(m if isinstance(m, PetMove) else PetMove.from_data(m) for m in learnset)
        object.__setattr__(self, "evolutions", evolutions)
        object.__setattr__(
            self, "learnset", tuple(sorted(learnset, key=lambda m: (m.level, m.ability_id)))
        )
        max_affinity = float(max_affinity)
        affinity_per_battle = float(affinity_per_battle)
        if not isfinite(max_affinity) or max_affinity < 0:
            raise ValueError("max_affinity must be >= 0")
        if not isfinite(affinity_per_battle):
            raise ValueError("affinity_per_battle must be finite")
        object.__setattr__(self, "max_affinity", max_affinity)
        object.__setattr__(self, "affinity_per_battle", affinity_per_battle)
        object.__setattr__(self, "battle_unit", bool(battle_unit))
        object.__setattr__(self, "resources", _numbers(resources, "resource"))
        object.__setattr__(
            self, "battle_abilities", tuple(dict.fromkeys(str(a) for a in battle_abilities if a))
        )
        if exp_curve is not None and not isinstance(exp_curve, PetExpCurve):
            exp_curve = PetExpCurve.from_data(exp_curve)
        object.__setattr__(self, "exp_curve", exp_curve)
        for name, value in (("exp_yield", exp_yield), ("capture_rate", capture_rate)):
            value = float(value)
            if not isfinite(value) or value < 0:
                raise ValueError(f"{name} must be >= 0")
            object.__setattr__(self, name, value)
        object.__setattr__(
            self, "teachable", tuple(dict.fromkeys(str(a).strip() for a in teachable if a))
        )
        object.__setattr__(
            self, "visual_profile_id", _text(visual_profile_id, "visual", required=False)
        )
        object.__setattr__(
            self,
            "back_visual_profile_id",
            _text(back_visual_profile_id, "back visual", required=False),
        )

    def resources_at(self, level, genes=None, formulas=None):
        """Resource maximums when the pet fights as a unit: ``resources[name]``, or the pet stat
        ``max_<name>`` (else a stat called ``<name>``) at ``level`` when the species defines
        one (so it can grow)."""
        stats = self.stats_at(level, genes, formulas)
        return {
            name: stats.get(f"max_{name}", stats.get(name, base))
            for name, base in self.resources.items()
        }

    def knows(self, ability_id, level, affinity=0.0):
        """Whether a pet of ``level`` and ``affinity`` has learned ``ability_id``."""
        return any(
            m.ability_id == ability_id and level >= m.level and affinity >= m.min_affinity
            for m in self.learnset
        )

    def known_abilities(self, level, affinity=0.0):
        return tuple(
            dict.fromkeys(
                m.ability_id
                for m in self.learnset
                if level >= m.level and affinity >= m.min_affinity
            )
        )

    def gated(self, ability_id):
        """True when ``ability_id`` is in this species' learnset (so it must be learned)."""
        return any(m.ability_id == ability_id for m in self.learnset)

    def stats_at(self, level, genes=None, formulas=None):
        """The stats at ``level``: the species' linear growth, or, with ``formulas``
        (``PetRules.stat_formulas``: stat name or ``"*"`` -> PetStatFormula), each stat
        through its formula with the pet's own ``genes``."""
        level = max(1, min(self.max_level, int(level)))
        names = set(self.stats) | set(self.growth)
        if not formulas:
            return {
                name: self.stats.get(name, 0.0) + self.growth.get(name, 0.0) * (level - 1)
                for name in sorted(names)
            }
        result = {}
        for name in sorted(names):
            formula = formulas.get(name, formulas.get("*"))
            if formula is None:
                result[name] = self.stats.get(name, 0.0) + self.growth.get(name, 0.0) * (level - 1)
            else:
                result[name] = formula.value(self.stats.get(name, 0.0), level, name, genes)
        return result

    def exp_to_next(self, level):
        if self.exp_curve is not None:
            return self.exp_curve.to_next(max(1, int(level)))
        return self.exp_base * max(1, int(level))

    def to_data(self):
        return {
            "schema": "asteria.rpg.pet_species",
            "version": 1,
            "species_id": self.species_id,
            "display_name": self.display_name,
            "stats": dict(sorted(self.stats.items())),
            "growth": dict(sorted(self.growth.items())),
            "max_level": self.max_level,
            "exp_base": self.exp_base,
            "exp_per_battle": self.exp_per_battle,
            **({"icon_id": self.icon_id} if self.icon_id else {}),
            **({"tags": list(self.tags)} if self.tags else {}),
            **({"evolutions": [e.to_data() for e in self.evolutions]} if self.evolutions else {}),
            **({"learnset": [m.to_data() for m in self.learnset]} if self.learnset else {}),
            **(
                {"affinity_per_battle": self.affinity_per_battle}
                if self.affinity_per_battle
                else {}
            ),
            **({"max_affinity": self.max_affinity} if self.max_affinity != 100.0 else {}),
            **({"battle_unit": True} if self.battle_unit else {}),
            **({"resources": dict(sorted(self.resources.items()))} if self.resources else {}),
            **({"battle_abilities": list(self.battle_abilities)} if self.battle_abilities else {}),
            **({"exp_curve": self.exp_curve.to_data()} if self.exp_curve is not None else {}),
            **({"exp_yield": self.exp_yield} if self.exp_yield else {}),
            **({"capture_rate": self.capture_rate} if self.capture_rate else {}),
            **({"visual_profile_id": self.visual_profile_id} if self.visual_profile_id else {}),
            **(
                {"back_visual_profile_id": self.back_visual_profile_id}
                if self.back_visual_profile_id
                else {}
            ),
            **({"teachable": list(self.teachable)} if self.teachable else {}),
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != "asteria.rpg.pet_species" or data.get("version") != 1:
            raise ValueError("unsupported pet species")
        return cls(
            data["species_id"],
            data.get("display_name", ""),
            stats=data.get("stats"),
            growth=data.get("growth"),
            max_level=data.get("max_level", 50),
            exp_base=data.get("exp_base", 40.0),
            exp_per_battle=data.get("exp_per_battle", 30.0),
            icon_id=data.get("icon_id", ""),
            tags=data.get("tags", ()),
            evolutions=data.get("evolutions", ()),
            learnset=data.get("learnset", ()),
            affinity_per_battle=data.get("affinity_per_battle", 0.0),
            max_affinity=data.get("max_affinity", 100.0),
            battle_unit=data.get("battle_unit", False),
            resources=data.get("resources"),
            battle_abilities=data.get("battle_abilities", ()),
            exp_curve=data.get("exp_curve"),
            exp_yield=data.get("exp_yield", 0.0),
            capture_rate=data.get("capture_rate", 0.0),
            visual_profile_id=data.get("visual_profile_id", ""),
            back_visual_profile_id=data.get("back_visual_profile_id", ""),
            teachable=data.get("teachable", ()),
        )


@dataclass(slots=True)
class PetRecord:
    """One owned creature (save data).

    Under :class:`PetRules` it also keeps what a battle unit carries between fights:
    ``resources`` (current values, e.g. hit points; empty = full), ``states`` (ids of the
    states still on it: a poison that lasts), ``moves`` (the abilities it knows now; empty =
    whatever its species taught it by its level), ``pp`` (uses left of each move with
    ``AbilityDefinition.max_uses``; absent = full), ``held_item_id`` and ``genes`` (its own
    numbers for the stat formulas: ``iv.attack``, ``nature.speed``...)."""

    instance_id: str
    species_id: str
    nickname: str = ""
    level: int = 1
    experience: float = 0.0
    affinity: float = 0.0
    resources: dict = None
    states: list = None
    moves: list = None
    pp: dict = None
    held_item_id: str = ""
    genes: dict = None

    def __post_init__(self):
        self.instance_id = _text(self.instance_id, "instance_id")
        self.species_id = _text(self.species_id, "species_id")
        self.nickname = str(self.nickname or "").strip()[:24]
        self.level = max(1, int(self.level))
        self.experience = max(0.0, float(self.experience))
        self.affinity = max(0.0, float(self.affinity))
        self.resources = _numbers(self.resources, "resource")
        self.states = [str(x) for x in (self.states or ()) if str(x)]
        self.moves = list(dict.fromkeys(str(x) for x in (self.moves or ()) if str(x)))
        self.pp = {k: max(0, int(v)) for k, v in dict(self.pp or {}).items() if str(k)}
        self.held_item_id = str(self.held_item_id or "").strip()
        self.genes = _numbers(self.genes, "gene")

    def known_moves(self, species, max_moves=0):
        """The abilities the pet can use: its own ``moves`` when set, else what its species
        taught it by now (``battle_abilities`` plus the learnset) - the last ``max_moves``
        learned when that limit is set (0 = all)."""
        if self.moves:
            return tuple(self.moves)
        if species is None:
            return ()
        learned = (*species.battle_abilities, *species.known_abilities(self.level, self.affinity))
        learned = tuple(dict.fromkeys(learned))
        return learned[-max_moves:] if max_moves and len(learned) > max_moves else learned

    def add_affinity(self, species, amount):
        """Change affinity (clamped to ``0..max_affinity``); returns the applied change."""
        before = self.affinity
        self.affinity = max(0.0, min(species.max_affinity, before + float(amount)))
        return self.affinity - before

    def evolution_for(self, species, *, item_id=""):
        """The first evolution whose conditions hold (``item_id`` is the item being used)."""
        for evolution in species.evolutions:
            if evolution.item_id and evolution.item_id != item_id:
                continue
            if self.level >= evolution.min_level and self.affinity >= evolution.min_affinity:
                return evolution
        return None

    def evolve(self, evolution):
        """Become ``evolution.to_species_id`` (nickname, level, affinity and experience stay)."""
        self.species_id = evolution.to_species_id

    def name(self, species=None):
        """What the pet is called: its nickname, else its species' name."""
        if self.nickname:
            return self.nickname
        return species.display_name if species is not None else self.species_id

    def gain(self, species, amount):
        """Add experience; returns how many levels it gained."""
        gained = 0
        self.experience += max(0.0, float(amount))
        while self.level < species.max_level and self.experience >= species.exp_to_next(
            self.level
        ):
            self.experience -= species.exp_to_next(self.level)
            self.level += 1
            gained += 1
        if self.level >= species.max_level:
            self.experience = 0.0
        return gained

    def to_data(self):
        return {
            "instance_id": self.instance_id,
            "species_id": self.species_id,
            "nickname": self.nickname,
            "level": self.level,
            "experience": self.experience,
            **({"affinity": self.affinity} if self.affinity else {}),
            **({"resources": dict(sorted(self.resources.items()))} if self.resources else {}),
            **({"states": list(self.states)} if self.states else {}),
            **({"moves": list(self.moves)} if self.moves else {}),
            **({"pp": dict(sorted(self.pp.items()))} if self.pp else {}),
            **({"held_item_id": self.held_item_id} if self.held_item_id else {}),
            **({"genes": dict(sorted(self.genes.items()))} if self.genes else {}),
        }

    @classmethod
    def from_data(cls, data):
        return cls(
            data["instance_id"],
            data["species_id"],
            data.get("nickname", ""),
            data.get("level", 1),
            data.get("experience", 0.0),
            data.get("affinity", 0.0),
            data.get("resources"),
            data.get("states"),
            data.get("moves"),
            data.get("pp"),
            data.get("held_item_id", ""),
            data.get("genes"),
        )


EXP_SHARES = ("none", "split", "each", "party")
LEVEL_UP_HEALS = ("none", "delta", "full")


@dataclass(frozen=True, slots=True)
class PetRules:
    """Project-wide creature-party rules (Game Systems > Pet Rules); without a record every
    pet behaves as before (one active pet, sent out by abilities or fighting as one unit).

    - ``party_size``: how many pets travel with the player (0 = every owned pet); the rest
      wait in **storage** (a PC) when ``storage`` is on, else cannot be caught or must be
      let go - the game's own choice through its events.
    - ``battle_slots``: pets of a side on the stage at once (0 = all of them); the others sit
      on the bench and come in when one falls or is switched (``switch_costs_turn``).
    - ``actors_fight``: off = the roster's characters stay out of battle (a trainer who
      watches); ``pets_decide_outcome``: on = a side with no standing pet has lost.
    - ``exp_share``: what beaten foes give the pets - ``none`` (each species' own
      ``exp_per_battle``), ``split`` (the foe's experience divided among the pets that
      fought it), ``each`` (every pet that fought gets all of it), ``party`` (every party pet
      gets all of it); a foe is worth its species' ``exp_yield x level`` (a species foe) or
      the sum of its reward experience, over ``exp_divisor``; ``exp_whole`` rounds each pet's
      share down to whole points.
    - ``level_up_heal``: on a level up current resources rise by the growth (``delta``),
      to the new maximum (``full``) or stay (``none``).
    - ``max_moves``: moves a pet can know at once (0 = unlimited); learning past it asks
      which to forget. ``heal_restores_pp``: the HEAL_PETS command refills move uses.
    - ``out_of_uses_ability``: what a creature uses when none of its moves has a use left
      (a project ability, e.g. one that also hurts its user); empty = it cannot attack.
    - ``stat_formulas``: stat name (or ``"*"`` for the rest) -> PetStatFormula; when set the
      species' linear growth is replaced for those stats.
    - ``gene_ranges``: gene prefix -> ``[low, high]``: every new creature (caught, given,
      a wild one) rolls a whole number in the range for each species stat
      (``<prefix>.<stat>``); ``gene_sets``: prefix -> a list of ``{stat: number}`` sets, one
      picked at random per creature (a "nature": which stats it favours).
    """

    rules_id: str
    party_size: int = 0
    battle_slots: int = 1
    storage: bool = False
    actors_fight: bool = True
    pets_decide_outcome: bool = False
    switch_costs_turn: bool = True
    exp_share: str = "none"
    exp_divisor: float = 1.0
    exp_whole: bool = False  # each pet's share rounded down to whole points (Gen III)
    level_up_heal: str = "delta"
    max_moves: int = 0
    heal_restores_pp: bool = True
    stat_formulas: dict = None
    out_of_uses_ability: str = ""
    gene_ranges: dict = None
    gene_sets: dict = None

    def __init__(
        self,
        rules_id,
        *,
        party_size=0,
        battle_slots=1,
        storage=False,
        actors_fight=True,
        pets_decide_outcome=False,
        switch_costs_turn=True,
        exp_share="none",
        exp_divisor=1.0,
        exp_whole=False,
        level_up_heal="delta",
        max_moves=0,
        heal_restores_pp=True,
        stat_formulas=None,
        gene_ranges=None,
        gene_sets=None,
        out_of_uses_ability="",
    ):
        s = object.__setattr__
        s(self, "out_of_uses_ability", _text(out_of_uses_ability, "ability", required=False))
        s(self, "rules_id", _text(rules_id, "rules_id"))
        for name, value in (
            ("party_size", party_size),
            ("battle_slots", battle_slots),
            ("max_moves", max_moves),
        ):
            value = int(value)
            if value < 0:
                raise ValueError(f"{name} must be >= 0")
            s(self, name, value)
        for name, value in (
            ("storage", storage),
            ("actors_fight", actors_fight),
            ("pets_decide_outcome", pets_decide_outcome),
            ("switch_costs_turn", switch_costs_turn),
            ("heal_restores_pp", heal_restores_pp),
            ("exp_whole", exp_whole),
        ):
            s(self, name, bool(value))
        if str(exp_share) not in EXP_SHARES:
            raise ValueError(f"exp_share must be one of {EXP_SHARES}")
        s(self, "exp_share", str(exp_share))
        exp_divisor = float(exp_divisor)
        if not isfinite(exp_divisor) or exp_divisor <= 0:
            raise ValueError("exp_divisor must be > 0")
        s(self, "exp_divisor", exp_divisor)
        if str(level_up_heal) not in LEVEL_UP_HEALS:
            raise ValueError(f"level_up_heal must be one of {LEVEL_UP_HEALS}")
        s(self, "level_up_heal", str(level_up_heal))
        formulas = {}
        for name, value in dict(stat_formulas or {}).items():
            if not isinstance(value, PetStatFormula):
                value = PetStatFormula.from_data(value)
            formulas[_text(name, "stat formula name")] = value
        s(self, "stat_formulas", formulas)
        ranges = {}
        for name, value in dict(gene_ranges or {}).items():
            low, high = (int(x) for x in tuple(value)[:2])
            if high < low:
                raise ValueError(f"gene range {name} is reversed")
            ranges[_text(name, "gene range name")] = (low, high)
        s(self, "gene_ranges", ranges)
        sets = {}
        for name, values in dict(gene_sets or {}).items():
            sets[_text(name, "gene set name")] = tuple(
                _numbers(v, f"gene set {name}") for v in tuple(values)
            )
        s(self, "gene_sets", sets)

    def roll_genes(self, stat_names, rng):
        """A new creature's genes: one roll per stat for each ``gene_ranges`` prefix and one
        of each ``gene_sets`` prefix's sets (``rng``: ``random.Random``)."""
        genes = {}
        for prefix, (low, high) in sorted(self.gene_ranges.items()):
            for stat in sorted(stat_names):
                genes[f"{prefix}.{stat}"] = float(rng.randint(low, high))
        for prefix, choices in sorted(self.gene_sets.items()):
            if choices:
                for stat, value in rng.choice(choices).items():
                    genes[f"{prefix}.{stat}"] = value
        return genes

    def to_data(self):
        return {
            "schema": "asteria.rpg.pet_rules",
            "version": 1,
            "rules_id": self.rules_id,
            **({"party_size": self.party_size} if self.party_size else {}),
            **({"battle_slots": self.battle_slots} if self.battle_slots != 1 else {}),
            **({"storage": True} if self.storage else {}),
            **({"actors_fight": False} if not self.actors_fight else {}),
            **({"pets_decide_outcome": True} if self.pets_decide_outcome else {}),
            **({"switch_costs_turn": False} if not self.switch_costs_turn else {}),
            **({"exp_share": self.exp_share} if self.exp_share != "none" else {}),
            **({"exp_divisor": self.exp_divisor} if self.exp_divisor != 1.0 else {}),
            **({"exp_whole": True} if self.exp_whole else {}),
            **({"level_up_heal": self.level_up_heal} if self.level_up_heal != "delta" else {}),
            **({"max_moves": self.max_moves} if self.max_moves else {}),
            **({"heal_restores_pp": False} if not self.heal_restores_pp else {}),
            **(
                {"out_of_uses_ability": self.out_of_uses_ability}
                if self.out_of_uses_ability
                else {}
            ),
            **(
                {"stat_formulas": {k: v.to_data() for k, v in sorted(self.stat_formulas.items())}}
                if self.stat_formulas
                else {}
            ),
            **(
                {"gene_ranges": {k: list(v) for k, v in sorted(self.gene_ranges.items())}}
                if self.gene_ranges
                else {}
            ),
            **(
                {"gene_sets": {k: [dict(x) for x in v] for k, v in sorted(self.gene_sets.items())}}
                if self.gene_sets
                else {}
            ),
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != "asteria.rpg.pet_rules" or data.get("version") != 1:
            raise ValueError("unsupported pet rules")
        return cls(
            data["rules_id"],
            party_size=data.get("party_size", 0),
            battle_slots=data.get("battle_slots", 1),
            storage=data.get("storage", False),
            actors_fight=data.get("actors_fight", True),
            pets_decide_outcome=data.get("pets_decide_outcome", False),
            switch_costs_turn=data.get("switch_costs_turn", True),
            exp_share=data.get("exp_share", "none"),
            exp_divisor=data.get("exp_divisor", 1.0),
            exp_whole=data.get("exp_whole", False),
            level_up_heal=data.get("level_up_heal", "delta"),
            max_moves=data.get("max_moves", 0),
            heal_restores_pp=data.get("heal_restores_pp", True),
            stat_formulas=data.get("stat_formulas"),
            gene_ranges=data.get("gene_ranges"),
            gene_sets=data.get("gene_sets"),
            out_of_uses_ability=data.get("out_of_uses_ability", ""),
        )


PET_STAT_PREFIX = "pet_"
