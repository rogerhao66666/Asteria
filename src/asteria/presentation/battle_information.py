from __future__ import annotations

from dataclasses import dataclass


def _id(value, name):
    value=str(value).strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value


@dataclass(frozen=True, slots=True)
class BattleInformationRule:
    info_id: str
    role: str
    priority: int = 0
    visibility: str = "persistent"
    compact: bool = False
    group: str = "default"

    VISIBILITY=("persistent","contextual","focused","compact","hidden")

    def __post_init__(self):
        _id(self.info_id,"info_id")
        _id(self.role,"role")
        _id(self.group,"group")
        if self.visibility not in self.VISIBILITY:
            raise ValueError("unsupported information visibility")


@dataclass(frozen=True, slots=True)
class BattleInformationItem:
    info_id: str
    role: str
    label: str
    value: object = None
    priority: int = 0
    visibility: str = "persistent"
    compact: bool = False
    group: str = "default"
    member_id: str | None = None
    contextual: bool = False

    def __post_init__(self):
        _id(self.info_id,"info_id")
        _id(self.role,"role")
        _id(self.label,"label")


@dataclass(frozen=True, slots=True)
class BattleInformationView:
    persistent: tuple[BattleInformationItem, ...]
    compact: tuple[BattleInformationItem, ...]
    focused: tuple[BattleInformationItem, ...]
    contextual: tuple[BattleInformationItem, ...]
    overflow: tuple[BattleInformationItem, ...]
    hidden_count: int
    revision: int


@dataclass(frozen=True, slots=True)
class BattleInformationPolicy:
    persistent_limit: int = 8
    compact_limit: int = 8
    focused_limit: int = 12
    contextual_limit: int = 8

    def __post_init__(self):
        for name in ("persistent_limit","compact_limit","focused_limit","contextual_limit"):
            if int(getattr(self,name)) < 0:
                raise ValueError(f"{name} must be >= 0")


class BattleInformationRuntime:
    """Presentation-only information hierarchy / clutter-control resolver.

    Canonical gameplay may expose arbitrary resources, states, combatants and
    timeline data. This runtime decides only how much of already-known
    information should be simultaneously visible.
    """

    def __init__(self, policy=None):
        self.policy=policy or BattleInformationPolicy()
        self.revision=0
        self._view=BattleInformationView((),(),(),(),(),0,0)

    @property
    def view(self):
        return self._view

    @staticmethod
    def _sort(values):
        return sorted(values,key=lambda x:(-x.priority,x.group,x.label.casefold(),x.info_id))

    def resolve(self, items, *, focus_member_id=None, active_contexts=()):
        values=tuple(items)
        active_contexts={str(x) for x in active_contexts}
        focus=None if focus_member_id is None else str(focus_member_id)
        persistent=[]; compact=[]; focused=[]; contextual=[]; overflow=[]
        hidden=0

        for item in values:
            if not isinstance(item,BattleInformationItem):
                item=BattleInformationItem(**item)
            if item.visibility=="hidden":
                hidden+=1
                continue
            if item.visibility=="focused":
                if focus is not None and item.member_id==focus:
                    focused.append(item)
                else:
                    overflow.append(item)
                continue
            if item.visibility=="contextual":
                if item.contextual or item.group in active_contexts:
                    contextual.append(item)
                else:
                    # contextual information is dormant, not clutter/overflow
                    hidden+=1
                continue
            if item.visibility=="compact" or item.compact:
                compact.append(item)
            else:
                persistent.append(item)

        def cap(values, limit):
            ordered=self._sort(values)
            return ordered[:limit], ordered[limit:]

        persistent,p_over=cap(persistent,self.policy.persistent_limit)
        compact,c_over=cap(compact,self.policy.compact_limit)
        focused,f_over=cap(focused,self.policy.focused_limit)
        contextual,x_over=cap(contextual,self.policy.contextual_limit)
        overflow=self._sort((*overflow,*p_over,*c_over,*f_over,*x_over))

        self.revision+=1
        self._view=BattleInformationView(
            tuple(persistent),tuple(compact),tuple(focused),tuple(contextual),
            tuple(overflow),hidden,self.revision,
        )
        return self._view


@dataclass(frozen=True, slots=True)
class BattleRosterSummary:
    primary_member_ids: tuple[str, ...]
    compact_member_ids: tuple[str, ...]
    overflow_member_ids: tuple[str, ...]
    focus_member_id: str | None


class BattleRosterDensityPolicy:
    """Keeps large rosters legible without imposing gameplay party limits."""

    def __init__(self, *, primary_limit=4, compact_limit=4):
        if int(primary_limit)<1 or int(compact_limit)<0:
            raise ValueError("invalid roster density limits")
        self.primary_limit=int(primary_limit)
        self.compact_limit=int(compact_limit)

    def resolve(self, member_ids, *, focus_member_id=None):
        ids=tuple(str(x) for x in member_ids)
        if len(ids)!=len(set(ids)):
            raise ValueError("duplicate roster member")
        focus=None if focus_member_id is None else str(focus_member_id)
        primary=list(ids[:self.primary_limit])
        if focus in ids and focus not in primary and primary:
            primary[-1]=focus
        used=set(primary)
        remaining=[x for x in ids if x not in used]
        compact=remaining[:self.compact_limit]
        overflow=remaining[self.compact_limit:]
        return BattleRosterSummary(tuple(primary),tuple(compact),tuple(overflow),focus)
