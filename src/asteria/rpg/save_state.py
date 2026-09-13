from __future__ import annotations

from dataclasses import dataclass

from .actors import RpgActorSnapshot, RpgDatabase
from .items import EquipmentLoadout, Inventory
from .progression import ProgressionRuntime
from .progression_graph import ProgressionAllocationRuntime


def _ids(values, label):
    out = []
    for value in values:
        value = str(value).strip()
        if not value:
            raise ValueError(f"{label} is required")
        if value in out:
            raise ValueError(f"duplicate {label}: {value}")
        out.append(value)
    return tuple(out)




@dataclass(slots=True)
class ActorProgressionState:
    """Per-actor mutable progression metadata persisted in a game save.

    Progression tracks/graphs remain generic engine mechanisms. This record owns
    player-state that cannot live in immutable ActorDefinition: level/EXP,
    spendable point balances, unlocked classes/jobs, and currently active
    classes/jobs.
    """

    level: int = 1
    experience: float = 0.0
    points: dict[str, float] = None
    unlocked_class_ids: tuple[str, ...] = ()
    active_class_ids: tuple[str, ...] = ()

    SCHEMA = "asteria.rpg.actor_progression_state"
    VERSION = 1

    def __init__(
        self, level=1, experience=0.0, *, points=None,
        unlocked_class_ids=(), active_class_ids=()
    ):
        self.level=int(level)
        self.experience=float(experience)
        if self.level < 1:
            raise ValueError("actor level must be >= 1")
        if self.experience < 0:
            raise ValueError("actor experience must be >= 0")
        self.points={}
        for key,value in dict(points or {}).items():
            key=str(key).strip()
            value=float(value)
            if not key:
                raise ValueError("actor progression point id is required")
            if value < 0:
                raise ValueError("actor progression points must be >= 0")
            self.points[key]=value
        self.unlocked_class_ids=_ids(unlocked_class_ids,"unlocked class id")
        self.active_class_ids=_ids(active_class_ids,"active class id")
        missing=set(self.active_class_ids)-set(self.unlocked_class_ids)
        if missing:
            raise ValueError("active classes must be unlocked")

    def validate(self,database):
        for class_id in self.unlocked_class_ids:
            if class_id not in database.classes:
                raise ValueError(f"actor progression references unknown class {class_id}")
        return True

    def to_data(self):
        return {
            "schema":self.SCHEMA,"version":self.VERSION,
            "level":self.level,"experience":self.experience,
            "points":{k:self.points[k] for k in sorted(self.points)},
            "unlocked_class_ids":list(self.unlocked_class_ids),
            "active_class_ids":list(self.active_class_ids),
        }

    @classmethod
    def from_data(cls,data):
        expected={
            "schema","version","level","experience","points",
            "unlocked_class_ids","active_class_ids",
        }
        if set(data)!=expected or data.get("schema")!=cls.SCHEMA or data.get("version")!=1:
            raise ValueError("unsupported actor progression state")
        return cls(
            data["level"],data["experience"],points=data["points"],
            unlocked_class_ids=data["unlocked_class_ids"],
            active_class_ids=data["active_class_ids"],
        )

