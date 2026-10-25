"""Pets: the roster, stats, evolution, affinity and experience; under ``PetRules`` also the
creature party (party, storage, bench and switching, species foes, moves and their uses)."""

from __future__ import annotations

import random

from asteria.rpg.built_in_text import Words

from .support import (  # noqa: F401 - the names the moved methods use
    BattleLogEntry,
    EquipOffer,
    GameSessionError,
    _base_relative,
    _EitherBlocks,
    _merge_casts,
    describe_condition,
)

PET_MEMBER_PREFIX = "pet:"


def taught_ability(item):
    """The ability an item tagged ``teaches:<ability>`` teaches (a TM), else ""."""
    for tag in getattr(item, "tags", ()) or ():
        if str(tag).startswith("teaches:"):
            return str(tag)[len("teaches:") :].strip()
    return ""


class SpeciesFoe:
    """What a foe generated from a pet species looks like where an enemy definition is read
    (names, tags, rewards): the species' name and tags, no abilities of its own (the unit
    carries its moves), no item rewards (its experience is the species' ``exp_yield``)."""

    __slots__ = ("abilities", "display_name", "reward", "species", "tags")

    def __init__(self, species):
        from asteria.rpg.enemies import RewardDefinition

        self.species = species
        self.display_name = species.display_name
        self.tags = tuple(species.tags)
        self.abilities = ()
        self.reward = RewardDefinition()


