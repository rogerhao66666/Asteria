from __future__ import annotations

from dataclasses import dataclass

from asteria.rpg import (
    FormationDefinition,
    PartyPlacementDefinition,
    PartyPresentationPolicyDefinition,
    PartySetupDefinition,
)


class RpgPartyFormationAuthoringError(RuntimeError):
    pass


@dataclass(slots=True)
class _MapCommand:
    mapping: dict
    key: str
    new_value: object | None
    old_value: object | None
    description: str

    @property
    def label(self):
        return self.description

    def redo(self):
        if self.new_value is None:
            self.mapping.pop(self.key, None)
        else:
            self.mapping[self.key] = self.new_value

    def undo(self):
        if self.old_value is None:
            self.mapping.pop(self.key, None)
        else:
            self.mapping[self.key] = self.old_value


@dataclass(frozen=True, slots=True)
class PartyFormationSection:
    section_id: str
    label: str
    mode: str
    detail_groups: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PartyFormationInformationArchitecture:
    sections: tuple[PartyFormationSection, ...] = (
        PartyFormationSection(
            "parties",
            "Party Setups",
            "roster_detail",
            ("Identity", "Roster", "Active & Reserve", "Policies", "Formation"),
        ),
        PartyFormationSection(
            "formations", "Formations", "formation_canvas", ("Canvas", "Selected Slot", "Position", "Tags", "Adjacency")
        ),
        PartyFormationSection(
            "presentation", "Party UI", "profile_detail", ("Groups", "Labels", "Visible Limits", "Focused Member")
        ),
    )
    primary_navigation: str = "category_sidebar"
    roster_pattern: str = "browser_plus_active_reserve"
    formation_pattern: str = "canvas_plus_contextual_slot_inspector"
    progressive_disclosure: bool = True
    show_all_members_as_full_cards: bool = False
    show_all_details_simultaneously: bool = False

    def section(self, key):
        return next((x for x in self.sections if x.section_id == str(key)), None)


