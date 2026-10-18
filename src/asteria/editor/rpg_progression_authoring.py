from __future__ import annotations

from dataclasses import dataclass

from asteria.gameplay import AbilityDefinition
from asteria.rpg import (
    AbilityEvolutionRule,
    PassiveDefinition,
    ProgressionGraphDefinition,
    ProgressionMilestone,
    ProgressionNodeDefinition,
    ProgressionTrackDefinition,
)


class RpgProgressionAuthoringError(RuntimeError):
    pass


@dataclass(slots=True)
class _MappingCommand:
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


@dataclass(slots=True)
class _AbilityRegistryCommand:
    registry: object
    key: str
    new_value: object | None
    old_value: object | None
    description: str

    @property
    def label(self):
        return self.description

    def redo(self):
        store = self.registry._definitions
        if self.new_value is None:
            store.pop(self.key, None)
        else:
            store[self.key] = self.new_value

    def undo(self):
        store = self.registry._definitions
        if self.old_value is None:
            store.pop(self.key, None)
        else:
            store[self.key] = self.old_value


@dataclass(frozen=True, slots=True)
class ProgressionEditorSection:
    section_id: str
    label: str
    mode: str
    summary_fields: tuple[str, ...]
    detail_groups: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ProgressionEditorInformationArchitecture:
    """Presentation contract: complete capability without one-screen sprawl."""

    sections: tuple[ProgressionEditorSection, ...] = (
        ProgressionEditorSection(
            "abilities",
            "Abilities",
            "list_detail",
            ("ability_id", "tags"),
            ("Targeting", "Costs", "Conditions", "Effects", "Tags"),
        ),
        ProgressionEditorSection(
            "passives",
            "Passives",
            "list_detail",
            ("passive_id", "display_name", "tags"),
            ("Identity", "Stat Modifiers", "Granted Abilities", "Triggers"),
        ),
        ProgressionEditorSection(
            "tracks",
            "Progression Tracks",
            "list_detail",
            ("track_id", "display_name", "milestone_count"),
            ("Milestones", "Rewards"),
        ),
        ProgressionEditorSection(
            "graphs",
            "Skill Trees",
            "graph_detail",
            ("graph_id", "display_name", "node_count"),
            ("Graph", "Selected Node", "Ranks & Costs", "Prerequisites", "Rewards", "Tags"),
        ),
        ProgressionEditorSection(
            "evolutions",
            "Ability Evolutions",
            "list_detail",
            ("rule_id", "source_ability_id", "result_ability_id"),
            ("Condition", "Priority", "Source Retention"),
        ),
    )
    primary_navigation: str = "category_sidebar"
    browser_pattern: str = "search_filter_list"
    inspector_pattern: str = "contextual_detail"
    progressive_disclosure: bool = True
    graph_focus: bool = True
    show_all_details_simultaneously: bool = False

    def section(self, section_id):
        return next((x for x in self.sections if x.section_id == str(section_id)), None)


