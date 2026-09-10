from __future__ import annotations

from dataclasses import dataclass

from .actors import RpgActorSnapshot, RpgDatabase
from .items import EquipmentLoadout, Inventory
from .progression import ProgressionRuntime


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
class RpgRuntimeState:
    """Saveable player-facing RPG state; definitions remain in Project/RpgDatabase."""

    inventory: Inventory
    progression: ProgressionRuntime
    loadouts: dict[str, EquipmentLoadout]
    party_actor_ids: tuple[str, ...]
    currencies: dict[str, float]
    actor_snapshots: dict[str, RpgActorSnapshot]

    SCHEMA = "asteria.rpg.runtime_state"
    VERSION = 2

    def __init__(
        self,
        *,
        inventory=None,
        progression=None,
        loadouts=None,
        party_actor_ids=(),
        currencies=None,
        actor_snapshots=None,
    ):
        self.inventory = inventory or Inventory()
        self.progression = progression or ProgressionRuntime()
        self.loadouts = dict(loadouts or {})
        if any(not isinstance(x, EquipmentLoadout) for x in self.loadouts.values()):
            raise TypeError("loadouts must contain EquipmentLoadout values")
        self.party_actor_ids = _ids(party_actor_ids, "party actor id")
        self.actor_snapshots = dict(actor_snapshots or {})
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
        for actor_id in self.actor_snapshots:
            if actor_id not in database.actors:
                raise ValueError(f"actor snapshot references unknown actor {actor_id}")
        for actor_id, loadout in self.loadouts.items():
            if actor_id not in database.actors:
                raise ValueError(f"loadout references unknown actor {actor_id}")
            for item in loadout.equipped():
                if item.equipment.equipment_id not in database.equipment:
                    raise ValueError(
                        f"loadout references unknown equipment {item.equipment.equipment_id}"
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
        return True

    def to_data(self):
        return {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "inventory": self.inventory.to_data(),
            "progression": self.progression.to_data(),
            "loadouts": {k: self.loadouts[k].to_data() for k in sorted(self.loadouts)},
            "party_actor_ids": list(self.party_actor_ids),
            "currencies": {k: self.currencies[k] for k in sorted(self.currencies)},
            "actor_snapshots": {
                k: self.actor_snapshots[k].to_data()
                for k in sorted(self.actor_snapshots)
            },
        }

    @classmethod
    def from_data(cls, data, database, *, hooks=None):
        if data.get("schema") != cls.SCHEMA or data.get("version") not in {1, 2}:
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
        if set(data) != (expected_v2 if version == 2 else expected_v1):
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
                    hooks=hooks,
                )
                for actor_id, raw in data["loadouts"].items()
            },
            party_actor_ids=data["party_actor_ids"],
            currencies=data["currencies"],
            actor_snapshots={
                actor_id: RpgActorSnapshot.from_data(raw)
                for actor_id, raw in data.get("actor_snapshots", {}).items()
            },
        )
        result.validate(database)
        return result
