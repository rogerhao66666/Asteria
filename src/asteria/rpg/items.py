from __future__ import annotations

from dataclasses import dataclass, field

from asteria.core.lifecycle import emit_hook
from asteria.gameplay import (
    Effect,
    GameplayTrigger,
    ModifierSet,
    StatModifier,
    apply_effect,
)


def _id(value, label):
    value = str(value).strip()
    if not value:
        raise ValueError(f"{label} is required")
    return value


def _tags(values):
    return tuple(sorted({_id(x, "tag").lower() for x in values}))


@dataclass(frozen=True, slots=True)
class SocketDefinition:
    socket_id: str
    accepted_tags: tuple[str, ...] = ()
    locked: bool = False

    def __init__(self, socket_id, *, accepted_tags=(), locked=False):
        object.__setattr__(self, "socket_id", _id(socket_id, "socket_id"))
        object.__setattr__(self, "accepted_tags", _tags(accepted_tags))
        object.__setattr__(self, "locked", bool(locked))

    def accepts(self, attachment):
        if self.locked:
            return False
        if not self.accepted_tags:
            return True
        return any(tag in attachment.tags for tag in self.accepted_tags)

    def to_data(self):
        return {
            "socket_id": self.socket_id,
            "accepted_tags": list(self.accepted_tags),
            "locked": self.locked,
        }

    @classmethod
    def from_data(cls, data):
        if set(data) != {"socket_id", "accepted_tags", "locked"}:
            raise ValueError("invalid socket definition")
        return cls(
            data["socket_id"],
            accepted_tags=data["accepted_tags"],
            locked=data["locked"],
        )