@dataclass(slots=True)
class RpgRuntimeState:
    """Saveable player-facing RPG state; definitions remain in Project/RpgDatabase."""

    inventory: Inventory
    progression: ProgressionRuntime
    loadouts: dict[str, EquipmentLoadout]
    party_actor_ids: tuple[str, ...]
    currencies: dict[str, float]
    actor_snapshots: dict[str, RpgActorSnapshot]
    progression_allocations: dict[str, ProgressionAllocationRuntime]
    actor_progression: dict[str, ActorProgressionState]
    party_active_actor_ids: tuple[str, ...]
    party_placements: dict[str, str]

    SCHEMA = "asteria.rpg.runtime_state"
    VERSION = 5

    def __init__(
        self,
        *,
        inventory=None,
        progression=None,
        loadouts=None,
        party_actor_ids=(),
        currencies=None,
        actor_snapshots=None,
        progression_allocations=None,
        actor_progression=None,
        party_active_actor_ids=None,
        party_placements=None,
    ):
        self.inventory = inventory or Inventory()
        self.progression = progression or ProgressionRuntime()
        self.loadouts = dict(loadouts or {})
        if any(not isinstance(x, EquipmentLoadout) for x in self.loadouts.values()):
            raise TypeError("loadouts must contain EquipmentLoadout values")
        self.party_actor_ids = _ids(party_actor_ids, "party actor id")
        self.party_active_actor_ids = _ids(
            self.party_actor_ids if party_active_actor_ids is None else party_active_actor_ids,
            "active party actor id",
        )
        if not set(self.party_active_actor_ids).issubset(set(self.party_actor_ids)):
            raise ValueError("active party actors must belong to party roster")
        self.party_placements = {}
        for actor_id, slot_id in dict(party_placements or {}).items():
            actor_id=str(actor_id).strip(); slot_id=str(slot_id).strip()
            if actor_id not in self.party_actor_ids:
                raise ValueError("party placement actor must belong to party roster")
            if not slot_id:
                raise ValueError("party placement slot id is required")
            self.party_placements[actor_id]=slot_id
        self.actor_snapshots = dict(actor_snapshots or {})
        self.progression_allocations = dict(progression_allocations or {})
        self.actor_progression = dict(actor_progression or {})
        if any(not isinstance(x, ActorProgressionState) for x in self.actor_progression.values()):
            raise TypeError("actor_progression must contain ActorProgressionState values")
        if any(
            not isinstance(x, ProgressionAllocationRuntime)
            for x in self.progression_allocations.values()
        ):
            raise TypeError(
                "progression_allocations must contain ProgressionAllocationRuntime values"
            )
        if any(
            not isinstance(x, RpgActorSnapshot) for x in self.actor_snapshots.values()
        ):
            raise TypeError("actor_snapshots must contain RpgActorSnapshot values")
        for actor_id, snapshot in self.actor_snapshots.items():
            if str(actor_id) != snapshot.actor_id:
                raise ValueError("actor snapshot key does not match actor_id")
        self.currencies = {}
        for key, value in dict(currencies or {}).items():
            key = str(key).strip()
            if not key:
                raise ValueError("currency id is required")
            value = float(value)
            if value < 0:
                raise ValueError("currency value must be >= 0")
            self.currencies[key] = value

    def validate(self, database):
        if not isinstance(database, RpgDatabase):
            raise TypeError("database must be RpgDatabase")
        database.validate()
        for item_id in self.inventory._counts:
            if item_id not in database.items:
                raise ValueError(f"inventory references unknown item {item_id}")
        for actor_id in self.party_actor_ids:
            if actor_id not in database.actors:
                raise ValueError(f"party references unknown actor {actor_id}")
        for actor_id in self.party_active_actor_ids:
            if actor_id not in database.actors:
                raise ValueError(f"active party references unknown actor {actor_id}")
        for actor_id, progression_state in self.actor_progression.items():
            if actor_id not in database.actors:
                raise ValueError(f"actor progression references unknown actor {actor_id}")
            progression_state.validate(database)
        for actor_id, snapshot in self.actor_snapshots.items():
            if actor_id not in database.actors:
                raise ValueError(f"actor snapshot references unknown actor {actor_id}")
            if snapshot.ability_state is not None:
                from .ability_build import ActorAbilityState
                state = ActorAbilityState.from_data(snapshot.ability_state)
                for passive_id in state.active_passives:
                    if passive_id not in database.passives:
                        raise ValueError(f"actor snapshot references unknown passive {passive_id}")
                for rule_id in state.selected_evolutions.values():
                    if rule_id not in database.ability_evolutions:
                        raise ValueError(f"actor snapshot references unknown ability evolution {rule_id}")
        for actor_id, loadout in self.loadouts.items():
            if actor_id not in database.actors:
                raise ValueError(f"loadout references unknown actor {actor_id}")
            for item in loadout.equipped():
                if item.equipment.equipment_id not in database.equipment:
                    raise ValueError(
                        f"loadout references unknown equipment {item.equipment.equipment_id}"
                    )
                if item.growth is not None:
                    growth_id = item.growth.definition.growth_id
                    if growth_id not in database.equipment_growth:
                        raise ValueError(
                            f"loadout references unknown equipment growth {growth_id}"
                        )
                    if item.equipment.growth_id != growth_id:
                        raise ValueError(
                            f"equipment instance {item.instance_id} growth does not match equipment definition"
                        )
                for attachment in item.attachments.values():
                    if attachment.attachment_id not in database.attachments:
                        raise ValueError(
                            f"loadout references unknown attachment {attachment.attachment_id}"
                        )
        expected = set(database.progression_tracks)
        if set(self.progression.definitions) != expected:
            raise ValueError(
                "progression runtime definitions do not match RPG database"
            )
        expected_graphs = set(database.progression_graphs)
        for scope_id, allocation in self.progression_allocations.items():
            if not str(scope_id).strip():
                raise ValueError("progression allocation scope id is required")
            if set(allocation.definitions) != expected_graphs:
                raise ValueError(
                    "progression allocation definitions do not match RPG database"
                )
            allocation.validate()
        return True

    def to_data(self):
        return {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "inventory": self.inventory.to_data(),
            "progression": self.progression.to_data(),
            "loadouts": {k: self.loadouts[k].to_data() for k in sorted(self.loadouts)},
            "party_actor_ids": list(self.party_actor_ids),
            "party_active_actor_ids": list(self.party_active_actor_ids),
            "party_placements": {k:self.party_placements[k] for k in sorted(self.party_placements)},
            "currencies": {k: self.currencies[k] for k in sorted(self.currencies)},
            "actor_snapshots": {
                k: self.actor_snapshots[k].to_data()
                for k in sorted(self.actor_snapshots)
            },
            "progression_allocations": {
                k: self.progression_allocations[k].to_data()
                for k in sorted(self.progression_allocations)
            },
            "actor_progression": {
                k: self.actor_progression[k].to_data()
                for k in sorted(self.actor_progression)
            },
        }

    @classmethod
    def from_data(cls, data, database, *, hooks=None):
        if data.get("schema") != cls.SCHEMA or data.get("version") not in {1, 2, 3, 4, 5}:
            raise ValueError("unsupported RPG runtime state")
        version = data["version"]
        expected_v1 = {
            "schema",
            "version",
            "inventory",
            "progression",
            "loadouts",
            "party_actor_ids",
            "currencies",
        }
        expected_v2 = expected_v1 | {"actor_snapshots"}
        expected_v3 = expected_v2 | {"progression_allocations"}
        expected_v4 = expected_v3 | {"actor_progression"}
        expected_v5 = expected_v4 | {"party_active_actor_ids","party_placements"}
        expected = expected_v5 if version == 5 else expected_v4 if version == 4 else expected_v3 if version == 3 else expected_v2 if version == 2 else expected_v1
        if set(data) != expected:
            raise ValueError("invalid RPG runtime state")
        result = cls(
            inventory=Inventory.from_data(data["inventory"]),
            progression=ProgressionRuntime.from_data(
                data["progression"], database.progression_tracks.values()
            ),
            loadouts={
                actor_id: EquipmentLoadout.from_data(
                    raw,
                    equipment=database.equipment,
                    attachments=database.attachments,
                    growth_definitions=database.equipment_growth,
                    hooks=hooks,
                )
                for actor_id, raw in data["loadouts"].items()
            },
            party_actor_ids=data["party_actor_ids"],
            party_active_actor_ids=data.get("party_active_actor_ids",data["party_actor_ids"]),
            party_placements=data.get("party_placements",{}),
            currencies=data["currencies"],
            actor_snapshots={
                actor_id: RpgActorSnapshot.from_data(raw)
                for actor_id, raw in data.get("actor_snapshots", {}).items()
            },
            progression_allocations={
                scope_id: ProgressionAllocationRuntime.from_data(
                    raw, database.progression_graphs.values(), hooks=hooks
                )
                for scope_id, raw in data.get("progression_allocations", {}).items()
            },
            actor_progression={
                actor_id: ActorProgressionState.from_data(raw)
                for actor_id, raw in data.get("actor_progression", {}).items()
            },
        )
        result.validate(database)
        return result