class RpgProgressionAuthoringController:
    """Complete authoring facade for abilities, passives and progression.

    All edits replace canonical immutable definitions atomically. The UI may
    organize this through list/detail and graph/detail views without exposing
    every field simultaneously.
    """

    information_architecture = ProgressionEditorInformationArchitecture()

    def __init__(self, document):
        self.document = document

    @property
    def project(self):
        if self.document.project is None:
            raise RpgProgressionAuthoringError("project required")
        return self.document.project

    @property
    def database(self):
        return self.project.rpg_database

    @property
    def abilities(self):
        return self.project.gameplay_library.abilities

    def _execute(self, command):
        self.document.execute(command)
        return command

    def _ability_ids(self):
        return set(self.abilities.ids())

    def _check_abilities(self, values):
        result = tuple(dict.fromkeys(str(x).strip() for x in values))
        missing = [x for x in result if x not in self._ability_ids()]
        if missing:
            raise RpgProgressionAuthoringError("unknown abilities: " + ", ".join(sorted(missing)))
        return result

    def _check_passives(self, values):
        result = tuple(dict.fromkeys(str(x).strip() for x in values))
        missing = [x for x in result if x not in self.database.passives]
        if missing:
            raise RpgProgressionAuthoringError("unknown passives: " + ", ".join(sorted(missing)))
        return result

    # Ability definitions remain owned by GameplayLibrary.
    def create_ability(self, definition):
        if not isinstance(definition, AbilityDefinition):
            if isinstance(definition, dict):
                definition = AbilityDefinition.from_data(definition)
            else:
                raise TypeError("definition must be AbilityDefinition or data")
        key = definition.ability_id
        if self.abilities.get(key) is not None:
            raise RpgProgressionAuthoringError(f"duplicate ability: {key}")
        self._execute(
            _AbilityRegistryCommand(self.abilities, key, definition, None, f"Add Ability {key}")
        )
        return definition

    def edit_ability(self, ability_id, definition):
        key = str(ability_id)
        old = self.abilities.get(key)
        if old is None:
            raise RpgProgressionAuthoringError(f"unknown ability: {key}")
        if isinstance(definition, dict):
            definition = AbilityDefinition.from_data(definition)
        if not isinstance(definition, AbilityDefinition):
            raise TypeError("definition must be AbilityDefinition or data")
        if definition.ability_id != key:
            raise RpgProgressionAuthoringError("ability id cannot change during edit")
        self._execute(
            _AbilityRegistryCommand(self.abilities, key, definition, old, f"Edit Ability {key}")
        )
        return definition

    def delete_ability(self, ability_id):
        key = str(ability_id)
        old = self.abilities.get(key)
        if old is None:
            raise RpgProgressionAuthoringError(f"unknown ability: {key}")
        refs = []
        for actor in self.database.actors.values():
            if key in actor.abilities:
                refs.append(f"actor:{actor.actor_id}")
        for cls in self.database.classes.values():
            if key in cls.granted_abilities:
                refs.append(f"class:{cls.class_id}")
        for passive in self.database.passives.values():
            if key in passive.granted_abilities:
                refs.append(f"passive:{passive.passive_id}")
        for rule in self.database.ability_evolutions.values():
            if key in (rule.source_ability_id, rule.result_ability_id):
                refs.append(f"evolution:{rule.rule_id}")
        for graph in self.database.progression_graphs.values():
            for node in graph.nodes:
                for reward in node.rewards:
                    if key in reward.granted_abilities:
                        refs.append(f"graph:{graph.graph_id}:{node.node_id}")
        if refs:
            raise RpgProgressionAuthoringError(
                f"ability {key} is referenced by " + ", ".join(sorted(refs))
            )
        self._execute(
            _AbilityRegistryCommand(self.abilities, key, None, old, f"Delete Ability {key}")
        )

    def create_passive(
        self,
        passive_id,
        display_name=None,
        *,
        tags=(),
        modifiers=(),
        granted_abilities=(),
        triggers=(),
    ):
        key = str(passive_id).strip()
        if key in self.database.passives:
            raise RpgProgressionAuthoringError(f"duplicate passive: {key}")
        value = PassiveDefinition(
            key,
            display_name,
            tags=tags,
            modifiers=modifiers,
            granted_abilities=self._check_abilities(granted_abilities),
            triggers=triggers,
        )
        self._execute(
            _MappingCommand(self.database.passives, key, value, None, f"Add Passive {key}")
        )
        return value

    def edit_passive(
        self,
        passive_id,
        *,
        display_name=None,
        tags=None,
        modifiers=None,
        granted_abilities=None,
        triggers=None,
    ):
        key = str(passive_id)
        old = self.database.passives.get(key)
        if old is None:
            raise RpgProgressionAuthoringError(f"unknown passive: {key}")
        value = PassiveDefinition(
            key,
            old.display_name if display_name is None else display_name,
            tags=old.tags if tags is None else tags,
            modifiers=old.modifiers if modifiers is None else modifiers,
            granted_abilities=(
                old.granted_abilities
                if granted_abilities is None
                else self._check_abilities(granted_abilities)
            ),
            triggers=old.triggers if triggers is None else triggers,
        )
        self._execute(
            _MappingCommand(self.database.passives, key, value, old, f"Edit Passive {key}")
        )
        return value

    def delete_passive(self, passive_id):
        key = str(passive_id)
        old = self.database.passives.get(key)
        if old is None:
            raise RpgProgressionAuthoringError(f"unknown passive: {key}")
        refs = []
        for graph in self.database.progression_graphs.values():
            for node in graph.nodes:
                if any(key in r.unlocked_passives for r in node.rewards):
                    refs.append(f"{graph.graph_id}:{node.node_id}")
        if refs:
            raise RpgProgressionAuthoringError(
                f"passive {key} is referenced by progression nodes: " + ", ".join(sorted(refs))
            )
        self._execute(
            _MappingCommand(self.database.passives, key, None, old, f"Delete Passive {key}")
        )

    def create_track(self, track_id, display_name=None, *, milestones):
        key = str(track_id).strip()
        if key in self.database.progression_tracks:
            raise RpgProgressionAuthoringError(f"duplicate progression track: {key}")
        ms = tuple(
            x if isinstance(x, ProgressionMilestone) else ProgressionMilestone.from_data(x)
            for x in milestones
        )
        for m in ms:
            self._check_abilities(m.granted_abilities)
        value = ProgressionTrackDefinition(key, display_name, milestones=ms)
        self._execute(
            _MappingCommand(
                self.database.progression_tracks, key, value, None, f"Add Progression Track {key}"
            )
        )
        return value

    def edit_track(self, track_id, *, display_name=None, milestones=None):
        key = str(track_id)
        old = self.database.progression_tracks.get(key)
        if old is None:
            raise RpgProgressionAuthoringError(f"unknown progression track: {key}")
        ms = (
            old.milestones
            if milestones is None
            else tuple(
                x if isinstance(x, ProgressionMilestone) else ProgressionMilestone.from_data(x)
                for x in milestones
            )
        )
        for m in ms:
            self._check_abilities(m.granted_abilities)
        value = ProgressionTrackDefinition(
            key, old.display_name if display_name is None else display_name, milestones=ms
        )
        self._execute(
            _MappingCommand(
                self.database.progression_tracks, key, value, old, f"Edit Progression Track {key}"
            )
        )
        return value

    def delete_track(self, track_id):
        key = str(track_id)
        old = self.database.progression_tracks.get(key)
        if old is None:
            raise RpgProgressionAuthoringError(f"unknown progression track: {key}")
        refs = []
        for actor in self.database.actors.values():
            for a in actor.class_assignments:
                if key in a.progression_track_ids:
                    refs.append(f"actor:{actor.actor_id}:{a.assignment_id}")
        for rule in self.database.ability_evolutions.values():
            if rule.progression_track_id == key:
                refs.append(f"evolution:{rule.rule_id}")
        if refs:
            raise RpgProgressionAuthoringError(
                f"progression track {key} is referenced by " + ", ".join(sorted(refs))
            )
        self._execute(
            _MappingCommand(
                self.database.progression_tracks, key, None, old, f"Delete Progression Track {key}"
            )
        )

    def _normalize_node(self, node):
        if isinstance(node, dict):
            node = ProgressionNodeDefinition.from_data(node)
        if not isinstance(node, ProgressionNodeDefinition):
            raise TypeError("nodes must be ProgressionNodeDefinition values or data")
        for reward in node.rewards:
            self._check_abilities(reward.granted_abilities)
            self._check_passives(reward.unlocked_passives)
        return node

    def create_graph(
        self,
        graph_id,
        display_name=None,
        *,
        nodes,
        tags=(),
        editor_view="list",
        node_positions=None,
    ):
        key = str(graph_id).strip()
        if key in self.database.progression_graphs:
            raise RpgProgressionAuthoringError(f"duplicate progression graph: {key}")
        value = ProgressionGraphDefinition(
            key,
            display_name,
            nodes=tuple(self._normalize_node(x) for x in nodes),
            tags=tags,
            editor_view=editor_view,
            node_positions=node_positions,
        )
        self._execute(
            _MappingCommand(
                self.database.progression_graphs, key, value, None, f"Add Progression Graph {key}"
            )
        )
        return value

    def edit_graph(
        self,
        graph_id,
        *,
        display_name=None,
        nodes=None,
        tags=None,
        editor_view=None,
        node_positions=None,
    ):
        key = str(graph_id)
        old = self.database.progression_graphs.get(key)
        if old is None:
            raise RpgProgressionAuthoringError(f"unknown progression graph: {key}")
        value = ProgressionGraphDefinition(
            key,
            old.display_name if display_name is None else display_name,
            nodes=old.nodes if nodes is None else tuple(self._normalize_node(x) for x in nodes),
            tags=old.tags if tags is None else tags,
            editor_view=old.editor_view if editor_view is None else editor_view,
            node_positions=old.node_positions if node_positions is None else node_positions,
        )
        self._execute(
            _MappingCommand(
                self.database.progression_graphs, key, value, old, f"Edit Progression Graph {key}"
            )
        )
        return value

    def add_graph_node(self, graph_id, node):
        graph = self.database.progression_graphs.get(str(graph_id))
        if graph is None:
            raise RpgProgressionAuthoringError(f"unknown progression graph: {graph_id}")
        return self.edit_graph(graph_id, nodes=graph.nodes + (self._normalize_node(node),))

    def edit_graph_node(self, graph_id, node_id, replacement):
        graph = self.database.progression_graphs.get(str(graph_id))
        if graph is None:
            raise RpgProgressionAuthoringError(f"unknown progression graph: {graph_id}")
        replacement = self._normalize_node(replacement)
        if replacement.node_id != str(node_id):
            raise RpgProgressionAuthoringError("node id cannot change during edit")
        found = False
        nodes = []
        for node in graph.nodes:
            if node.node_id == str(node_id):
                nodes.append(replacement)
                found = True
            else:
                nodes.append(node)
        if not found:
            raise RpgProgressionAuthoringError(f"unknown progression node: {node_id}")
        return self.edit_graph(graph_id, nodes=nodes)

    def delete_graph_node(self, graph_id, node_id):
        graph = self.database.progression_graphs.get(str(graph_id))
        if graph is None:
            raise RpgProgressionAuthoringError(f"unknown progression graph: {graph_id}")
        key = str(node_id)
        refs = [
            n.node_id
            for n in graph.nodes
            if any(r.node_id == key for r in n.prerequisites + n.any_prerequisites)
        ]
        if refs:
            raise RpgProgressionAuthoringError(
                f"node {key} is prerequisite of " + ", ".join(sorted(refs))
            )
        nodes = tuple(n for n in graph.nodes if n.node_id != key)
        if len(nodes) == len(graph.nodes):
            raise RpgProgressionAuthoringError(f"unknown progression node: {key}")
        if not nodes:
            raise RpgProgressionAuthoringError("progression graph requires at least one node")
        return self.edit_graph(graph_id, nodes=nodes)

    def delete_graph(self, graph_id):
        key = str(graph_id)
        old = self.database.progression_graphs.get(key)
        if old is None:
            raise RpgProgressionAuthoringError(f"unknown progression graph: {key}")
        self._execute(
            _MappingCommand(
                self.database.progression_graphs, key, None, old, f"Delete Progression Graph {key}"
            )
        )

    def create_evolution(
        self,
        rule_id,
        source_ability_id,
        result_ability_id,
        *,
        progression_track_id=None,
        minimum_rank=1,
        priority=0,
        retain_source=False,
    ):
        key = str(rule_id).strip()
        if key in self.database.ability_evolutions:
            raise RpgProgressionAuthoringError(f"duplicate evolution: {key}")
        self._check_abilities((source_ability_id, result_ability_id))
        if (
            progression_track_id is not None
            and progression_track_id not in self.database.progression_tracks
        ):
            raise RpgProgressionAuthoringError(
                f"unknown progression track: {progression_track_id}"
            )
        value = AbilityEvolutionRule(
            key,
            source_ability_id,
            result_ability_id,
            progression_track_id=progression_track_id,
            minimum_rank=minimum_rank,
            priority=priority,
            retain_source=retain_source,
        )
        self._execute(
            _MappingCommand(
                self.database.ability_evolutions, key, value, None, f"Add Ability Evolution {key}"
            )
        )
        return value

    def edit_evolution(self, rule_id, **changes):
        key = str(rule_id)
        old = self.database.ability_evolutions.get(key)
        if old is None:
            raise RpgProgressionAuthoringError(f"unknown evolution: {key}")
        allowed = {
            "source_ability_id",
            "result_ability_id",
            "progression_track_id",
            "minimum_rank",
            "priority",
            "retain_source",
            "required_tags",
        }
        unknown = set(changes) - allowed
        if unknown:
            raise RpgProgressionAuthoringError(
                "unsupported evolution fields: " + ", ".join(sorted(unknown))
            )
        src = changes.get("source_ability_id", old.source_ability_id)
        dst = changes.get("result_ability_id", old.result_ability_id)
        self._check_abilities((src, dst))
        track = changes.get("progression_track_id", old.progression_track_id)
        if track is not None and track not in self.database.progression_tracks:
            raise RpgProgressionAuthoringError(f"unknown progression track: {track}")
        value = AbilityEvolutionRule(
            key,
            src,
            dst,
            progression_track_id=track,
            minimum_rank=changes.get("minimum_rank", old.minimum_rank),
            priority=changes.get("priority", old.priority),
            retain_source=changes.get("retain_source", old.retain_source),
            required_tags=changes.get("required_tags", old.required_tags),
        )
        self._execute(
            _MappingCommand(
                self.database.ability_evolutions, key, value, old, f"Edit Ability Evolution {key}"
            )
        )
        return value

    def delete_evolution(self, rule_id):
        key = str(rule_id)
        old = self.database.ability_evolutions.get(key)
        if old is None:
            raise RpgProgressionAuthoringError(f"unknown evolution: {key}")
        self._execute(
            _MappingCommand(
                self.database.ability_evolutions, key, None, old, f"Delete Ability Evolution {key}"
            )
        )

    def validate(self):
        try:
            self.project.validate()
        except Exception as exc:
            return (str(exc),)
        return ()
