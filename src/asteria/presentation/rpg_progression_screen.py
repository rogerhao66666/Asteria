from __future__ import annotations

from dataclasses import dataclass

from asteria.rpg.progression_graph import ProgressionAllocationRuntime, ProgressionGraphDefinition


@dataclass(frozen=True, slots=True)
class ProgressionRequirementView:
    node_id: str
    minimum_rank: int


@dataclass(frozen=True, slots=True)
class ProgressionNodeView:
    graph_id: str
    node_id: str
    label: str
    rank: int
    max_rank: int
    tags: tuple[str, ...]
    prerequisites: tuple[ProgressionRequirementView, ...]
    any_prerequisites: tuple[ProgressionRequirementView, ...]
    exclusive_group: str | None
    next_costs: tuple[tuple[str, float], ...]
    allocatable: bool
    reasons: tuple[str, ...]
    selected: bool


@dataclass(frozen=True, slots=True)
class ProgressionGraphView:
    graph_id: str
    label: str
    tags: tuple[str, ...]
    node_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ProgressionScreenView:
    graphs: tuple[ProgressionGraphView, ...]
    nodes: tuple[ProgressionNodeView, ...]
    balances: tuple[tuple[str, float], ...]
    selected_graph_id: str | None
    selected_node_id: str | None
    query: str
    revision: int


