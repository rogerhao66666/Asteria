from __future__ import annotations

from dataclasses import dataclass


def _id(value, label):
    value = str(value).strip()
    if not value:
        raise ValueError(f"{label} is required")
    return value


@dataclass(frozen=True, slots=True)
class BattleActionEntry:
    """Presentation description of one already-known project action.

    `action_id` is an opaque controller-owned identifier. `kind`, category and
    tags are presentation metadata only; this class never resolves or executes it.
    """

    action_id: str
    label: str
    category: str = "default"
    kind: str = "action"
    icon_asset_id: str | None = None
    detail: str = ""
    cost_text: str = ""
    enabled: bool = True
    disabled_reason: str = ""
    order: int = 0
    priority: int = 0
    tags: tuple[str, ...] = ()
    search_terms: tuple[str, ...] = ()

    def __init__(
        self,
        action_id,
        label=None,
        *,
        category="default",
        kind="action",
        icon_asset_id=None,
        detail="",
        cost_text="",
        enabled=True,
        disabled_reason="",
        order=0,
        priority=0,
        tags=(),
        search_terms=(),
    ):
        action_id = _id(action_id, "action_id")
        label = action_id if label is None else _id(label, "label")
        category = _id(category, "category")
        kind = _id(kind, "kind")
        tags = tuple(dict.fromkeys(str(x).strip() for x in tags if str(x).strip()))
        search_terms = tuple(dict.fromkeys(str(x).strip() for x in search_terms if str(x).strip()))
        object.__setattr__(self, "action_id", action_id)
        object.__setattr__(self, "label", label)
        object.__setattr__(self, "category", category)
        object.__setattr__(self, "kind", kind)
        object.__setattr__(
            self, "icon_asset_id", None if icon_asset_id is None else _id(icon_asset_id, "icon_asset_id")
        )
        object.__setattr__(self, "detail", str(detail))
        object.__setattr__(self, "cost_text", str(cost_text))
        object.__setattr__(self, "enabled", bool(enabled))
        object.__setattr__(self, "disabled_reason", str(disabled_reason))
        object.__setattr__(self, "order", int(order))
        object.__setattr__(self, "priority", int(priority))
        object.__setattr__(self, "tags", tags)
        object.__setattr__(self, "search_terms", search_terms)

    def matches(self, query):
        query = str(query).strip().casefold()
        if not query:
            return True
        haystack = (
            self.action_id,
            self.label,
            self.category,
            self.kind,
            self.detail,
            self.cost_text,
            *self.tags,
            *self.search_terms,
        )
        return any(query in str(x).casefold() for x in haystack)

    def to_data(self):
        return {
            "action_id": self.action_id,
            "label": self.label,
            "category": self.category,
            "kind": self.kind,
            "icon_asset_id": self.icon_asset_id,
            "detail": self.detail,
            "cost_text": self.cost_text,
            "enabled": self.enabled,
            "disabled_reason": self.disabled_reason,
            "order": self.order,
            "priority": self.priority,
            "tags": list(self.tags),
            "search_terms": list(self.search_terms),
        }

    @classmethod
    def from_data(cls, data):
        return cls(**data)


