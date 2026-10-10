from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


def _id(value, label):
    value = str(value).strip()
    if not value:
        raise ValueError(f"{label} is required")
    return value


def _finite(value, label):
    value = float(value)
    if not isfinite(value):
        raise ValueError(f"{label} must be finite")
    return value


@dataclass(frozen=True, slots=True)
class BattleHudResourceStyle:
    """Project-owned presentation policy for one generic battle resource.

    `presentation` is visual semantics only. It never changes resource gameplay.
    Supported built-in roles are intentionally generic: bar, segmented_bar, pips,
    number, icon_stack, ring, action_gauge, timeline, contextual, and hidden.
    Projects may also provide a custom role string for their own UI adapter.
    """

    resource_id: str
    label: str
    order: int = 0
    icon_asset_id: str | None = None
    visible: bool = True
    presentation: str = "bar"
    segments: int = 0
    group: str = "primary"
    priority: int = 0
    show_label: bool = True
    show_value: bool = True
    compact: bool = False

    BUILTIN_PRESENTATIONS = frozenset({
        "bar", "segmented_bar", "pips", "number", "icon_stack", "ring",
        "action_gauge", "timeline", "contextual", "hidden",
    })

    def __init__(
        self, resource_id, label=None, *, order=0, icon_asset_id=None, visible=True,
        presentation="bar", segments=0, group="primary", priority=0,
        show_label=True, show_value=True, compact=False,
    ):
        resource_id = _id(resource_id, "resource_id")
        presentation = _id(presentation, "presentation").lower()
        segments = int(segments)
        if segments < 0:
            raise ValueError("segments must be >= 0")
        group = _id(group, "group")
        object.__setattr__(self, "resource_id", resource_id)
        object.__setattr__(self, "label", resource_id.upper() if label is None else _id(label, "label"))
        object.__setattr__(self, "order", int(order))
        object.__setattr__(self, "icon_asset_id", None if icon_asset_id is None else _id(icon_asset_id, "icon_asset_id"))
        object.__setattr__(self, "visible", bool(visible) and presentation != "hidden")
        object.__setattr__(self, "presentation", presentation)
        object.__setattr__(self, "segments", segments)
        object.__setattr__(self, "group", group)
        object.__setattr__(self, "priority", int(priority))
        object.__setattr__(self, "show_label", bool(show_label))
        object.__setattr__(self, "show_value", bool(show_value))
        object.__setattr__(self, "compact", bool(compact))

    def to_data(self):
        return {
            "resource_id": self.resource_id,
            "label": self.label,
            "order": self.order,
            "icon_asset_id": self.icon_asset_id,
            "visible": self.visible,
            "presentation": self.presentation,
            "segments": self.segments,
            "group": self.group,
            "priority": self.priority,
            "show_label": self.show_label,
            "show_value": self.show_value,
            "compact": self.compact,
        }

    @classmethod
    def from_data(cls, data):
        return cls(**data)


@dataclass(frozen=True, slots=True)
class BattleHudStatusStyle:
    state_id: str
    icon_asset_id: str
    label: str | None = None
    order: int = 0

    def __init__(self, state_id, icon_asset_id, *, label=None, order=0):
        state_id = _id(state_id, "state_id")
        object.__setattr__(self, "state_id", state_id)
        object.__setattr__(self, "icon_asset_id", _id(icon_asset_id, "icon_asset_id"))
        object.__setattr__(self, "label", state_id if label is None else _id(label, "label"))
        object.__setattr__(self, "order", int(order))

    def to_data(self):
        return {
            "state_id": self.state_id,
            "icon_asset_id": self.icon_asset_id,
            "label": self.label,
            "order": self.order,
        }

    @classmethod
    def from_data(cls, data):
        return cls(**data)