@dataclass(frozen=True, slots=True)
class ProgressionScreenProfile:
    graph_labels: tuple[tuple[str, str], ...] = ()
    node_labels: tuple[tuple[str, str], ...] = ()
    visible_limits: tuple[tuple[str, int], ...] = ()
    SCHEMA = "asteria.progression_screen_profile"
    VERSION = 1

    def __init__(self, *, graph_labels=None, node_labels=None, visible_limits=None):
        object.__setattr__(
            self,
            "graph_labels",
            tuple(sorted((str(k), str(v)) for k, v in dict(graph_labels or {}).items())),
        )
        object.__setattr__(
            self,
            "node_labels",
            tuple(sorted((str(k), str(v)) for k, v in dict(node_labels or {}).items())),
        )
        limits = []
        for k, v in dict(visible_limits or {}).items():
            v = int(v)
            if v < 1:
                raise ValueError("visible limit must be >= 1")
            limits.append((str(k), v))
        object.__setattr__(self, "visible_limits", tuple(sorted(limits)))

    def graph_label(self, key):
        key = str(key)
        return dict(self.graph_labels).get(key, key)

    def node_label(self, key):
        key = str(key)
        return dict(self.node_labels).get(key, key)

    def visible_limit(self, key):
        return dict(self.visible_limits).get(str(key))

    def to_data(self):
        return {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "graph_labels": dict(self.graph_labels),
            "node_labels": dict(self.node_labels),
            "visible_limits": dict(self.visible_limits),
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != cls.SCHEMA or data.get("version") != cls.VERSION:
            raise ValueError("unsupported progression screen profile")
        return cls(
            graph_labels=data.get("graph_labels", {}),
            node_labels=data.get("node_labels", {}),
            visible_limits=data.get("visible_limits", {}),
        )


class ProgressionScreenRuntime:
    SCHEMA = "asteria.progression_screen_runtime"
    VERSION = 1

    def __init__(self, profile=None):
        self.profile = profile or ProgressionScreenProfile()
        if not isinstance(self.profile, ProgressionScreenProfile):
            raise TypeError("profile must be ProgressionScreenProfile")
        self.selected_graph_id = None
        self.selected_node_id = None
        self.query = ""
        self.revision = 0
        self._view = None

    @property
    def view(self):
        return self._view

    def project(self, allocation_runtime, graphs=None):
        if not isinstance(allocation_runtime, ProgressionAllocationRuntime):
            raise TypeError("allocation_runtime must be ProgressionAllocationRuntime")
        graph_defs = (
            tuple(allocation_runtime.definitions.values()) if graphs is None else tuple(graphs)
        )
        if any(not isinstance(x, ProgressionGraphDefinition) for x in graph_defs):
            raise TypeError("graphs must contain ProgressionGraphDefinition values")

        graph_ids = {x.graph_id for x in graph_defs}
        if self.selected_graph_id not in graph_ids:
            self.selected_graph_id = graph_defs[0].graph_id if graph_defs else None

        query = self.query.casefold().strip()
        graph_views = []
        node_views = []
        for graph in graph_defs:
            node_ids = []
            limit = self.profile.visible_limit(graph.graph_id)
            visible_count = 0
            for node in graph.nodes:
                label = self.profile.node_label(node.node_id)
                haystack = " ".join((node.node_id, label, graph.graph_id, *node.tags)).casefold()
                if query and query not in haystack:
                    continue
                rank = allocation_runtime.rank(graph.graph_id, node.node_id)
                if rank >= node.max_rank:
                    allocatable = False
                    reasons = (f"maximum rank is {node.max_rank}",)
                    next_costs = ()
                else:
                    preview = allocation_runtime.preview_allocate(graph.graph_id, node.node_id, 1)
                    allocatable = preview.allowed
                    reasons = tuple(preview.reasons)
                    next_costs = tuple(
                        sorted((str(k), float(v)) for k, v in preview.costs.items())
                    )
                if limit is None or visible_count < limit:
                    node_ids.append(node.node_id)
                    visible_count += 1
                node_views.append(
                    ProgressionNodeView(
                        graph_id=graph.graph_id,
                        node_id=node.node_id,
                        label=label,
                        rank=rank,
                        max_rank=node.max_rank,
                        tags=tuple(node.tags),
                        prerequisites=tuple(
                            ProgressionRequirementView(x.node_id, x.minimum_rank)
                            for x in node.prerequisites
                        ),
                        any_prerequisites=tuple(
                            ProgressionRequirementView(x.node_id, x.minimum_rank)
                            for x in node.any_prerequisites
                        ),
                        exclusive_group=node.exclusive_group,
                        next_costs=next_costs,
                        allocatable=allocatable,
                        reasons=reasons,
                        selected=(
                            node.node_id == self.selected_node_id
                            and graph.graph_id == self.selected_graph_id
                        ),
                    )
                )
            graph_views.append(
                ProgressionGraphView(
                    graph.graph_id,
                    self.profile.graph_label(graph.graph_id),
                    tuple(graph.tags),
                    tuple(node_ids),
                )
            )

        valid_nodes = {x.node_id for x in node_views if x.graph_id == self.selected_graph_id}
        if self.selected_node_id not in valid_nodes:
            self.selected_node_id = next(
                (x.node_id for x in node_views if x.graph_id == self.selected_graph_id), None
            )

        self.revision += 1
        self._view = ProgressionScreenView(
            tuple(graph_views),
            tuple(node_views),
            tuple(sorted((str(k), float(v)) for k, v in allocation_runtime.balances.items())),
            self.selected_graph_id,
            self.selected_node_id,
            self.query,
            self.revision,
        )
        return self._view

    def select_graph(self, graph_id):
        if self._view is None:
            raise RuntimeError("progression screen has not been projected")
        graph_id = str(graph_id)
        if graph_id not in {x.graph_id for x in self._view.graphs}:
            raise KeyError(f"unknown progression graph: {graph_id}")
        self.selected_graph_id = graph_id
        self.selected_node_id = None
        return graph_id

    def select_node(self, node_id):
        if self._view is None:
            raise RuntimeError("progression screen has not been projected")
        node_id = str(node_id)
        if node_id not in {
            x.node_id for x in self._view.nodes if x.graph_id == self.selected_graph_id
        }:
            raise KeyError(f"unknown progression node: {node_id}")
        self.selected_node_id = node_id
        return node_id

    def set_query(self, query):
        self.query = str(query)
        return self.query

    def snapshot(self):
        return {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "profile": self.profile.to_data(),
            "selected_graph_id": self.selected_graph_id,
            "selected_node_id": self.selected_node_id,
            "query": self.query,
            "revision": self.revision,
        }

    def restore(self, data):
        if data.get("schema") != self.SCHEMA or data.get("version") != self.VERSION:
            raise ValueError("unsupported progression screen snapshot")
        if ProgressionScreenProfile.from_data(data["profile"]) != self.profile:
            raise ValueError("progression screen profile mismatch")
        self.selected_graph_id = data.get("selected_graph_id")
        self.selected_node_id = data.get("selected_node_id")
        self.query = str(data.get("query", ""))
        self.revision = int(data["revision"])
        self._view = None
        return self