@dataclass(frozen=True, slots=True)
class AttachmentDefinition:
    attachment_id: str
    display_name: str
    tags: tuple[str, ...] = ()
    modifiers: tuple[StatModifier, ...] = ()
    granted_abilities: tuple[str, ...] = ()
    triggers: tuple[GameplayTrigger, ...] = ()
    growth_id: str | None = None

    icon_id: str = ""  # a project icon shown in menus; written only when set

    def __init__(
        self,
        attachment_id,
        display_name=None,
        *,
        tags=(),
        modifiers=(),
        granted_abilities=(),
        triggers=(),
        growth_id=None,
        icon_id="",
    ):
        attachment_id = _id(attachment_id, "attachment_id")
        modifiers = tuple(modifiers)
        triggers = tuple(triggers)
        if any(not isinstance(x, StatModifier) for x in modifiers):
            raise TypeError("modifiers must be StatModifier values")
        if any(not isinstance(x, GameplayTrigger) for x in triggers):
            raise TypeError("triggers must be GameplayTrigger values")
        object.__setattr__(self, "attachment_id", attachment_id)
        object.__setattr__(self, "display_name", str(display_name or attachment_id))
        object.__setattr__(self, "tags", _tags(tags))
        object.__setattr__(self, "modifiers", modifiers)
        object.__setattr__(
            self,
            "granted_abilities",
            tuple(dict.fromkeys(_id(x, "ability_id") for x in granted_abilities)),
        )
        object.__setattr__(self, "triggers", triggers)
        object.__setattr__(
            self, "growth_id", None if growth_id is None else _id(growth_id, "growth_id")
        )
        object.__setattr__(self, "icon_id", str(icon_id or "").strip())

    def to_data(self):
        return {
            "schema": "asteria.rpg.attachment",
            "version": 2,
            "attachment_id": self.attachment_id,
            "display_name": self.display_name,
            "tags": list(self.tags),
            "modifiers": [x.to_data() for x in self.modifiers],
            "granted_abilities": list(self.granted_abilities),
            "triggers": [x.to_data() for x in self.triggers],
            "growth_id": self.growth_id,
            **({"icon_id": self.icon_id} if self.icon_id else {}),
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != "asteria.rpg.attachment" or data.get("version") not in {1, 2}:
            raise ValueError("unsupported attachment definition")
        version = data["version"]
        return cls(
            data["attachment_id"],
            data["display_name"],
            tags=data["tags"],
            modifiers=[StatModifier.from_data(x) for x in data["modifiers"]],
            granted_abilities=data["granted_abilities"],
            triggers=[GameplayTrigger.from_data(x) for x in data["triggers"]],
            growth_id=data.get("growth_id") if version >= 2 else None,
            icon_id=data.get("icon_id", ""),
        )


@dataclass(frozen=True, slots=True)
class EquipmentEligibility:
    allowed: bool
    reasons: tuple[str, ...] = ()
    missing_capabilities: tuple[str, ...] = ()
    forbidden_capabilities: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class EquipmentDefinition:
    equipment_id: str
    display_name: str
    slot: str
    tags: tuple[str, ...] = ()
    modifiers: tuple[StatModifier, ...] = ()
    granted_abilities: tuple[str, ...] = ()
    triggers: tuple[GameplayTrigger, ...] = ()
    sockets: tuple[SocketDefinition, ...] = ()
    required_capabilities: tuple[str, ...] = ()
    any_capabilities: tuple[str, ...] = ()
    forbidden_capabilities: tuple[str, ...] = ()
    growth_id: str | None = None
    icon_id: str = ""  # a project icon asset shown in menus; written only when set
    OPTIONAL_DATA = {"icon_id": ""}

    def __init__(
        self,
        equipment_id,
        display_name=None,
        *,
        slot="equipment",
        tags=(),
        modifiers=(),
        granted_abilities=(),
        triggers=(),
        sockets=(),
        required_capabilities=(),
        any_capabilities=(),
        forbidden_capabilities=(),
        growth_id=None,
        icon_id="",
    ):
        equipment_id = _id(equipment_id, "equipment_id")
        modifiers = tuple(modifiers)
        triggers = tuple(triggers)
        sockets = tuple(sockets)
        if any(not isinstance(x, StatModifier) for x in modifiers):
            raise TypeError("modifiers must be StatModifier values")
        if any(not isinstance(x, GameplayTrigger) for x in triggers):
            raise TypeError("triggers must be GameplayTrigger values")
        if any(not isinstance(x, SocketDefinition) for x in sockets):
            raise TypeError("sockets must be SocketDefinition values")
        if len({x.socket_id for x in sockets}) != len(sockets):
            raise ValueError("duplicate socket_id")
        object.__setattr__(self, "equipment_id", equipment_id)
        object.__setattr__(self, "display_name", str(display_name or equipment_id))
        object.__setattr__(self, "slot", _id(slot, "slot"))
        object.__setattr__(self, "tags", _tags(tags))
        object.__setattr__(self, "modifiers", modifiers)
        object.__setattr__(
            self,
            "granted_abilities",
            tuple(dict.fromkeys(_id(x, "ability_id") for x in granted_abilities)),
        )
        object.__setattr__(self, "triggers", triggers)
        object.__setattr__(self, "sockets", sockets)
        object.__setattr__(self, "required_capabilities", _tags(required_capabilities))
        object.__setattr__(self, "any_capabilities", _tags(any_capabilities))
        object.__setattr__(self, "forbidden_capabilities", _tags(forbidden_capabilities))
        object.__setattr__(
            self, "growth_id", None if growth_id is None else _id(growth_id, "growth_id")
        )
        object.__setattr__(self, "icon_id", str(icon_id or "").strip())

    def to_data(self):
        return {
            "schema": "asteria.rpg.equipment",
            "version": 3,
            "equipment_id": self.equipment_id,
            "display_name": self.display_name,
            "slot": self.slot,
            "tags": list(self.tags),
            "modifiers": [x.to_data() for x in self.modifiers],
            "granted_abilities": list(self.granted_abilities),
            "triggers": [x.to_data() for x in self.triggers],
            "sockets": [x.to_data() for x in self.sockets],
            "required_capabilities": list(self.required_capabilities),
            "any_capabilities": list(self.any_capabilities),
            "forbidden_capabilities": list(self.forbidden_capabilities),
            "growth_id": self.growth_id,
            **({"icon_id": self.icon_id} if self.icon_id else {}),
        }

    def eligibility(self, capabilities=()):
        available = {str(x).strip().lower() for x in capabilities if str(x).strip()}
        missing = tuple(x for x in self.required_capabilities if x not in available)
        forbidden = tuple(x for x in self.forbidden_capabilities if x in available)
        any_missing = bool(self.any_capabilities) and not any(
            x in available for x in self.any_capabilities
        )
        reasons = []
        if missing:
            reasons.append("missing required capabilities: " + ", ".join(missing))
        if any_missing:
            reasons.append("requires any capability: " + ", ".join(self.any_capabilities))
        if forbidden:
            reasons.append("forbidden capabilities present: " + ", ".join(forbidden))
        return EquipmentEligibility(not reasons, tuple(reasons), missing, forbidden)

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != "asteria.rpg.equipment" or data.get("version") not in {1, 2, 3}:
            raise ValueError("unsupported equipment definition")
        version = data["version"]
        return cls(
            data["equipment_id"],
            data["display_name"],
            slot=data["slot"],
            tags=data["tags"],
            modifiers=[StatModifier.from_data(x) for x in data["modifiers"]],
            granted_abilities=data["granted_abilities"],
            triggers=[GameplayTrigger.from_data(x) for x in data["triggers"]],
            sockets=[SocketDefinition.from_data(x) for x in data["sockets"]],
            required_capabilities=data.get("required_capabilities", ()) if version >= 2 else (),
            any_capabilities=data.get("any_capabilities", ()) if version >= 2 else (),
            forbidden_capabilities=data.get("forbidden_capabilities", ()) if version >= 2 else (),
            growth_id=data.get("growth_id") if version >= 3 else None,
            icon_id=data.get("icon_id", ""),
        )


@dataclass(frozen=True, slots=True)
class ItemDefinition:
    item_id: str
    display_name: str
    tags: tuple[str, ...] = ()
    stack_limit: int = 99
    use_effects: tuple[Effect, ...] = ()
    icon_id: str = ""  # a project icon asset shown in menus; written only when set
    battle_ability: str = (
        ""  # used in battle, the item runs this ability (its targets, rules and VFX)
    )
    # socketable items (cards, gems, orbs): the attachment the item becomes when socketed, and
    # whether taking it out again destroys it (default: it returns to the bag)
    attachment_id: str = ""
    destroyed_on_removal: bool = False
    OPTIONAL_DATA = {
        "icon_id": "",
        "battle_ability": "",
        "attachment_id": "",
        "destroyed_on_removal": False,
    }

    def __init__(
        self,
        item_id,
        display_name=None,
        *,
        tags=(),
        stack_limit=99,
        use_effects=(),
        icon_id="",
        battle_ability="",
        attachment_id="",
        destroyed_on_removal=False,
    ):
        item_id = _id(item_id, "item_id")
        stack_limit = int(stack_limit)
        use_effects = tuple(use_effects)
        if stack_limit < 1:
            raise ValueError("stack_limit must be >= 1")
        if any(not isinstance(x, Effect) for x in use_effects):
            raise TypeError("use_effects must be Effect values")
        object.__setattr__(self, "item_id", item_id)
        object.__setattr__(self, "display_name", str(display_name or item_id))
        object.__setattr__(self, "tags", _tags(tags))
        object.__setattr__(self, "stack_limit", stack_limit)
        object.__setattr__(self, "use_effects", use_effects)
        object.__setattr__(self, "icon_id", str(icon_id or "").strip())
        object.__setattr__(self, "battle_ability", str(battle_ability or "").strip())
        object.__setattr__(self, "attachment_id", str(attachment_id or "").strip())
        object.__setattr__(self, "destroyed_on_removal", bool(destroyed_on_removal))

    def to_data(self):
        return {
            "schema": "asteria.rpg.item",
            "version": 2,
            "item_id": self.item_id,
            "display_name": self.display_name,
            "tags": list(self.tags),
            "stack_limit": self.stack_limit,
            "use_effects": [x.to_data() for x in self.use_effects],
            **({"icon_id": self.icon_id} if self.icon_id else {}),
            **({"battle_ability": self.battle_ability} if self.battle_ability else {}),
            **({"attachment_id": self.attachment_id} if self.attachment_id else {}),
            **({"destroyed_on_removal": True} if self.destroyed_on_removal else {}),
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != "asteria.rpg.item" or data.get("version") not in {
            1,
            2,
        }:
            raise ValueError("unsupported item definition")
        return cls(
            data["item_id"],
            data["display_name"],
            tags=data["tags"],
            stack_limit=data["stack_limit"],
            use_effects=[]
            if data["version"] == 1
            else [Effect.from_data(x) for x in data["use_effects"]],
            icon_id=data.get("icon_id", ""),
            battle_ability=data.get("battle_ability", ""),
            attachment_id=data.get("attachment_id", ""),
            destroyed_on_removal=bool(data.get("destroyed_on_removal", False)),
        )


INVENTORY_OVERFLOW = ("fill", "reject")


@dataclass(frozen=True, slots=True)
class InventoryRules:
    """How much the party can carry (RPG-01). Every rule is optional; with none, the bag is
    unlimited.

    * ``stack_limits``  - an item stacks up to its own ``stack_limit`` (``stack_limit=1`` makes it
      unique)
    * ``max_kinds``     - how many different items fit (``None`` = no limit); items carrying one of
      ``exempt_tags`` (key items by default) never take a place
    * ``overflow``      - what happens when an amount does not fit: ``"fill"`` keeps what fits,
      ``"reject"``
      keeps none of it. What did not fit is reported in ``Inventory.overflow``.
    """

    rules_id: str
    display_name: str = ""
    stack_limits: bool = True
    max_kinds: int | None = None
    exempt_tags: tuple[str, ...] = ("item.key",)
    overflow: str = "fill"

    def __init__(
        self,
        rules_id,
        display_name="",
        *,
        stack_limits=True,
        max_kinds=None,
        exempt_tags=("item.key",),
        overflow="fill",
    ):
        if max_kinds is not None:
            max_kinds = int(max_kinds)
            if max_kinds < 1:
                raise ValueError("max_kinds must be >= 1 or None")
        if overflow not in INVENTORY_OVERFLOW:
            raise ValueError(f"overflow must be one of {INVENTORY_OVERFLOW}")
        object.__setattr__(self, "rules_id", _id(rules_id, "rules_id"))
        object.__setattr__(self, "display_name", str(display_name or ""))
        object.__setattr__(self, "stack_limits", bool(stack_limits))
        object.__setattr__(self, "max_kinds", max_kinds)
        object.__setattr__(self, "exempt_tags", _tags(exempt_tags))
        object.__setattr__(self, "overflow", overflow)

    def to_data(self):
        return {
            "schema": "asteria.rpg.inventory_rules",
            "version": 1,
            "rules_id": self.rules_id,
            "display_name": self.display_name,
            "stack_limits": self.stack_limits,
            "max_kinds": self.max_kinds,
            "exempt_tags": list(self.exempt_tags),
            "overflow": self.overflow,
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != "asteria.rpg.inventory_rules" or data.get("version") != 1:
            raise ValueError("unsupported inventory rules")
        return cls(
            data["rules_id"],
            data.get("display_name", ""),
            stack_limits=data.get("stack_limits", True),
            max_kinds=data.get("max_kinds"),
            exempt_tags=data.get("exempt_tags", ("item.key",)),
            overflow=data.get("overflow", "fill"),
        )


class Inventory:
    def __init__(self):
        self._counts = {}
        self.rules = None  # InventoryRules; None = unlimited (set by the game session)
        self._lookup = lambda item_id: None
        self.overflow = []  # (item_id, amount that did not fit), newest last

    def configure(self, rules, lookup):
        """Apply ``rules`` (or ``None``); ``lookup(item_id)`` gives the item's definition
        (stack_limit, tags)."""
        self.rules = rules
        self._lookup = lookup
        return self

    def count(self, item_id):
        return self._counts.get(str(item_id), 0)

    def room_for(self, item_id):
        """How many more of ``item_id`` fit (``None`` = unlimited)."""
        rules = self.rules
        if rules is None:
            return None
        item_id = str(item_id)
        definition = self._lookup(item_id)
        room = None
        limit = getattr(definition, "stack_limit", None) if rules.stack_limits else None
        if limit is not None:
            room = max(0, int(limit) - self.count(item_id))
        if rules.max_kinds is not None and self.count(item_id) == 0 and not self._exempt(item_id):
            if self.kinds_used() >= rules.max_kinds:
                room = 0
        return room

    def item_ids(self):
        """Ids of every item held, sorted."""
        return tuple(sorted(self._counts))

    def kinds_used(self):
        return sum(1 for item_id in self._counts if not self._exempt(item_id))

    def _exempt(self, item_id):
        tags = set(getattr(self._lookup(item_id), "tags", ()) or ())
        return bool(self.rules is not None and tags & set(self.rules.exempt_tags))

    def add(self, item_id, amount=1):
        item_id = _id(item_id, "item_id")
        amount = int(amount)
        if amount < 1:
            raise ValueError("amount must be >= 1")
        room = self.room_for(item_id)
        if room is not None and amount > room:
            if self.rules.overflow == "reject" or room == 0:
                self.overflow.append((item_id, amount))
                return self.count(item_id)
            self.overflow.append((item_id, amount - room))
            amount = room
        self._counts[item_id] = self.count(item_id) + amount
        return self._counts[item_id]

    def remove(self, item_id, amount=1):
        item_id = _id(item_id, "item_id")
        amount = int(amount)
        if amount < 1:
            raise ValueError("amount must be >= 1")
        if self.count(item_id) < amount:
            return False
        remain = self.count(item_id) - amount
        if remain:
            self._counts[item_id] = remain
        else:
            self._counts.pop(item_id, None)
        return True

    def to_data(self):
        return {
            "schema": "asteria.rpg.inventory",
            "version": 1,
            "counts": {k: self._counts[k] for k in sorted(self._counts)},
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != "asteria.rpg.inventory" or data.get("version") != 1:
            raise ValueError("unsupported inventory")
        result = cls()
        for key, value in data["counts"].items():
            result._counts[_id(key, "item_id")] = int(value)
        return result

    def replace_from(self, other):
        if not isinstance(other, Inventory):
            raise TypeError("other must be Inventory")
        self._counts = dict(other._counts)
        return self

    def replace_from_data(self, data):
        return self.replace_from(type(self).from_data(data))


@dataclass(slots=True)
class EquippedItem:
    equipment: EquipmentDefinition
    attachments: dict[str, AttachmentDefinition] = field(default_factory=dict)
    instance_id: str = ""
    growth: object | None = None
    # rolled loot (rpg.loot): written only when set, so plain instances save as before
    item_level: int = 1
    rarity: str = ""
    rolled_affixes: tuple = ()
    # wear (rpg.durability): None = the instance does not wear out; a broken one (0) gives nothing
    durability: float | None = None
    max_durability: float = 0.0
    nickname: str = ""
    # refinement (rpg.refine): the level and the modifiers it granted, saved with the instance
    refine_level: int = 0
    refine_modifiers: tuple = ()

    @property
    def broken(self):
        return self.durability is not None and self.durability <= 0.0

    def rename(self, name, *, max_length=24):
        name = " ".join(str(name).split())
        if len(name) > int(max_length):
            raise ValueError(f"a name is at most {max_length} characters")
        self.nickname = name
        return name

    def __post_init__(self):
        from .equipment_growth import EquipmentGrowthRuntime

        self.instance_id = _id(self.instance_id or self.equipment.equipment_id, "instance_id")
        if self.growth is not None:
            if not isinstance(self.growth, EquipmentGrowthRuntime):
                raise TypeError("growth must be EquipmentGrowthRuntime")
            if self.equipment.growth_id is None:
                raise ValueError("equipment does not declare a growth_id")
            if self.growth.definition.growth_id != self.equipment.growth_id:
                raise ValueError("equipment growth definition does not match equipment growth_id")
            self.growth.source = self.instance_id
        existing = dict(self.attachments)
        self.attachments = {}
        for socket_id, attachment in existing.items():
            self.attach(socket_id, attachment)

    def to_data(self):
        return {
            "schema": "asteria.rpg.equipment_instance",
            "version": 2,
            "instance_id": self.instance_id,
            "equipment_id": self.equipment.equipment_id,
            "attachments": {
                key: value.attachment_id for key, value in sorted(self.attachments.items())
            },
            "growth": None if self.growth is None else self.growth.to_data(),
            **({"item_level": self.item_level} if self.item_level != 1 else {}),
            **({"rarity": self.rarity} if self.rarity else {}),
            **(
                {"durability": self.durability, "max_durability": self.max_durability}
                if self.durability is not None
                else {}
            ),
            **({"nickname": self.nickname} if self.nickname else {}),
            **(
                {
                    "refine": {
                        "level": self.refine_level,
                        "modifiers": [m.to_data() for m in self.refine_modifiers],
                    }
                }
                if self.refine_level
                else {}
            ),
            **(
                {"rolled_affixes": [a.to_data() for a in self.rolled_affixes]}
                if self.rolled_affixes
                else {}
            ),
        }

    @classmethod
    def from_data(cls, data, *, equipment, attachments, growth_definitions=None, hooks=None):
        if data.get("schema") != "asteria.rpg.equipment_instance" or data.get("version") not in {
            1,
            2,
        }:
            raise ValueError("unsupported equipment instance")
        equipment_id = data["equipment_id"]
        if equipment_id not in equipment:
            raise KeyError(f"unknown equipment: {equipment_id}")
        growth = None
        if data["version"] >= 2 and data.get("growth") is not None:
            from .equipment_growth import EquipmentGrowthRuntime

            growth = EquipmentGrowthRuntime.from_data(
                data["growth"],
                growth_definitions or {},
                hooks=hooks,
                source=data["instance_id"],
            )
        from .loot import RolledAffix

        item = cls(
            equipment[equipment_id],
            instance_id=data["instance_id"],
            growth=growth,
            item_level=int(data.get("item_level", 1)),
            rarity=str(data.get("rarity", "")),
            rolled_affixes=tuple(RolledAffix.from_data(x) for x in data.get("rolled_affixes", ())),
            durability=data.get("durability"),
            max_durability=float(data.get("max_durability", 0.0)),
            nickname=str(data.get("nickname", "")),
            refine_level=int(data.get("refine", {}).get("level", 0)),
            refine_modifiers=tuple(
                StatModifier.from_data(x) for x in data.get("refine", {}).get("modifiers", ())
            ),
        )
        for socket_id, attachment_id in data["attachments"].items():
            if attachment_id not in attachments:
                raise KeyError(f"unknown attachment: {attachment_id}")
            item.attach(socket_id, attachments[attachment_id])
        return item

    def ensure_growth(self, growth_definitions, *, hooks=None):
        if self.equipment.growth_id is None:
            return None
        if self.growth is None:
            from .equipment_growth import EquipmentGrowthRuntime

            definitions = dict(growth_definitions)
            if self.equipment.growth_id not in definitions:
                raise KeyError(f"unknown equipment growth definition: {self.equipment.growth_id}")
            self.growth = EquipmentGrowthRuntime(
                definitions[self.equipment.growth_id], hooks=hooks, source=self.instance_id
            )
        return self.growth

    def growth_contribution(self):
        return None if self.growth is None else self.growth.contribution()

    def unlocked_socket_ids(self):
        unlocked = {x.socket_id for x in self.equipment.sockets if not x.locked}
        contribution = self.growth_contribution()
        if contribution is not None:
            unlocked.update(contribution.unlocked_sockets)
        return tuple(sorted(unlocked))

    @property
    def evolution_target_id(self):
        contribution = self.growth_contribution()
        return None if contribution is None else contribution.evolution_equipment_id

    def attach(self, socket_id, attachment):
        socket_id = str(socket_id)
        socket = next((x for x in self.equipment.sockets if x.socket_id == socket_id), None)
        if socket is None:
            raise KeyError(f"unknown socket: {socket_id}")
        if not isinstance(attachment, AttachmentDefinition):
            raise TypeError("attachment must be AttachmentDefinition")
        unlocked = set(self.unlocked_socket_ids())
        if socket_id not in unlocked:
            raise ValueError("equipment socket is locked")
        # Growth-unlocked sockets may be authored with locked=True; once the
        # runtime unlock exists, compatibility still follows accepted_tags.
        if socket.accepted_tags and not any(
            tag in attachment.tags for tag in socket.accepted_tags
        ):
            raise ValueError("attachment is not compatible with socket")
        self.attachments[socket_id] = attachment

    def detach(self, socket_id):
        return self.attachments.pop(str(socket_id), None)

    def modifiers(self):
        result = list(self.equipment.modifiers)
        for affix in self.rolled_affixes:
            result.extend(affix.modifiers(self.instance_id))
        contribution = self.growth_contribution()
        if contribution is not None:
            result.extend(contribution.modifiers)
        for socket_id in sorted(self.attachments):
            result.extend(self.attachments[socket_id].modifiers)
        result.extend(self.refine_modifiers)
        return tuple(result)

    def abilities(self):
        result = list(self.equipment.granted_abilities)
        contribution = self.growth_contribution()
        if contribution is not None:
            result.extend(contribution.granted_abilities)
        for socket_id in sorted(self.attachments):
            result.extend(self.attachments[socket_id].granted_abilities)
        return tuple(dict.fromkeys(result))

    def triggers(self):
        result = list(self.equipment.triggers)
        contribution = self.growth_contribution()
        if contribution is not None:
            result.extend(contribution.granted_triggers)
        for socket_id in sorted(self.attachments):
            result.extend(self.attachments[socket_id].triggers)
        return tuple(result)

    def tags(self):
        result = set(self.equipment.tags)
        contribution = self.growth_contribution()
        if contribution is not None:
            result.update(contribution.granted_tags)
            result.update(contribution.granted_capabilities)
        for socket_id in sorted(self.attachments):
            result.update(self.attachments[socket_id].tags)
        return tuple(sorted(result))


@dataclass(frozen=True, slots=True)
class EquipmentSlotDefinition:
    slot_id: str
    accepted_tags: tuple[str, ...] = ()
    capacity: int | None = 1

    def __init__(self, slot_id, *, accepted_tags=(), capacity=1):
        object.__setattr__(self, "slot_id", _id(slot_id, "slot_id"))
        object.__setattr__(self, "accepted_tags", _tags(accepted_tags))
        if capacity is not None:
            capacity = int(capacity)
            if capacity < 1:
                raise ValueError("capacity must be >= 1 or None")
        object.__setattr__(self, "capacity", capacity)

    def to_data(self):
        return {
            "slot_id": self.slot_id,
            "accepted_tags": list(self.accepted_tags),
            "capacity": self.capacity,
        }

    @classmethod
    def from_data(cls, data):
        return cls(
            data["slot_id"],
            accepted_tags=data["accepted_tags"],
            capacity=data["capacity"],
        )

    def accepts(self, equipment):
        return not self.accepted_tags or any(x in equipment.tags for x in self.accepted_tags)


class EquipmentLoadout:
    """Owns equipped instances; derives contributions without mutating base actor data."""

    def __init__(self, slots=(), *, hooks=None, set_definitions=()):
        self.hooks = hooks
        # Equipment set definitions (EquipmentSetDefinition) whose bonuses this
        # loadout contributes; bound from the RPG database when a save loads.
        self.set_definitions = tuple(set_definitions)
        self._slots = {x.slot_id: x for x in slots}
        if len(self._slots) != len(tuple(slots)):
            raise ValueError("duplicate equipment slot")
        self._equipped = {key: [] for key in self._slots}

    def to_data(self):
        return {
            "schema": "asteria.rpg.equipment_loadout",
            "version": 1,
            "slots": [self._slots[key].to_data() for key in sorted(self._slots)],
            "equipped": {
                key: [item.to_data() for item in self._equipped[key]]
                for key in sorted(self._equipped)
            },
        }

    @classmethod
    def from_data(cls, data, *, equipment, attachments, growth_definitions=None, hooks=None):
        if data.get("schema") != "asteria.rpg.equipment_loadout" or data.get("version") != 1:
            raise ValueError("unsupported equipment loadout")
        result = cls([EquipmentSlotDefinition.from_data(x) for x in data["slots"]], hooks=hooks)
        for slot_id, items in data["equipped"].items():
            for raw in items:
                result.equip(
                    slot_id,
                    EquippedItem.from_data(
                        raw,
                        equipment=equipment,
                        attachments=attachments,
                        growth_definitions=growth_definitions or {},
                        hooks=hooks,
                    ),
                    validate_requirements=False,
                )
        return result

    def check_equip(self, slot_id, item, *, capabilities=()):
        slot_id = str(slot_id)
        if slot_id not in self._slots:
            return EquipmentEligibility(False, (f"unknown equipment slot: {slot_id}",))
        if not isinstance(item, EquippedItem):
            raise TypeError("item must be EquippedItem")
        if any(existing.instance_id == item.instance_id for existing in self.equipped()):
            return EquipmentEligibility(False, ("equipment instance is already equipped",))
        slot = self._slots[slot_id]
        if item.equipment.slot != slot_id and not slot.accepts(item.equipment):
            return EquipmentEligibility(False, ("equipment is not compatible with slot",))
        if slot.capacity is not None and len(self._equipped[slot_id]) >= slot.capacity:
            return EquipmentEligibility(False, ("equipment slot is full",))
        return item.equipment.eligibility(capabilities)

    def equip(self, slot_id, item, *, capabilities=(), validate_requirements=True):
        slot_id = str(slot_id)
        emit_hook(
            self.hooks,
            "rpg.equipment.before_equip",
            source=slot_id,
            data={
                "item": item,
                "instance_id": getattr(item, "instance_id", None),
                "equipment_id": getattr(getattr(item, "equipment", None), "equipment_id", None),
            },
        )
        if not isinstance(item, EquippedItem):
            raise TypeError("item must be EquippedItem")
        if validate_requirements:
            eligibility = self.check_equip(slot_id, item, capabilities=capabilities)
            if not eligibility.allowed:
                emit_hook(
                    self.hooks,
                    "rpg.equipment.equip_rejected",
                    source=slot_id,
                    data={
                        "item": item,
                        "instance_id": item.instance_id,
                        "equipment_id": item.equipment.equipment_id,
                        "reasons": eligibility.reasons,
                        "missing_capabilities": eligibility.missing_capabilities,
                        "forbidden_capabilities": eligibility.forbidden_capabilities,
                    },
                )
                if eligibility.reasons and eligibility.reasons[0].startswith(
                    "unknown equipment slot"
                ):
                    raise KeyError(eligibility.reasons[0])
                raise ValueError("; ".join(eligibility.reasons))
        else:
            if slot_id not in self._slots:
                raise KeyError(f"unknown equipment slot: {slot_id}")
            if any(existing.instance_id == item.instance_id for existing in self.equipped()):
                raise ValueError("equipment instance is already equipped")
            slot = self._slots[slot_id]
            if item.equipment.slot != slot_id and not slot.accepts(item.equipment):
                raise ValueError("equipment is not compatible with slot")
            if slot.capacity is not None and len(self._equipped[slot_id]) >= slot.capacity:
                raise ValueError("equipment slot is full")
        self._equipped[slot_id].append(item)
        emit_hook(
            self.hooks,
            "rpg.equipment.after_equip",
            source=slot_id,
            data={
                "item": item,
                "instance_id": getattr(item, "instance_id", None),
                "equipment_id": getattr(getattr(item, "equipment", None), "equipment_id", None),
            },
        )
        return item

    def unequip(self, slot_id, index=0):
        slot_id = str(slot_id)
        if slot_id not in self._slots:
            raise KeyError(f"unknown equipment slot: {slot_id}")
        item = self._equipped[slot_id][int(index)]
        emit_hook(
            self.hooks,
            "rpg.equipment.before_unequip",
            source=slot_id,
            data={
                "item": item,
                "instance_id": getattr(item, "instance_id", None),
                "equipment_id": getattr(getattr(item, "equipment", None), "equipment_id", None),
            },
        )
        item = self._equipped[slot_id].pop(int(index))
        emit_hook(
            self.hooks,
            "rpg.equipment.after_unequip",
            source=slot_id,
            data={
                "item": item,
                "instance_id": getattr(item, "instance_id", None),
                "equipment_id": getattr(getattr(item, "equipment", None), "equipment_id", None),
            },
        )
        return item

    def slot_ids(self):
        """The loadout's slot ids, in a stable (sorted) order."""
        return tuple(sorted(self._slots))

    def equipped(self, slot_id=None):
        if slot_id is not None:
            return tuple(self._equipped[str(slot_id)])
        return tuple(item for key in sorted(self._equipped) for item in self._equipped[key])

    def working(self):
        """The equipped items that still work (a broken one stays equipped but gives nothing)."""
        return tuple(item for item in self.equipped() if not item.broken)

    def active_set_bonuses(self):
        """``(set_id, EquipmentSetBonus)`` pairs active for the equipped pieces."""
        equipped_ids = [item.equipment.equipment_id for item in self.working()]
        return tuple(
            (definition.set_id, bonus)
            for definition in sorted(self.set_definitions, key=lambda x: x.set_id)
            for bonus in definition.active_bonuses(equipped_ids)
        )

    def modifier_set(self):
        result = ModifierSet()
        for set_id, bonus in self.active_set_bonuses():
            for modifier in bonus.modifiers:
                result.add(
                    StatModifier(
                        f"set:{set_id}:{bonus.pieces}:{modifier.modifier_id}",
                        modifier.stat,
                        modifier.operation,
                        modifier.value,
                        priority=modifier.priority,
                        required_tags=modifier.required_tags,
                        blocked_tags=modifier.blocked_tags,
                    )
                )
        for item in self.working():
            for modifier in item.modifiers():
                # Modifier IDs are definition-local.  Scope them by stable
                # equipment instance so multiple copies of the same definition
                # contribute independently without colliding in ModifierSet.
                result.add(
                    StatModifier(
                        f"{item.instance_id}:{modifier.modifier_id}",
                        modifier.stat,
                        modifier.operation,
                        modifier.value,
                        priority=modifier.priority,
                        required_tags=modifier.required_tags,
                        blocked_tags=modifier.blocked_tags,
                    )
                )
        return result

    def abilities(self):
        result = []
        for item in self.working():
            result.extend(item.abilities())
        for _, bonus in self.active_set_bonuses():
            result.extend(bonus.granted_abilities)
        return tuple(dict.fromkeys(result))

    def triggers(self):
        result = []
        for item in self.working():
            result.extend(item.triggers())
        return tuple(result)

    def tags(self):
        result = set()
        for item in self.working():
            result.update(item.tags())
        for _, bonus in self.active_set_bonuses():
            result.update(bonus.tags)
        return tuple(sorted(result))


@dataclass(frozen=True, slots=True)
class ItemUseResult:
    used: bool
    item_id: str
    effect_results: tuple = ()
    reason: str | None = None


def use_inventory_item(
    inventory, item, target_stats, target_resources, target_tags, *, hooks=None
):
    """Use one item atomically with inventory consumption after all effects succeed."""
    if not isinstance(inventory, Inventory):
        raise TypeError("inventory must be Inventory")
    if not isinstance(item, ItemDefinition):
        raise TypeError("item must be ItemDefinition")
    emit_hook(
        hooks,
        "rpg.item.before_use",
        source=item.item_id,
        data={
            "item": item,
            "instance_id": getattr(item, "instance_id", None),
            "equipment_id": getattr(getattr(item, "equipment", None), "equipment_id", None),
        },
    )
    if inventory.count(item.item_id) < 1:
        result = ItemUseResult(False, item.item_id, (), "not_in_inventory")
        emit_hook(hooks, "rpg.item.use_failed", source=item.item_id, data={"result": result})
        return result
    # Stage gameplay state so a later failed effect cannot partially mutate target.
    stats = type(target_stats).from_data(target_stats.to_data())
    resources = type(target_resources).from_data(target_resources.to_data())
    tags = type(target_tags).from_data(target_tags.to_data())
    results = []
    for effect in item.use_effects:
        result = apply_effect(effect, stats, resources, tags)
        if not result.applied:
            failed = ItemUseResult(
                False, item.item_id, tuple(results) + (result,), "effect_rejected"
            )
            emit_hook(
                hooks,
                "rpg.item.use_failed",
                source=item.item_id,
                data={"result": failed},
            )
            return failed
        results.append(result)
    # Commit only after all effects succeeded, through public replacement seams.
    target_stats.replace_from(stats)
    target_resources.replace_from(resources)
    target_tags.replace_from(tags)
    inventory.remove(item.item_id, 1)
    final = ItemUseResult(True, item.item_id, tuple(results), None)
    emit_hook(hooks, "rpg.item.after_use", source=item.item_id, data={"result": final})
    return final