@dataclass(frozen=True, slots=True)
class BattleHudProfile:
    resources: tuple[BattleHudResourceStyle, ...]
    statuses: tuple[BattleHudStatusStyle, ...]
    show_unmapped_resources: bool = True
    show_unmapped_statuses: bool = False

    SCHEMA = "asteria.battle_hud_profile"
    VERSION = 1

    def __init__(self, resources=(), statuses=(), *, show_unmapped_resources=True, show_unmapped_statuses=False):
        resources = tuple(x if isinstance(x, BattleHudResourceStyle) else BattleHudResourceStyle.from_data(x) for x in resources)
        statuses = tuple(x if isinstance(x, BattleHudStatusStyle) else BattleHudStatusStyle.from_data(x) for x in statuses)
        if len({x.resource_id for x in resources}) != len(resources):
            raise ValueError("duplicate HUD resource style")
        if len({x.state_id for x in statuses}) != len(statuses):
            raise ValueError("duplicate HUD status style")
        object.__setattr__(self, "resources", resources)
        object.__setattr__(self, "statuses", statuses)
        object.__setattr__(self, "show_unmapped_resources", bool(show_unmapped_resources))
        object.__setattr__(self, "show_unmapped_statuses", bool(show_unmapped_statuses))

    @classmethod
    def default(cls):
        return cls((
            BattleHudResourceStyle("hp", "HP", order=0),
            BattleHudResourceStyle("mp", "MP", order=10),
        ), show_unmapped_resources=True)

    def resource_style(self, resource_id):
        resource_id = str(resource_id)
        return next((x for x in self.resources if x.resource_id == resource_id), None)

    def status_style(self, state_id):
        state_id = str(state_id)
        return next((x for x in self.statuses if x.state_id == state_id), None)

    def to_data(self):
        return {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "resources": [x.to_data() for x in self.resources],
            "statuses": [x.to_data() for x in self.statuses],
            "show_unmapped_resources": self.show_unmapped_resources,
            "show_unmapped_statuses": self.show_unmapped_statuses,
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != cls.SCHEMA or data.get("version") != cls.VERSION:
            raise ValueError("unsupported battle HUD profile")
        return cls(
            data.get("resources", ()), data.get("statuses", ()),
            show_unmapped_resources=data.get("show_unmapped_resources", True),
            show_unmapped_statuses=data.get("show_unmapped_statuses", False),
        )


@dataclass(frozen=True, slots=True)
class BattleHudGauge:
    resource_id: str
    label: str
    current: float
    minimum: float
    maximum: float
    overflow: float
    normalized: float
    full: bool
    icon_asset_id: str | None
    order: int
    presentation: str = "bar"
    segments: int = 0
    group: str = "primary"
    priority: int = 0
    show_label: bool = True
    show_value: bool = True
    compact: bool = False


@dataclass(frozen=True, slots=True)
class BattleHudStatusIcon:
    state_id: str
    label: str
    icon_asset_id: str | None
    stacks: int
    remaining: float
    source_id: str | None
    order: int


@dataclass(frozen=True, slots=True)
class BattleHudMember:
    member_id: str
    gauges: tuple[BattleHudGauge, ...]
    statuses: tuple[BattleHudStatusIcon, ...]


class _PoolValue:
    """Adapts a gameplay ResourcePool entry to the battle-resource value shape."""

    def __init__(self, raw):
        self.current = float(raw["current"])
        self.minimum = float(raw.get("minimum", 0.0))
        self.maximum = float(raw["maximum"])
        self.overflow = 0.0
        span = self.maximum - self.minimum
        self.normalized = 0.0 if span <= 0 else max(0.0, min(1.0, (self.current - self.minimum) / span))
        self.full = self.current >= self.maximum


class BattleHudRuntime:
    """Read-only battle HUD projection over canonical resource/state runtimes.

    No gameplay mutation, target validation, resource math, state application, or
    semantic interpretation occurs here. HP/MP are merely default profile entries;
    projects can expose any resource IDs and state icon mappings they choose.
    """

    SCHEMA = "asteria.battle_hud_runtime"
    VERSION = 1

    def __init__(self, profile=None):
        self.profile = profile or BattleHudProfile.default()
        if not isinstance(self.profile, BattleHudProfile):
            raise TypeError("profile must be BattleHudProfile")
        self._members: dict[str, BattleHudMember] = {}
        self.revision = 0

    @property
    def members(self):
        return tuple(self._members[k] for k in sorted(self._members))

    def member(self, member_id):
        return self._members[str(member_id)]

    def _gauge(self, resource_id, value):
        style = self.profile.resource_style(resource_id)
        if style is None:
            if not self.profile.show_unmapped_resources:
                return None
            style = BattleHudResourceStyle(resource_id, str(resource_id).upper(), order=1000)
        if not style.visible:
            return None
        return BattleHudGauge(
            str(resource_id), style.label, _finite(value.current, "current"),
            _finite(value.minimum, "minimum"), _finite(value.maximum, "maximum"),
            _finite(value.overflow, "overflow"), _finite(value.normalized, "normalized"),
            bool(value.full), style.icon_asset_id, style.order,
            style.presentation, style.segments, style.group, style.priority,
            style.show_label, style.show_value, style.compact,
        )

    def _status(self, active):
        style = self.profile.status_style(active.state_id)
        if style is None:
            if not self.profile.show_unmapped_statuses:
                return None
            style = BattleHudStatusStyle(active.state_id, "status.unmapped", order=1000)
        return BattleHudStatusIcon(
            str(active.state_id), style.label or str(active.state_id), style.icon_asset_id,
            int(active.stacks), _finite(active.remaining, "remaining"),
            None if active.source_id is None else str(active.source_id), style.order,
        )

    def sync_member(self, member_id, battle_resources, subject):
        """Mirror one canonical member without mutating either source runtime."""
        member_id = _id(member_id, "member_id")
        values = battle_resources.values.get(member_id, {})
        gauges = [self._gauge(resource_id, values[resource_id]) for resource_id in sorted(values)]
        # Gameplay resources (HP, SP, ...) appear only when the profile maps them explicitly.
        pool = getattr(subject, "resources", None)
        if pool is not None:
            for resource_id, raw in sorted(pool.to_data()["values"].items()):
                if resource_id not in values and self.profile.resource_style(resource_id) is not None:
                    gauges.append(self._gauge(resource_id, _PoolValue(raw)))
        gauges = [x for x in gauges if x is not None]
        gauges.sort(key=lambda x: (x.order, x.resource_id))

        state_runtime = getattr(subject, "states", None)
        active_states = () if state_runtime is None else state_runtime.active_states()
        statuses = [self._status(active) for active in active_states]
        statuses = [x for x in statuses if x is not None]
        statuses.sort(key=lambda x: (x.order, x.state_id))

        view = BattleHudMember(member_id, tuple(gauges), tuple(statuses))
        self._members[member_id] = view
        self.revision += 1
        return view

    def sync_battle(self, battle_runtime):
        """Mirror all canonical battle members in deterministic member-id order."""
        resources = battle_runtime.battle_resources
        present = set()
        for member_id in sorted(resources.members):
            member = resources.members[member_id]
            self.sync_member(member_id, resources, member.subject)
            present.add(member_id)
        for member_id in tuple(self._members):
            if member_id not in present:
                del self._members[member_id]
                self.revision += 1
        return self.members

    def snapshot(self):
        return {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "profile": self.profile.to_data(),
            "revision": self.revision,
            "members": [
                {
                    "member_id": member.member_id,
                    "gauges": [
                        {
                            "resource_id": x.resource_id, "label": x.label, "current": x.current,
                            "minimum": x.minimum, "maximum": x.maximum, "overflow": x.overflow,
                            "normalized": x.normalized, "full": x.full,
                            "icon_asset_id": x.icon_asset_id, "order": x.order,
                            "presentation": x.presentation, "segments": x.segments,
                            "group": x.group, "priority": x.priority,
                            "show_label": x.show_label, "show_value": x.show_value,
                            "compact": x.compact,
                        } for x in member.gauges
                    ],
                    "statuses": [
                        {
                            "state_id": x.state_id, "label": x.label, "icon_asset_id": x.icon_asset_id,
                            "stacks": x.stacks, "remaining": x.remaining, "source_id": x.source_id,
                            "order": x.order,
                        } for x in member.statuses
                    ],
                } for member in self.members
            ],
        }

    def restore(self, data):
        if data.get("schema") != self.SCHEMA or data.get("version") != self.VERSION:
            raise ValueError("unsupported battle HUD runtime snapshot")
        profile = BattleHudProfile.from_data(data["profile"])
        if profile != self.profile:
            raise ValueError("battle HUD profile mismatch")
        revision = int(data["revision"])
        if revision < 0:
            raise ValueError("invalid battle HUD revision")
        members = {}
        for raw in data.get("members", ()):
            member_id = _id(raw["member_id"], "member_id")
            if member_id in members:
                raise ValueError("duplicate battle HUD member")
            gauges = tuple(BattleHudGauge(**x) for x in raw.get("gauges", ()))
            statuses = tuple(BattleHudStatusIcon(**x) for x in raw.get("statuses", ()))
            members[member_id] = BattleHudMember(member_id, gauges, statuses)
        self._members = members
        self.revision = revision
