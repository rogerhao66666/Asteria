"""Pets: the roster, stats, evolution, affinity and experience."""

from __future__ import annotations

from .support import (  # noqa: F401 - the names the moved methods use
    BattleLogEntry,
    EquipOffer,
    GameSessionError,
    _base_relative,
    _EitherBlocks,
    _merge_casts,
    describe_condition,
)


class PetsMixin:
    # -- pets ---------------------------------------------------------------------------------
    def pets(self):
        """The owned pets (``rpg.pets.PetRecord``)."""
        return tuple(self.save.rpg_state.pets)

    def pet_species(self, pet):
        return self.project.rpg_database.pet_species.get(pet.species_id)

    def active_pet(self):
        """The pet that abilities send out: the chosen one, else the first owned."""
        state = self.save.rpg_state
        for pet in state.pets:
            if pet.instance_id == state.active_pet_id:
                return pet
        return state.pets[0] if state.pets else None

    def add_pet(self, species_id, *, level=1, nickname=""):
        from asteria.rpg.pets import PetRecord

        if species_id not in self.project.rpg_database.pet_species:
            raise GameSessionError(f"unknown pet species {species_id}")
        state = self.save.rpg_state
        taken = {p.instance_id for p in state.pets}
        serial = 1
        while f"{species_id}#{serial}" in taken:
            serial += 1
        pet = PetRecord(f"{species_id}#{serial}", species_id, nickname, level)
        state.pets.append(pet)
        if not state.active_pet_id:
            state.active_pet_id = pet.instance_id
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

    def pet_stats(self, pet=None):
        """``{"pet_<stat>": value, "pet_level": n}`` of a pet (default: the active one)."""
        pet = pet or self.active_pet()
        species = self.pet_species(pet) if pet is not None else None
        if species is None:
            return {}
        values = {f"pet_{k}": v for k, v in species.stats_at(pet.level).items()}
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
        pet.evolve(evolution)
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

    def _pets_gain_experience(self):
        for instance_id in sorted(self._pets_sent):
            pet = next((p for p in self.save.rpg_state.pets if p.instance_id == instance_id), None)
            species = self.pet_species(pet) if pet is not None else None
            if species is None:
                continue
            gained = pet.gain(species, species.exp_per_battle)
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
        self._pets_sent = set()