@dataclass(frozen=True, slots=True)
class BattleActionMenuPolicy:
    page_size: int = 6
    categories_visible: bool = True
    include_all_category: bool = True
    all_category_id: str = "all"
    sort_mode: str = "order"
    wrap_cursor: bool = True

    SCHEMA = "asteria.battle_action_menu_policy"
    VERSION = 1

    def __post_init__(self):
        if int(self.page_size) < 1:
            raise ValueError("page_size must be >= 1")
        _id(self.all_category_id, "all_category_id")
        if self.sort_mode not in {"order", "priority", "label"}:
            raise ValueError("unsupported action menu sort_mode")

    def to_data(self):
        return {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "page_size": self.page_size,
            "categories_visible": self.categories_visible,
            "include_all_category": self.include_all_category,
            "all_category_id": self.all_category_id,
            "sort_mode": self.sort_mode,
            "wrap_cursor": self.wrap_cursor,
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != cls.SCHEMA or data.get("version") != cls.VERSION:
            raise ValueError("unsupported battle action menu policy")
        return cls(**{k: v for k, v in data.items() if k not in {"schema", "version"}})


@dataclass(frozen=True, slots=True)
class BattleActionMenuView:
    categories: tuple[str, ...]
    active_category: str
    query: str
    entries: tuple[BattleActionEntry, ...]
    page: int
    page_count: int
    total_count: int
    cursor: int
    revision: int

    @property
    def selected(self):
        if not self.entries:
            return None
        return self.entries[min(max(self.cursor, 0), len(self.entries) - 1)]


class BattleActionMenuRuntime:
    """Browse/filter presentation state for arbitrary project actions.

    Availability is supplied by the canonical controller as `enabled` and
    `disabled_reason`. The menu never evaluates conditions, costs or targets and
    never executes an action.
    """

    SCHEMA = "asteria.battle_action_menu_runtime"
    VERSION = 1

    def __init__(self, policy=None):
        self.policy = policy or BattleActionMenuPolicy()
        if not isinstance(self.policy, BattleActionMenuPolicy):
            raise TypeError("policy must be BattleActionMenuPolicy")
        self._source = ()
        self.active_category = self.policy.all_category_id
        self.query = ""
        self.page = 0
        self.cursor = 0
        self.revision = 0
        self._view = BattleActionMenuView((), self.active_category, "", (), 0, 0, 0, 0, 0)

    @property
    def view(self):
        return self._view

    def _sort(self, values):
        if self.policy.sort_mode == "priority":
            return sorted(values, key=lambda x: (-x.priority, x.order, x.label.casefold(), x.action_id))
        if self.policy.sort_mode == "label":
            return sorted(values, key=lambda x: (x.label.casefold(), x.order, x.action_id))
        return sorted(values, key=lambda x: (x.order, -x.priority, x.label.casefold(), x.action_id))

    def _categories(self):
        values = []
        for entry in self._sort(self._source):
            if entry.category not in values:
                values.append(entry.category)
        if self.policy.include_all_category and values:
            return (self.policy.all_category_id, *values)
        return tuple(values)

    def _refresh(self):
        categories = self._categories()
        if self.active_category not in categories:
            self.active_category = categories[0] if categories else self.policy.all_category_id

        values = [
            x
            for x in self._source
            if (self.active_category == self.policy.all_category_id or x.category == self.active_category)
            and x.matches(self.query)
        ]
        values = self._sort(values)
        total = len(values)
        page_count = (total + self.policy.page_size - 1) // self.policy.page_size
        if page_count == 0:
            self.page = 0
        else:
            self.page = min(max(self.page, 0), page_count - 1)
        start = self.page * self.policy.page_size
        entries = tuple(values[start : start + self.policy.page_size])
        self.cursor = 0 if not entries else min(max(self.cursor, 0), len(entries) - 1)
        self.revision += 1
        self._view = BattleActionMenuView(
            categories,
            self.active_category,
            self.query,
            entries,
            self.page,
            page_count,
            total,
            self.cursor,
            self.revision,
        )
        return self._view

    def set_entries(self, entries):
        entries = tuple(x if isinstance(x, BattleActionEntry) else BattleActionEntry.from_data(x) for x in entries)
        if len({x.action_id for x in entries}) != len(entries):
            raise ValueError("duplicate action menu action_id")
        self._source = entries
        self.page = 0
        self.cursor = 0
        return self._refresh()

    def set_category(self, category):
        self.active_category = _id(category, "category")
        self.page = 0
        self.cursor = 0
        return self._refresh()

    def set_query(self, query):
        self.query = str(query)
        self.page = 0
        self.cursor = 0
        return self._refresh()

    def show(self, entries, category, index):
        """Entries, the active category and the selected row (``index`` within that category, any page) at once:
        for a controller that keeps its own cursor."""
        self._source = tuple(entries)
        self.active_category = _id(category, "category")
        self.query = ""
        index = max(0, int(index))
        self.page = index // self.policy.page_size
        self.cursor = index % self.policy.page_size
        return self._refresh()

    def set_page(self, page):
        self.page = int(page)
        self.cursor = 0
        return self._refresh()

    def move_cursor(self, delta):
        if not self._view.entries:
            return self._view
        count = len(self._view.entries)
        value = self.cursor + int(delta)
        if self.policy.wrap_cursor:
            value %= count
        else:
            value = min(max(value, 0), count - 1)
        self.cursor = value
        self.revision += 1
        self._view = BattleActionMenuView(
            self._view.categories,
            self._view.active_category,
            self._view.query,
            self._view.entries,
            self._view.page,
            self._view.page_count,
            self._view.total_count,
            self.cursor,
            self.revision,
        )
        return self._view

    def selected_action_id(self):
        selected = self._view.selected
        return None if selected is None else selected.action_id

    def snapshot(self):
        return {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "policy": self.policy.to_data(),
            "source": [x.to_data() for x in self._source],
            "active_category": self.active_category,
            "query": self.query,
            "page": self.page,
            "cursor": self.cursor,
            "revision": self.revision,
        }

    def restore(self, data):
        if data.get("schema") != self.SCHEMA or data.get("version") != self.VERSION:
            raise ValueError("unsupported battle action menu runtime snapshot")
        if BattleActionMenuPolicy.from_data(data["policy"]) != self.policy:
            raise ValueError("battle action menu policy mismatch")
        self._source = tuple(BattleActionEntry.from_data(x) for x in data.get("source", ()))
        self.active_category = str(data.get("active_category", self.policy.all_category_id))
        self.query = str(data.get("query", ""))
        self.page = int(data.get("page", 0))
        self.cursor = int(data.get("cursor", 0))
        revision = int(data.get("revision", 0))
        if revision < 0:
            raise ValueError("invalid battle action menu revision")
        self._refresh()
        self.revision = revision
        self._view = BattleActionMenuView(
            self._view.categories,
            self._view.active_category,
            self._view.query,
            self._view.entries,
            self._view.page,
            self._view.page_count,
            self._view.total_count,
            self._view.cursor,
            revision,
        )
        return self