class RpgPartyFormationAuthoringController:
    information_architecture = PartyFormationInformationArchitecture()

    def __init__(self, document):
        self.document = document

    @property
    def project(self):
        if self.document.project is None:
            raise RpgPartyFormationAuthoringError("project required")
        return self.document.project

    @property
    def database(self):
        return self.project.rpg_database

    def _execute(self, c):
        self.document.execute(c)
        return c

    def _coerce(self, value, cls):
        if isinstance(value, cls):
            return value
        if isinstance(value, dict):
            return cls.from_data(value)
        raise TypeError(f"value must be {cls.__name__} or serialized data")

    def create_formation(self, value):
        value = self._coerce(value, FormationDefinition)
        key = value.formation_id
        if key in self.database.formations:
            raise RpgPartyFormationAuthoringError(f"duplicate formation: {key}")
        self._execute(_MapCommand(self.database.formations, key, value, None, f"Add Formation {key}"))
        return value

    def edit_formation(self, formation_id, value):
        key = str(formation_id)
        old = self.database.formations.get(key)
        if old is None:
            raise RpgPartyFormationAuthoringError(f"unknown formation: {key}")
        value = self._coerce(value, FormationDefinition)
        if value.formation_id != key:
            raise RpgPartyFormationAuthoringError("formation id cannot change during edit")
        self._execute(_MapCommand(self.database.formations, key, value, old, f"Edit Formation {key}"))
        return value

    def delete_formation(self, formation_id):
        key = str(formation_id)
        old = self.database.formations.get(key)
        if old is None:
            raise RpgPartyFormationAuthoringError(f"unknown formation: {key}")
        refs = [x.party_id for x in self.database.party_setups.values() if x.formation_id == key]
        if refs:
            raise RpgPartyFormationAuthoringError(
                f"formation {key} is referenced by parties: " + ", ".join(sorted(refs))
            )
        self._execute(_MapCommand(self.database.formations, key, None, old, f"Delete Formation {key}"))

    def create_party(self, value):
        value = self._coerce(value, PartySetupDefinition)
        key = value.party_id
        if key in self.database.party_setups:
            raise RpgPartyFormationAuthoringError(f"duplicate party setup: {key}")
        self._validate_party(value)
        self._execute(_MapCommand(self.database.party_setups, key, value, None, f"Add Party Setup {key}"))
        return value

    def edit_party(self, party_id, value):
        key = str(party_id)
        old = self.database.party_setups.get(key)
        if old is None:
            raise RpgPartyFormationAuthoringError(f"unknown party setup: {key}")
        value = self._coerce(value, PartySetupDefinition)
        if value.party_id != key:
            raise RpgPartyFormationAuthoringError("party id cannot change during edit")
        self._validate_party(value)
        self._execute(_MapCommand(self.database.party_setups, key, value, old, f"Edit Party Setup {key}"))
        return value

    def delete_party(self, party_id):
        key = str(party_id)
        old = self.database.party_setups.get(key)
        if old is None:
            raise RpgPartyFormationAuthoringError(f"unknown party setup: {key}")
        self._execute(_MapCommand(self.database.party_setups, key, None, old, f"Delete Party Setup {key}"))

    def _validate_party(self, value):
        unknown = sorted(set(value.roster_actor_ids) - set(self.database.actors))
        if unknown:
            raise RpgPartyFormationAuthoringError("unknown actors: " + ", ".join(unknown))
        if value.formation_id is not None:
            formation = self.database.formations.get(value.formation_id)
            if formation is None:
                raise RpgPartyFormationAuthoringError(f"unknown formation: {value.formation_id}")
            slots = {x.slot_id for x in formation.slots}
            missing = sorted({x.slot_id for x in value.placements} - slots)
            if missing:
                raise RpgPartyFormationAuthoringError("unknown formation slots: " + ", ".join(missing))

    def set_active(self, party_id, active_actor_ids):
        old = self.database.party_setups[str(party_id)]
        active = tuple(active_actor_ids)
        kept = tuple(x for x in old.placements if x.actor_id in set(active))
        value = PartySetupDefinition(
            old.party_id,
            old.display_name,
            roster_actor_ids=old.roster_actor_ids,
            active_actor_ids=active,
            active_capacity=old.active_capacity,
            formation_id=old.formation_id,
            placements=kept,
            allow_reserve=old.allow_reserve,
            allow_swap=old.allow_swap,
            allow_reorder=old.allow_reorder,
            tags=old.tags,
        )
        return self.edit_party(party_id, value)

    def place_actor(self, party_id, actor_id, slot_id):
        old = self.database.party_setups[str(party_id)]
        actor_id = str(actor_id)
        slot_id = str(slot_id)
        if actor_id not in old.active_actor_ids:
            raise RpgPartyFormationAuthoringError("only active actors can be placed")
        placements = [x for x in old.placements if x.actor_id != actor_id and x.slot_id != slot_id]
        placements.append(PartyPlacementDefinition(actor_id, slot_id))
        value = PartySetupDefinition(
            old.party_id,
            old.display_name,
            roster_actor_ids=old.roster_actor_ids,
            active_actor_ids=old.active_actor_ids,
            active_capacity=old.active_capacity,
            formation_id=old.formation_id,
            placements=placements,
            allow_reserve=old.allow_reserve,
            allow_swap=old.allow_swap,
            allow_reorder=old.allow_reorder,
            tags=old.tags,
        )
        return self.edit_party(party_id, value)

    def set_presentation_profile(self, profile_id, profile):
        key = str(profile_id).strip()
        if not key:
            raise RpgPartyFormationAuthoringError("profile id required")
        if not isinstance(profile, PartyPresentationPolicyDefinition):
            if isinstance(profile, dict):
                profile = PartyPresentationPolicyDefinition.from_data(profile)
            else:
                raise TypeError("profile must be PartyPresentationPolicyDefinition or data")
        if profile.profile_id != key:
            raise RpgPartyFormationAuthoringError("profile id cannot change during edit")
        old = self.database.party_presentation_policies.get(key)
        self._execute(
            _MapCommand(self.database.party_presentation_policies, key, profile, old, f"Set Party UI Profile {key}")
        )
        return profile

    def delete_presentation_profile(self, profile_id):
        key = str(profile_id)
        old = self.database.party_presentation_policies.get(key)
        if old is None:
            raise RpgPartyFormationAuthoringError(f"unknown party UI profile: {key}")
        self._execute(
            _MapCommand(self.database.party_presentation_policies, key, None, old, f"Delete Party UI Profile {key}")
        )

    def validate(self):
        try:
            self.project.validate()
        except Exception as exc:
            return (str(exc),)
        return ()
