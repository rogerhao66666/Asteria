from __future__ import annotations

from dataclasses import dataclass

from asteria.rpg import ActorDefinition, ClassAssignment, ClassDefinition


class RpgActorClassAuthoringError(RuntimeError):
    pass


@dataclass(slots=True)
class _DefinitionCommand:
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
class ActorClassCoverage:
    class_create: bool = True
    class_edit_display_name: bool = True
    class_edit_stat_bonuses: bool = True
    class_edit_resource_bonuses: bool = True
    class_edit_tags: bool = True
    class_edit_abilities: bool = True
    class_delete: bool = True
    actor_create: bool = True
    actor_edit_display_name: bool = True
    actor_edit_base_stats: bool = True
    actor_edit_base_resources: bool = True
    actor_edit_tags: bool = True
    actor_edit_abilities: bool = True
    actor_class_assignments: bool = True
    assignment_roles: bool = True
    assignment_priority: bool = True
    assignment_enabled: bool = True
    assignment_progression_tracks: bool = True
    assignment_tags: bool = True
    actor_delete: bool = True
    duplicate_actor: bool = True
    duplicate_class: bool = True
    undo_redo: bool = True
    reference_validation: bool = True


class RpgActorClassAuthoringController:
    """Complete Actor/Class authoring over the canonical RpgDatabase.

    Definitions are immutable engine records. Editing therefore replaces one
    canonical definition atomically through the editor command stack, rather
    than maintaining a second mutable editor representation.
    """

    coverage = ActorClassCoverage()

    def __init__(self, document):
        self.document = document

    @property
    def project(self):
        if self.document.project is None:
            raise RpgActorClassAuthoringError("project required")
        return self.document.project

    @property
    def database(self):
        return self.project.rpg_database

    def _execute(self, command):
        self.document.execute(command)
        return command

    def _known_abilities(self):
        return set(self.project.gameplay_library.abilities.ids())

    def _check_abilities(self, ability_ids):
        values = tuple(dict.fromkeys(str(x).strip() for x in ability_ids))
        if any(not x for x in values):
            raise RpgActorClassAuthoringError("ability id cannot be empty")
        missing = [x for x in values if x not in self._known_abilities()]
        if missing:
            raise RpgActorClassAuthoringError("unknown abilities: " + ", ".join(sorted(missing)))
        return values

    def _check_assignment_refs(self, assignments):
        seen = set()
        result = []
        for raw in assignments:
            a = raw if isinstance(raw, ClassAssignment) else ClassAssignment.from_data(raw)
            if a.assignment_id in seen:
                raise RpgActorClassAuthoringError(f"duplicate assignment id: {a.assignment_id}")
            seen.add(a.assignment_id)
            if a.class_id not in self.database.classes:
                raise RpgActorClassAuthoringError(f"unknown class: {a.class_id}")
            missing = [x for x in a.progression_track_ids if x not in self.database.progression_tracks]
            if missing:
                raise RpgActorClassAuthoringError("unknown progression tracks: " + ", ".join(sorted(missing)))
            result.append(a)
        return tuple(result)

    def classes(self):
        return tuple(self.database.classes[k] for k in sorted(self.database.classes))

    def actors(self):
        return tuple(self.database.actors[k] for k in sorted(self.database.actors))

    def create_class(
        self,
        class_id,
        display_name=None,
        *,
        stat_bonuses=None,
        resource_bonuses=None,
        granted_tags=(),
        granted_abilities=(),
    ):
        cid = str(class_id).strip()
        if cid in self.database.classes:
            raise RpgActorClassAuthoringError(f"duplicate class: {cid}")
        value = ClassDefinition(
            cid,
            display_name,
            stat_bonuses=stat_bonuses,
            resource_bonuses=resource_bonuses,
            granted_tags=granted_tags,
            granted_abilities=self._check_abilities(granted_abilities),
        )
        self._execute(_DefinitionCommand(self.database.classes, cid, value, None, f"Add Class {cid}"))
        return value

    def edit_class(
        self,
        class_id,
        *,
        display_name=None,
        stat_bonuses=None,
        resource_bonuses=None,
        granted_tags=None,
        granted_abilities=None,
    ):
        old = self.database.classes.get(str(class_id))
        if old is None:
            raise RpgActorClassAuthoringError(f"unknown class: {class_id}")
        value = ClassDefinition(
            old.class_id,
            old.display_name if display_name is None else display_name,
            stat_bonuses=old.stat_bonuses if stat_bonuses is None else stat_bonuses,
            resource_bonuses=(old.resource_bonuses if resource_bonuses is None else resource_bonuses),
            granted_tags=old.granted_tags if granted_tags is None else granted_tags,
            granted_abilities=(
                old.granted_abilities if granted_abilities is None else self._check_abilities(granted_abilities)
            ),
        )
        self._execute(_DefinitionCommand(self.database.classes, old.class_id, value, old, f"Edit Class {old.class_id}"))
        return value

    def delete_class(self, class_id):
        cid = str(class_id)
        old = self.database.classes.get(cid)
        if old is None:
            raise RpgActorClassAuthoringError(f"unknown class: {cid}")
        users = [
            a.actor_id for a in self.database.actors.values() if any(x.class_id == cid for x in a.class_assignments)
        ]
        if users:
            raise RpgActorClassAuthoringError(f"class {cid} is referenced by actors: " + ", ".join(sorted(users)))
        return self._execute(_DefinitionCommand(self.database.classes, cid, None, old, f"Delete Class {cid}"))

    def duplicate_class(self, class_id, new_class_id, display_name=None):
        source = self.database.classes.get(str(class_id))
        if source is None:
            raise RpgActorClassAuthoringError(f"unknown class: {class_id}")
        return self.create_class(
            new_class_id,
            display_name or f"{source.display_name} Copy",
            stat_bonuses=source.stat_bonuses,
            resource_bonuses=source.resource_bonuses,
            granted_tags=source.granted_tags,
            granted_abilities=source.granted_abilities,
        )

    def create_actor(
        self,
        actor_id,
        display_name=None,
        *,
        class_assignments=(),
        base_stats=None,
        base_resources=None,
        tags=(),
        abilities=(),
    ):
        aid = str(actor_id).strip()
        if aid in self.database.actors:
            raise RpgActorClassAuthoringError(f"duplicate actor: {aid}")
        assignments = self._check_assignment_refs(class_assignments)
        value = ActorDefinition(
            aid,
            display_name,
            class_assignments=assignments,
            base_stats=base_stats,
            base_resources=base_resources,
            tags=tags,
            abilities=self._check_abilities(abilities),
        )
        self._execute(_DefinitionCommand(self.database.actors, aid, value, None, f"Add Actor {aid}"))
        return value

    def edit_actor(
        self,
        actor_id,
        *,
        display_name=None,
        class_assignments=None,
        base_stats=None,
        base_resources=None,
        tags=None,
        abilities=None,
    ):
        old = self.database.actors.get(str(actor_id))
        if old is None:
            raise RpgActorClassAuthoringError(f"unknown actor: {actor_id}")
        assignments = (
            old.class_assignments if class_assignments is None else self._check_assignment_refs(class_assignments)
        )
        value = ActorDefinition(
            old.actor_id,
            old.display_name if display_name is None else display_name,
            class_assignments=assignments,
            base_stats=old.base_stats if base_stats is None else base_stats,
            base_resources=(old.base_resources if base_resources is None else base_resources),
            tags=old.tags if tags is None else tags,
            abilities=(old.abilities if abilities is None else self._check_abilities(abilities)),
        )
        self._execute(_DefinitionCommand(self.database.actors, old.actor_id, value, old, f"Edit Actor {old.actor_id}"))
        return value

    def delete_actor(self, actor_id):
        aid = str(actor_id)
        old = self.database.actors.get(aid)
        if old is None:
            raise RpgActorClassAuthoringError(f"unknown actor: {aid}")
        return self._execute(_DefinitionCommand(self.database.actors, aid, None, old, f"Delete Actor {aid}"))

    def duplicate_actor(self, actor_id, new_actor_id, display_name=None):
        source = self.database.actors.get(str(actor_id))
        if source is None:
            raise RpgActorClassAuthoringError(f"unknown actor: {actor_id}")
        return self.create_actor(
            new_actor_id,
            display_name or f"{source.display_name} Copy",
            class_assignments=source.class_assignments,
            base_stats=source.base_stats,
            base_resources=source.base_resources,
            tags=source.tags,
            abilities=source.abilities,
        )

    def add_assignment(
        self,
        actor_id,
        class_id,
        *,
        assignment_id=None,
        role="class",
        enabled=True,
        priority=0,
        progression_track_ids=(),
        tags=(),
    ):
        old = self.database.actors.get(str(actor_id))
        if old is None:
            raise RpgActorClassAuthoringError(f"unknown actor: {actor_id}")
        assignment = ClassAssignment(
            class_id,
            assignment_id=assignment_id,
            role=role,
            enabled=enabled,
            priority=priority,
            progression_track_ids=progression_track_ids,
            tags=tags,
        )
        return self.edit_actor(actor_id, class_assignments=old.class_assignments + (assignment,))

    def edit_assignment(self, actor_id, assignment_id, **changes):
        old = self.database.actors.get(str(actor_id))
        if old is None:
            raise RpgActorClassAuthoringError(f"unknown actor: {actor_id}")
        found = False
        values = []
        allowed = {"class_id", "role", "enabled", "priority", "progression_track_ids", "tags"}
        unknown = set(changes) - allowed
        if unknown:
            raise RpgActorClassAuthoringError("unsupported assignment fields: " + ", ".join(sorted(unknown)))
        for a in old.class_assignments:
            if a.assignment_id != str(assignment_id):
                values.append(a)
                continue
            found = True
            values.append(
                ClassAssignment(
                    changes.get("class_id", a.class_id),
                    assignment_id=a.assignment_id,
                    role=changes.get("role", a.role),
                    enabled=changes.get("enabled", a.enabled),
                    priority=changes.get("priority", a.priority),
                    progression_track_ids=changes.get("progression_track_ids", a.progression_track_ids),
                    tags=changes.get("tags", a.tags),
                )
            )
        if not found:
            raise RpgActorClassAuthoringError(f"unknown class assignment: {assignment_id}")
        return self.edit_actor(actor_id, class_assignments=values)

    def remove_assignment(self, actor_id, assignment_id):
        old = self.database.actors.get(str(actor_id))
        if old is None:
            raise RpgActorClassAuthoringError(f"unknown actor: {actor_id}")
        values = tuple(a for a in old.class_assignments if a.assignment_id != str(assignment_id))
        if len(values) == len(old.class_assignments):
            raise RpgActorClassAuthoringError(f"unknown class assignment: {assignment_id}")
        return self.edit_actor(actor_id, class_assignments=values)

    def validate(self):
        try:
            self.project.validate()
        except Exception as exc:
            return (str(exc),)
        return ()