class PetsMixin:
    # -- pets ---------------------------------------------------------------------------------
    def pets(self):
        """The owned pets (``rpg.pets.PetRecord``)."""
        return tuple(self.save.rpg_state.pets)

    def pet_species(self, pet):
        return self.project.rpg_database.pet_species.get(pet.species_id)

    @property
    def pet_rules(self):
        """The project's creature-party rules (Game Systems > Pet Rules): the first by id, or
        ``None`` - then pets behave as they always did."""
        values = self.project.rpg_database.pet_rules
        return values[sorted(values)[0]] if values else None

    def _pet_formulas(self):
        rules = self.pet_rules
        return rules.stat_formulas if rules is not None and rules.stat_formulas else None

    def pet_stats_at(self, pet, level=None):
        """A pet's stats at its level (or ``level``), through the rules' formulas and its genes."""
        species = self.pet_species(pet)
        if species is None:
            return {}
        level = pet.level if level is None else level
        return species.stats_at(level, pet.genes, self._pet_formulas())

    def pet_resources_at(self, pet, level=None):
        species = self.pet_species(pet)
        if species is None:
            return {}
        level = pet.level if level is None else level
        return species.resources_at(level, pet.genes, self._pet_formulas())

    def active_pet(self):
        """The pet that abilities send out: the chosen one, else the first owned."""
        state = self.save.rpg_state
        for pet in state.pets:
            if pet.instance_id == state.active_pet_id:
                return pet
        return state.pets[0] if state.pets else None

    # -- the party and storage ----------------------------------------------------------------
    def party_pets(self):
        """The pets travelling with the player, in order. Without rules: every owned pet."""
        state = self.save.rpg_state
        rules = self.pet_rules
        if rules is None:
            return tuple(state.pets)
        by_id = {p.instance_id: p for p in state.pets}
        if not state.party_pet_ids and state.pets:  # a save from before the party existed
            limit = rules.party_size or len(state.pets)
            state.party_pet_ids = tuple(p.instance_id for p in state.pets[:limit])
        return tuple(by_id[i] for i in state.party_pet_ids if i in by_id)

    def stored_pets(self):
        """The owned pets not in the party (the storage box); empty without rules."""
        if self.pet_rules is None:
            return ()
        party = {p.instance_id for p in self.party_pets()}
        return tuple(p for p in self.save.rpg_state.pets if p.instance_id not in party)

    def party_full(self):
        rules = self.pet_rules
        return bool(rules and rules.party_size and len(self.party_pets()) >= rules.party_size)

    def move_pet_to_party(self, instance_id):
        pet = self._pet(instance_id)
        state = self.save.rpg_state
        if pet.instance_id in state.party_pet_ids:
            return pet
        if self.party_full():
            raise GameSessionError(Words("pets.party_full", "The party is full"))
        self.party_pets()  # settles the ids of an old save first
        state.party_pet_ids = (*state.party_pet_ids, pet.instance_id)
        return pet

    def move_pet_to_storage(self, instance_id):
        pet = self._pet(instance_id)
        rules = self.pet_rules
        if rules is None or not rules.storage:
            raise GameSessionError(Words("pets.no_storage", "There is nowhere to keep it"))
        state = self.save.rpg_state
        party = self.party_pets()
        if pet.instance_id not in state.party_pet_ids:
            return pet
        others = [p for p in party if p.instance_id != pet.instance_id and self.pet_standing(p)]
        if not others:
            raise GameSessionError(Words("pets.last_one", "The last one must stay with you"))
        state.party_pet_ids = tuple(i for i in state.party_pet_ids if i != pet.instance_id)
        if state.active_pet_id == pet.instance_id:
            state.active_pet_id = others[0].instance_id
        return pet

    def reorder_party_pets(self, instance_ids):
        state = self.save.rpg_state
        current = tuple(p.instance_id for p in self.party_pets())
        wanted = tuple(dict.fromkeys(str(x) for x in instance_ids))
        if sorted(wanted) != sorted(current):
            raise GameSessionError("the new order must list every party pet once")
        state.party_pet_ids = wanted
        return wanted

    def pet_standing(self, pet):
        """Whether the pet can fight: its knockout resource (when it keeps one) is above 0."""
        resource = self.rules.knockout_resource_id
        if not resource or resource not in pet.resources:
            return True
        return pet.resources[resource] > 0

    def battle_pets(self):
        """The pets that fight as units in the next battle: the party's (rules), else the
        active pet when its species is a ``battle_unit``."""
        rules = self.pet_rules
        if rules is None:
            pet = self.active_pet()
            species = self.pet_species(pet) if pet is not None else None
            return (pet,) if species is not None and species.battle_unit else ()
        return tuple(
            p
            for p in self.party_pets()
            if (s := self.pet_species(p)) is not None and s.battle_unit
        )

    def add_pet(self, species_id, *, level=1, nickname="", record=None, rng=None):
        """Own a new creature of ``species_id`` (or adopt ``record``, a caught foe's state):
        it joins the party while there is room, else storage (rules), and rolls its genes and
        takes its moves as the rules say."""
        from asteria.rpg.pets import PetRecord

        db = self.project.rpg_database
        species_id = record.species_id if record is not None else str(species_id)
        species = db.pet_species.get(species_id)
        if species is None:
            raise GameSessionError(f"unknown pet species {species_id}")
        state = self.save.rpg_state
        rules = self.pet_rules
        room = True
        if rules is not None:
            self.party_pets()  # settles the party ids of an old save before the newcomer
            room = not self.party_full()
        taken = {p.instance_id for p in state.pets}
        serial = 1
        while f"{species_id}#{serial}" in taken:
            serial += 1
        instance_id = f"{species_id}#{serial}"
        if record is not None:
            pet = PetRecord(
                instance_id,
                species_id,
                nickname or record.nickname,
                record.level,
                record.experience,
                record.affinity,
                dict(record.resources),
                list(record.states),
                list(record.moves),
                dict(record.pp),
                record.held_item_id,
                dict(record.genes),
            )
        else:
            pet = PetRecord(instance_id, species_id, nickname, level)
        if rules is not None:
            if not pet.genes:
                rng = rng or random.Random(f"{self.encounter_id}:{instance_id}:genes")
                pet.genes = rules.roll_genes(species.stats, rng)
            if rules.max_moves and not pet.moves:
                pet.moves = list(pet.known_moves(species, rules.max_moves))
        state.pets.append(pet)
        if not state.active_pet_id:
            state.active_pet_id = pet.instance_id
        if rules is not None and room:
            state.party_pet_ids = (*state.party_pet_ids, pet.instance_id)
        return pet

    def _pet(self, instance_id):
        for pet in self.save.rpg_state.pets:
            if pet.instance_id == str(instance_id):
                return pet
        raise GameSessionError(f"unknown pet {instance_id}")

    def rename_pet(self, instance_id, nickname):
        pet = self._pet(instance_id)
        pet.nickname = str(nickname or "").strip()[:24]
        return pet

    def set_active_pet(self, instance_id):
        pet = self._pet(instance_id)
        self.save.rpg_state.active_pet_id = pet.instance_id
        return pet

    def use_item_on_pet(self, pet, item_id):
        """Use an item on a creature outside battle: its use effects (health...) and the
        states it cures (``cures:<state>`` tags). A fallen creature takes only an item tagged
        ``revives``. Consumed only when it changed something; returns whether it did."""
        from asteria.gameplay.effects import apply_effect

        from .ability_use import cure_states, self_context

        item = self.project.rpg_database.items.get(str(item_id))
        species = self.pet_species(pet)
        if item is None or species is None:
            return False
        if self.save.rpg_state.inventory.count(item.item_id) < 1:
            return False
        if taught_ability(item):
            return self._teach_with_item(pet, item)
        knockout = self.rules.knockout_resource_id
        tops = self.pet_resources_at(pet)
        if knockout in tops and pet.resources.get(knockout, tops[knockout]) <= 0:
            if "revives" not in item.tags:
                return False
        subject = self._creature_subject(pet, species)
        before = {name: subject.resources.current(name) for name in tops}
        for effect in item.use_effects:
            apply_effect(effect, subject.stats, subject.resources, subject.tags,
                         formula_context=self_context(subject))  # fmt: skip
        cured = cure_states(subject, item)
        after = {name: subject.resources.current(name) for name in tops}
        if after == before and not cured:
            return False
        for name, value in after.items():
            pet.resources[name] = value
        if cured:
            pet.states = [state for state in pet.states if state not in cured]
        self.save.rpg_state.inventory.remove(item.item_id, 1)
        return True

    def teaching_check(self, pet, item_id):
        """What an item tagged ``teaches:<ability>`` would do to ``pet``: ``able``,
        ``learned`` (it knows it), ``not_able`` (not in its species' ``teachable``), or ""
        for an item that teaches nothing."""
        item = self.project.rpg_database.items.get(str(item_id))
        ability = taught_ability(item) if item is not None else ""
        if not ability:
            return ""
        species = self.pet_species(pet)
        if species is None or ability not in species.teachable:
            return "not_able"
        return "learned" if ability in self.pet_moves(pet) else "able"

    def _teach_with_item(self, pet, item):
        """A teaching item on a creature able to learn it: learned (the item is used up
        unless tagged ``reusable``), or, with the moves full, the game asks which move to
        forget (``pending_pet_moves``) and the item goes once that is answered."""
        if self.teaching_check(pet, item.item_id) != "able":
            return False
        ability = taught_ability(item)
        self._teaching = dict(getattr(self, "_teaching", {}))
        self._teaching[(pet.instance_id, ability)] = item.item_id
        if self.learn_pet_move(pet.instance_id, ability):
            return True
        self._teaching[(pet.instance_id, ability)] = item.item_id  # until the answer
        pending = list(getattr(self, "_pending_pet_moves", []))
        pending.append((pet.instance_id, ability))
        self._pending_pet_moves = pending
        return True

    def stash_pets(self):
        """Put the player's creatures aside (PARTY_STASH): someone else's battle follows (a
        tutorial); ``restore_pets`` brings them back and drops whatever came in between."""
        state = self.save.rpg_state
        self._pet_stash = (list(state.pets), tuple(state.party_pet_ids))
        state.pets = []
        state.party_pet_ids = ()
        return len(self._pet_stash[0])

    def restore_pets(self):
        """PARTY_RESTORE: the creatures put aside come back as they were."""
        stash = getattr(self, "_pet_stash", None)
        if stash is None:
            return 0
        state = self.save.rpg_state
        state.pets, state.party_pet_ids = list(stash[0]), tuple(stash[1])
        self._pet_stash = None
        return len(state.pets)

    def heal_pets(self, *, party_only=False):
        """A rest for the creatures: every owned (or party) pet back to full resources, no
        lasting states, every move's uses restored (rules ``heal_restores_pp``)."""
        rules = self.pet_rules
        pets = self.party_pets() if party_only else self.pets()
        for pet in pets:
            pet.resources = {}
            pet.states = []
            if rules is None or rules.heal_restores_pp:
                pet.pp = {}
        return tuple(p.instance_id for p in pets)

    def pet_stats(self, pet=None):
        """``{"pet_<stat>": value, "pet_level": n}`` of a pet (default: the active one)."""
        pet = pet or self.active_pet()
        species = self.pet_species(pet) if pet is not None else None
        if species is None:
            return {}
        values = {f"pet_{k}": v for k, v in self.pet_stats_at(pet).items()}
        values["pet_level"] = float(pet.level)
        return values

    def _pet_move_missing(self, ability_id):
        """An ability listed in the active pet's learnset needs the pet to have learned it."""
        pet = self.active_pet()
        species = self.pet_species(pet) if pet is not None else None
        if species is None or not species.gated(ability_id):
            return ""
        if species.knows(ability_id, pet.level, pet.affinity):
            return ""
        return self.tr(
            "battle.reason.pet_unlearned", "{pet} has not learned this", pet=self.pet_display(pet)
        )

    def pet_display(self, pet):
        """What ``pet`` is called on screen: its nickname, else its species' name in the
        player's language (D60)."""
        if pet.nickname:
            return pet.nickname
        return self.name_of(self.pet_species(pet), pet.species_id)

    def pet_name(self, instance_id):
        """A pet's nickname (else its species' name) by instance id; ``""`` when unknown."""
        pet = next(
            (p for p in self.save.rpg_state.pets if p.instance_id == str(instance_id)), None
        )
        return "" if pet is None else self.pet_display(pet)

    def pet_abilities(self, pet=None):
        """Ability ids the pet (default: the active one) has learned from its species."""
        pet = pet or self.active_pet()
        species = self.pet_species(pet) if pet is not None else None
        if species is None:
            return ()
        return species.known_abilities(pet.level, pet.affinity)

    # -- moves and their uses -----------------------------------------------------------------
    def pet_moves(self, pet):
        """The moves a pet can use now (``PetRecord.known_moves`` under the rules' limit)."""
        rules = self.pet_rules
        return pet.known_moves(self.pet_species(pet), rules.max_moves if rules else 0)

    def pet_uses_left(self, pet, ability_id):
        """Uses left of a move with ``max_uses`` (``None`` when the move is unlimited)."""
        definition = self.project.gameplay_library.abilities.get(ability_id)
        top = int(getattr(definition, "max_uses", 0) or 0) if definition is not None else 0
        if not top:
            return None
        return min(top, pet.pp.get(str(ability_id), top))

    def spend_pet_use(self, pet, ability_id):
        left = self.pet_uses_left(pet, ability_id)
        if left is None:
            return None
        pet.pp[str(ability_id)] = max(0, left - 1)
        return pet.pp[str(ability_id)]

    def restore_pet_uses(self, pet, ability_id="", amount=None):
        """Refill a move's uses (every move when ``ability_id`` is empty) by ``amount`` (all)."""
        moves = (ability_id,) if ability_id else self.pet_moves(pet)
        for move in moves:
            left = self.pet_uses_left(pet, move)
            if left is None:
                continue
            if amount is None:
                pet.pp.pop(move, None)
            else:
                definition = self.project.gameplay_library.abilities.get(move)
                pet.pp[move] = min(int(definition.max_uses), left + int(amount))
        return pet

    def out_of_uses_move(self, member_id):
        """The ability a creature unit uses because none of its moves has a use left
        (``PetRules.out_of_uses_ability``), or ``""`` while it still has one to use."""
        rules = self.pet_rules
        record = self.unit_record(member_id)
        if rules is None or not rules.out_of_uses_ability or record is None:
            return ""
        moves = self.battle.member(member_id).ability_ids if self.battle else ()
        if any(self.pet_uses_left(record, move) != 0 for move in moves):
            return ""
        return rules.out_of_uses_ability

    def use_out_of_uses_move(self, member_id, target_ids=None):
        """Use the out-of-uses ability (it is no move of the creature's own: granted for
        this one action, the way a battle item's ability is)."""
        ability_id = self.out_of_uses_move(member_id)
        if not ability_id:
            raise GameSessionError(f"{member_id} still has moves to use")
        battle = self.battle
        battle.granted_abilities = {(str(member_id), ability_id)}
        try:
            return self.use_ability(member_id, ability_id, target_ids)
        finally:
            battle.granted_abilities = set()

    def pending_pet_moves(self):
        """``[(instance_id, ability_id), ...]``: moves learned while the pet already knows
        the rules' ``max_moves`` - the game asks which to forget (``learn_pet_move``)."""
        return tuple(getattr(self, "_pending_pet_moves", ()))

    def learn_pet_move(self, instance_id, ability_id, forget_ability_id=""):
        """Teach a pet a move; with the moves full, ``forget_ability_id`` makes room (empty =
        the pet does not learn it). Returns True when learned."""
        pet = self._pet(instance_id)
        ability_id = str(ability_id)
        pending = [
            x
            for x in getattr(self, "_pending_pet_moves", [])
            if x != (pet.instance_id, ability_id)
        ]
        self._pending_pet_moves = pending
        teaching = getattr(self, "_teaching", {})
        item_id = teaching.pop((pet.instance_id, ability_id), "")
        if ability_id in pet.moves:
            return True
        learned = self._learn_pet_move(pet, ability_id, forget_ability_id)
        item = self.project.rpg_database.items.get(item_id) if item_id else None
        if learned and item is not None and "reusable" not in item.tags:
            self.save.rpg_state.inventory.remove(item_id, 1)  # a taught move uses the item up
        return learned

    def _learn_pet_move(self, pet, ability_id, forget_ability_id):
        rules = self.pet_rules
        species = self.pet_species(pet)
        moves = list(pet.moves or pet.known_moves(species, rules.max_moves if rules else 0))
        if rules is not None and rules.max_moves and len(moves) >= rules.max_moves:
            if not forget_ability_id or forget_ability_id not in moves:
                return False
            moves[moves.index(forget_ability_id)] = ability_id
            pet.pp.pop(forget_ability_id, None)
        else:
            moves.append(ability_id)
        pet.moves = moves
        pet.pp.pop(ability_id, None)
        self._log(
            "pet_learned",
            member_id=pet.instance_id,
            data={"ability_id": ability_id, "forgot": forget_ability_id},
        )
        return True

    def _teach_new_moves(self, pet, species, old_level):
        """Moves the species teaches between ``old_level`` and the pet's level now."""
        rules = self.pet_rules
        if rules is None:
            return
        for move in species.learnset:
            if not (old_level < move.level <= pet.level) or pet.affinity < move.min_affinity:
                continue
            if move.ability_id in self.pet_moves(pet):
                continue
            if not self.learn_pet_move(pet.instance_id, move.ability_id):
                self._pending_pet_moves = [
                    *getattr(self, "_pending_pet_moves", []),
                    (pet.instance_id, move.ability_id),
                ]

    # -- evolution and affinity ---------------------------------------------------------------
    def pet_evolution(self, instance_id, *, item_id=""):
        """The evolution a pet currently qualifies for, or ``None``."""
        pet = self._pet(instance_id)
        species = self.pet_species(pet)
        return None if species is None else pet.evolution_for(species, item_id=item_id)

    def evolve_pet(self, instance_id, *, item_id=""):
        """Evolve a pet now (spending ``item_id`` when the evolution consumes it).

        Returns the new species id, or raises when the pet does not qualify.
        """
        pet = self._pet(instance_id)
        evolution = self.pet_evolution(instance_id, item_id=item_id)
        if evolution is None:
            raise GameSessionError(f"pet {instance_id} cannot evolve")
        target = self.project.rpg_database.pet_species.get(evolution.to_species_id)
        if target is None:
            raise GameSessionError(f"unknown pet species {evolution.to_species_id}")
        if evolution.item_id and evolution.consume_item:
            inventory = self.save.rpg_state.inventory
            if inventory.count(evolution.item_id) < 1:
                raise GameSessionError(f"needs item {evolution.item_id}")
            inventory.remove(evolution.item_id, 1)
        before = pet.species_id
        maxima_before = self.pet_resources_at(pet)
        pet.evolve(evolution)
        self._grow_pet_resources(pet, maxima_before)
        self._log(
            "pet_evolved",
            member_id=pet.instance_id,
            data={"from": before, "to": pet.species_id, "level": pet.level},
        )
        return pet.species_id

    def change_pet_affinity(self, instance_id, amount):
        pet = self._pet(instance_id)
        species = self.pet_species(pet)
        return pet.add_affinity(species, amount) if species is not None else 0.0

    # -- battle units -------------------------------------------------------------------------
    def pet_member_id(self, pet):
        return PET_MEMBER_PREFIX + pet.instance_id

    def pet_of_member(self, member_id):
        """The owned pet a hero-side unit stands for, or ``None``."""
        member_id = str(member_id)
        if not member_id.startswith(PET_MEMBER_PREFIX):
            return None
        instance_id = member_id[len(PET_MEMBER_PREFIX) :]
        return next((p for p in self.save.rpg_state.pets if p.instance_id == instance_id), None)

    def foe_record(self, member_id):
        """The creature record of a species foe (``EncounterMember.pet_species_id``), or
        ``None`` for an enemy definition's unit."""
        return getattr(self, "_species_foes", {}).get(str(member_id))

    def foe_definition(self, kind_id):
        """What a foe kind is: the enemy definition, or a :class:`SpeciesFoe` view of a pet
        species; ``None`` when unknown."""
        db = self.project.rpg_database
        definition = db.enemies.get(str(kind_id))
        if definition is not None:
            return definition
        species = db.pet_species.get(str(kind_id))
        return None if species is None else SpeciesFoe(species)

    def unit_record(self, member_id):
        """The pet record behind any creature unit (an owned pet or a species foe)."""
        return self.pet_of_member(member_id) or self.foe_record(member_id)

    def _creature_subject(self, record, species):
        from asteria.gameplay import ResourcePool, StatBlock, TagSet

        values = dict(self.pet_stats_at(record))
        values.setdefault("level", float(record.level))  # formulas may read it (damage...)
        stats = StatBlock(values)
        resources = ResourcePool()
        for name, maximum in self.pet_resources_at(record).items():
            resources.define(name, maximum)
            if name in record.resources:
                resources.set_current(name, max(0.0, min(maximum, record.resources[name])))
        subject = self._battle_subject(stats, resources, TagSet(species.tags))
        for state_id in record.states:  # the states it carried out of the last battle
            if subject.states is not None and subject.states.registry.get(state_id) is not None:
                subject.states.apply(state_id)
        return subject

    def _creature_unit(self, member_id, side, record, species):
        from asteria.rpg import PartyMember

        subject = self._creature_subject(record, species)
        return PartyMember(
            member_id,
            side,
            subject,
            ability_ids=self.pet_moves(record),
            initiative=subject.stats.get("speed"),
            initiative_stat="speed",
            initiative_expression=self.rules.initiative_expression,
        )

    def _pet_unit(self, pet):
        species = self.pet_species(pet)
        if species is None:
            raise GameSessionError(f"unknown pet species {pet.species_id}")
        return self._creature_unit(self.pet_member_id(pet), "heroes", pet, species)

    def _species_foe_unit(self, member, serial, rng):
        """A wild creature or a trainer's team member built from an encounter member."""
        from asteria.rpg.pets import PetRecord

        species = self.project.rpg_database.pet_species[member.pet_species_id]
        level = member.level
        if member.level_max:
            level = rng.randint(member.level, member.level_max)
        rules = self.pet_rules
        genes = dict(member.genes)
        if rules is not None and not genes:
            genes = rules.roll_genes(species.stats, rng)
        record = PetRecord(
            f"{member.pet_species_id}#{serial}",
            member.pet_species_id,
            level=level,
            moves=member.moves,
            genes=genes,
        )
        if rules is not None and rules.max_moves and not record.moves:
            record.moves = list(record.known_moves(species, rules.max_moves))
        member_id = f"{member.pet_species_id}:{serial}"
        foes = getattr(self, "_species_foes", None)
        if foes is None:
            foes = self._species_foes = {}
        foes[member_id] = record
        return self._creature_unit(member_id, "enemies", record, species)

    def _write_battle_pets_to_save(self):
        """After a battle: each party pet keeps its resources and lasting states."""
        battle = self.battle
        if battle is None:
            return
        for member in battle.parties["heroes"].members:
            pet = self.pet_of_member(member.member_id)
            if pet is None:
                continue
            pool = member.subject.resources
            counters = self.rules.battle_counters or {}  # these live for one battle only
            pet.resources = {
                name: float(pool.current(name))
                for name in pool.to_data()["values"]
                if name not in counters
            }
            states = member.subject.states
            policies = battle.battle_states.policies
            pet.states = (
                [
                    a.state_id
                    for a in states.active_states()
                    if not getattr(policies.get(a.state_id), "battle_only", False)
                ]
                if states is not None
                else []
            )

    # -- the stage and the bench --------------------------------------------------------------
    def _battle_slots(self):
        rules = self.pet_rules
        return rules.battle_slots if rules is not None else 0

    def creature_ids(self, side):
        """The creature units of ``side`` (owned pets, species foes), in party order."""
        battle = self.battle
        return tuple(
            m.member_id
            for m in battle.parties[side].members
            if self.unit_record(m.member_id) is not None
        )

    def stage_ids(self, side):
        """Creatures of ``side`` standing on the stage now."""
        battle = self.battle
        return tuple(m for m in self.creature_ids(side) if battle.is_active(battle.member(m)))

    def bench_ids(self, side):
        """Creatures of ``side`` waiting on the bench that could still come in."""
        battle = self.battle
        return tuple(
            m
            for m in self.creature_ids(side)
            if m in battle.benched and battle.standing(battle.member(m))
        )

    def side_standing(self, side):
        """Whether ``side`` still has anyone on the stage or able to come in from the bench."""
        battle = self.battle
        if battle is None:
            return False
        return bool(
            self.bench_ids(side) or any(battle.is_active(m) for m in battle.parties[side].members)
        )

    def switch_needed(self, side="heroes"):
        """True while a creature slot of ``side`` is empty and the bench could fill it. The
        slots (``PetRules.battle_slots``) are for creatures: other combatants never bench."""
        slots = self._battle_slots()
        if self.battle is None or not slots or not self.bench_ids(side):
            return False
        return len(self.stage_ids(side)) < slots

    def send_in_pet(self, member_id):
        """Bring a benched unit onto the stage into an empty slot (after one fell): no turn."""
        if self.battle is None:
            raise GameSessionError("no active battle")
        member_id = str(member_id)
        side = self.battle.member(member_id).side
        if member_id not in self.bench_ids(side):
            raise GameSessionError(f"{member_id} is not waiting on the bench")
        if not self.switch_needed(side):
            raise GameSessionError(Words("battle.switch.no_room", "There is no room on the stage"))
        self.battle.send_in(member_id)
        pet = self.pet_of_member(member_id)
        if pet is not None:
            self._pets_sent.add(pet.instance_id)
        self._log("sent_in", member_id=member_id, data={"side": side})
        return member_id

    def switch_pet(self, out_member_id, in_member_id):
        """Swap a stage unit for a benched one as an action (``switch_costs_turn``: the host
        ends the turn when this returns True)."""
        if self.battle is None:
            raise GameSessionError("no active battle")
        out_member_id, in_member_id = str(out_member_id), str(in_member_id)
        side = self.battle.member(out_member_id).side
        if in_member_id not in self.bench_ids(side):
            raise GameSessionError(f"{in_member_id} is not waiting on the bench")
        if out_member_id not in self.stage_ids(side):
            raise GameSessionError(f"{out_member_id} is not on the stage")
        self.battle.bench(out_member_id)
        pool = self.battle.member(out_member_id).subject.resources
        for name, (_low, _high, start) in (self.rules.battle_counters or {}).items():
            if pool.contains(name):  # a creature called back loses its battle counters
                pool.set_current(name, start)
        self.battle.send_in(in_member_id)
        pet = self.pet_of_member(in_member_id)
        if pet is not None:
            self._pets_sent.add(pet.instance_id)
        self._log(
            "switched", member_id=out_member_id, target_ids=(in_member_id,), data={"side": side}
        )
        rules = self.pet_rules
        return rules is None or rules.switch_costs_turn

    def _refill_slots(self, side):
        """Fill the empty stage slots of a side whose host does not choose (the foes): the
        first standing benched members come in, in party order."""
        sent = []
        while self.switch_needed(side):
            member_id = self.bench_ids(side)[0]
            self.battle.send_in(member_id)
            self._log("sent_in", member_id=member_id, data={"side": side})
            sent.append(member_id)
        return tuple(sent)

    def open_pet_storage(self):
        """Ask the host to show the party / storage screen (the PET_STORAGE command)."""
        if self.pet_rules is None or not self.pet_rules.storage:
            raise GameSessionError(Words("pets.no_storage", "There is nowhere to keep it"))
        self.pet_storage_requested = True
        return True

    def switch_candidates(self, actor_id):
        """The benched units ``actor_id``'s side could switch to now."""
        if self.battle is None:
            return ()
        return self.bench_ids(self.battle.member(actor_id).side)

    def battle_profile_key(self, member_id):
        """Which combatant visual profile draws a unit: a creature's species visual (the back
        one on the player's side when set), else the member's kind."""
        member_id = str(member_id)
        record = self.unit_record(member_id)
        if record is not None:
            species = self.pet_species(record)
            if species is not None:
                if member_id.startswith(PET_MEMBER_PREFIX):
                    key = species.back_visual_profile_id or species.visual_profile_id
                else:
                    key = species.visual_profile_id
                if key:
                    return key
        return member_id.split(":", 1)[0]

    # -- sending out and experience ---------------------------------------------------------
    def _send_out_pet(self, actor_id, definition):
        """Before an ability that needs a pet: its stats become the user's ``pet_*`` stats, and
        the pet will share the win's experience."""
        if not getattr(definition, "requires_pet", ""):
            return
        pet = self.active_pet()
        if pet is None:
            return
        stats = self.battle.member(actor_id).subject.stats
        for name, value in self.pet_stats(pet).items():
            stats.set(name, value)
        self._pets_sent.add(pet.instance_id)

    def _foe_experience(self, member_id):
        """What beating a foe is worth to creatures: a species foe's ``exp_yield x level``,
        else the sum of the enemy's reward experience."""
        record = self.foe_record(member_id)
        if record is not None:
            species = self.pet_species(record)
            return float(species.exp_yield) * record.level if species is not None else 0.0
        definition = self.foe_definition(str(member_id).rsplit(":", 1)[0])
        if definition is None:
            return 0.0
        return float(sum(definition.reward.experience.values()))

    def _grow_pet_resources(self, pet, maxima_before):
        """Current resources after a level up or evolution, by ``PetRules.level_up_heal``."""
        rules = self.pet_rules
        if rules is None or not pet.resources:
            return
        after = self.pet_resources_at(pet)
        for name, maximum in after.items():
            if name not in pet.resources:
                continue
            if rules.level_up_heal == "full":
                pet.resources[name] = maximum
            elif rules.level_up_heal == "delta":
                gained = maximum - maxima_before.get(name, maximum)
                pet.resources[name] = max(0.0, min(maximum, pet.resources[name] + gained))

    def _pet_gains(self, pet, species, amount):
        old_level = pet.level
        maxima_before = self.pet_resources_at(pet)
        gained = pet.gain(species, amount)
        if gained:
            self._grow_pet_resources(pet, maxima_before)
            self._teach_new_moves(pet, species, old_level)
        if species.affinity_per_battle:
            pet.add_affinity(species, species.affinity_per_battle)
        self._log(
            "pet_experience",
            member_id=pet.instance_id,
            data={"gained": gained, "level": pet.level, "species": pet.species_id},
        )
        evolution = pet.evolution_for(species)
        if evolution is not None and evolution.automatic and not evolution.item_id:
            self.evolve_pet(pet.instance_id)
        return gained

    def _pets_gain_experience(self, defeated_member_ids=()):
        rules = self.pet_rules
        share = rules.exp_share if rules is not None else "none"
        by_id = {p.instance_id: p for p in self.save.rpg_state.pets}
        fought = [by_id[i] for i in sorted(self._pets_sent) if i in by_id]
        if share == "none":
            for pet in fought:
                species = self.pet_species(pet)
                if species is not None:
                    self._pet_gains(pet, species, species.exp_per_battle)
            self._pets_sent = set()
            return
        total = sum(self._foe_experience(m) for m in defeated_member_ids) / rules.exp_divisor
        receivers = fought
        if share == "party":
            receivers = [p for p in self.party_pets() if self.pet_species(p) is not None]
        amount = total / len(fought) if share == "split" and fought else total
        if rules.exp_whole:
            amount = float(int(amount))  # whole points, rounded down
        for pet in receivers:
            species = self.pet_species(pet)
            if species is not None:
                self._pet_gains(pet, species, amount)
        self._pets_sent = set()
