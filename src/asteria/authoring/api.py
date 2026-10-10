from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from asteria.core import Entity, Transform
from asteria.core.ids import new_id
from asteria.events import (
    EventBinding,
    EventInstruction,
    EventProgram,
    EventTriggerKind,
    SceneEventBindings,
)
from asteria.gameplay import (
    Effect,
    GameplayAttributesComponent,
    ModifierSet,
    ResourcePool,
    StatBlock,
    TagSet,
    apply_effect,
)


class AuthoringError(RuntimeError):
    pass


@dataclass(slots=True)
class _SetAttribute:
    target: object
    attribute: str
    new_value: object
    old_value: object

    @property
    def label(self):
        return f"Script: set {self.attribute}"

    def redo(self):
        setattr(self.target, self.attribute, self.new_value)

    def undo(self):
        setattr(self.target, self.attribute, self.old_value)


@dataclass(slots=True)
class _AddEntity:
    scene: object
    entity: Entity

    @property
    def label(self):
        return f"Script: add {self.entity.name}"

    def redo(self):
        self.entity._destroy_requested = False
        if self.entity.scene is None:
            self.scene.add_entity(self.entity)

    def undo(self):
        if self.entity.scene is self.scene:
            self.scene.detach_entity(self.entity)


@dataclass(slots=True)
class _AddComponent:
    entity: Entity
    component: object

    @property
    def label(self):
        return f"Script: add {type(self.component).__name__}"

    def redo(self):
        if not self.entity.has(type(self.component)):
            self.entity.add_component(self.component)

    def undo(self):
        if self.entity.has(type(self.component)):
            self.entity.detach_component(type(self.component))


@dataclass(slots=True)
class _ReplaceProgram:
    registry: object
    program_id: str
    new_program: EventProgram
    old_program: EventProgram

    @property
    def label(self):
        return "Script: edit event"

    def redo(self):
        self.registry.replace(self.program_id, self.new_program)

    def undo(self):
        self.registry.replace(self.program_id, self.old_program)


@dataclass(slots=True)
class _AddProgram:
    registry: object
    program_id: str
    program: EventProgram

    @property
    def label(self):
        return "Script: add event program"

    def redo(self):
        if self.registry.get(self.program_id) is None:
            self.registry.register(self.program_id, self.program)

    def undo(self):
        if self.registry.get(self.program_id) is not None:
            self.registry.unregister(self.program_id)


@dataclass(slots=True)
class _AddBinding:
    bindings: SceneEventBindings
    binding: EventBinding

    @property
    def label(self):
        return "Script: add event binding"

    def redo(self):
        if self.binding.binding_id not in self.bindings.bindings:
            self.bindings.add(self.binding)

    def undo(self):
        if self.binding.binding_id in self.bindings.bindings:
            self.bindings.remove(self.binding.binding_id)


class AuthoringSession:
    """First-class Qt-free Python authoring facade."""

    def __init__(self, project, *, execute: Callable | None = None):
        if project is None:
            raise AuthoringError("no project loaded")
        self._project = project
        self._execute = execute or (lambda command: command.redo())

    @property
    def raw_project(self):
        return self._project

    @property
    def name(self):
        return self._project.name

    def scenes(self):
        return tuple(AuthoringScene(self, s) for s in self._project.scenes())

    def scene(self, name_or_id) -> AuthoringScene:
        value = str(name_or_id)
        by_id = self._project.scene(value)
        if by_id is not None:
            return AuthoringScene(self, by_id)
        matches = [s for s in self._project.scenes() if s.name == value]
        if not matches:
            raise AuthoringError(f"scene not found: {value}")
        if len(matches) > 1:
            raise AuthoringError(f"scene name is ambiguous: {value}")
        return AuthoringScene(self, matches[0])

    scene_named = scene

    def wrap_scene(self, scene) -> AuthoringScene:
        if scene is None:
            return None
        return AuthoringScene(self, scene)

    def wrap_entity(self, entity) -> AuthoringEntity:
        if entity is None:
            return None
        scene = entity.scene
        if scene is None:
            raise AuthoringError("entity is not attached to a scene")
        return AuthoringEntity(self, AuthoringScene(self, scene), entity)

    def wrap_selection(self, kind, value):
        if value is None:
            return None
        if kind == "project":
            return self
        if kind == "scene":
            return self.wrap_scene(value)
        if kind == "entity":
            return self.wrap_entity(value)
        if kind == "component":
            try:
                return self.wrap_entity(value.entity)
            except RuntimeError:
                return None
        return None

    def _run(self, command):
        self._execute(command)
        return command


class AuthoringScene:
    def __init__(self, session, scene):
        self._session = session
        self._scene = scene

    @property
    def id(self):
        return self._scene.id

    @property
    def name(self):
        return self._scene.name

    def entities(self):
        return tuple(AuthoringEntity(self._session, self, e) for e in self._scene.entities())

    def entity(self, name_or_id) -> AuthoringEntity:
        value = str(name_or_id)
        by_id = self._scene.get_entity(value)
        if by_id is not None:
            return AuthoringEntity(self._session, self, by_id)
        matches = [e for e in self._scene.entities() if e.name == value]
        if not matches:
            raise AuthoringError(f"entity not found in {self.name}: {value}")
        if len(matches) > 1:
            raise AuthoringError(f"entity name is ambiguous in {self.name}: {value}")
        return AuthoringEntity(self._session, self, matches[0])

    entity_named = entity

    def create_entity(self, name, *, x=0.0, y=0.0) -> AuthoringEntity:
        entity = Entity(str(name))
        entity.add_component(Transform(float(x), float(y)))
        self._session._run(_AddEntity(self._scene, entity))
        return AuthoringEntity(self._session, self, entity)


class AuthoringTransform:
    def __init__(self, session, transform):
        self._session = session
        self._transform = transform

    @property
    def x(self):
        return self._transform.x

    @x.setter
    def x(self, value):
        self._session._run(_SetAttribute(self._transform, "x", float(value), self._transform.x))

    @property
    def y(self):
        return self._transform.y

    @y.setter
    def y(self, value):
        self._session._run(_SetAttribute(self._transform, "y", float(value), self._transform.y))

    @property
    def position(self):
        return (self._transform.x, self._transform.y)

    @position.setter
    def position(self, value):
        x, y = value
        self.x = x
        self.y = y

    @property
    def rotation(self):
        return self._transform.rotation

    @rotation.setter
    def rotation(self, value):
        self._session._run(_SetAttribute(self._transform, "rotation", float(value), self._transform.rotation))

    @property
    def scale(self):
        return (self._transform.scale_x, self._transform.scale_y)

    @scale.setter
    def scale(self, value):
        x, y = value
        self._session._run(_SetAttribute(self._transform, "scale_x", float(x), self._transform.scale_x))
        self._session._run(_SetAttribute(self._transform, "scale_y", float(y), self._transform.scale_y))


class AuthoringEvent:
    def __init__(self, session, program_id):
        self._session = session
        self.program_id = program_id

    @property
    def program(self):
        return self._session.raw_project.event_programs.require(self.program_id)

    def append(self, opcode, **args) -> AuthoringEvent:
        old = self.program
        new = EventProgram(
            (*old.instructions, EventInstruction(opcode, args)),
            name=old.name,
        )
        self._session._run(
            _ReplaceProgram(
                self._session.raw_project.event_programs,
                self.program_id,
                new,
                old,
            )
        )
        return self

    def dialogue(self, speaker, text=None) -> AuthoringEvent:
        if text is None:
            text = speaker
            speaker = ""
        return self.append("DIALOGUE", speaker=str(speaker), text=str(text))

    def set_switch(self, name, value=True) -> AuthoringEvent:
        return self.append("SET_SWITCH", name=str(name), value=bool(value))

    def set_variable(self, name, value) -> AuthoringEvent:
        return self.append("SET_VARIABLE", name=str(name), value=value)

    def wait(self, seconds) -> AuthoringEvent:
        return self.append("WAIT", seconds=float(seconds))

    def world(self, command, **args) -> AuthoringEvent:
        return self.append("WORLD", command=str(command).upper(), args=dict(args))

    def transfer(self, destination, **args) -> AuthoringEvent:
        payload = {"destination": destination}
        payload.update(args)
        return self.world("TRANSFER", **payload)

    def end(self):
        return self.append("END")


class AuthoringGameplayAttributes:
    def __init__(self, session, component):
        self._session = session
        self._component = component

    def stat(self, name, default=0.0):
        return StatBlock(self._component.stats).get(name, default)

    def set_stat(self, name, value):
        block = StatBlock(self._component.stats)
        block.set(name, value)
        new_values = dict(block.to_data()["values"])
        self._session._run(_SetAttribute(self._component, "stats", new_values, self._component.stats))
        return block.get(name)

    def add_stat(self, name, delta):
        return self.set_stat(name, self.stat(name) + float(delta))

    def define_resource(self, name, maximum, *, current=None, minimum=0.0, replace=False):
        pool = ResourcePool.from_data(
            {
                "schema": "asteria.resource_pool",
                "version": 1,
                "values": self._component.resources,
            }
        )
        resource = pool.define(
            name,
            maximum,
            current=current,
            minimum=minimum,
            replace=replace,
        )
        new_values = dict(pool.to_data()["values"])
        self._session._run(_SetAttribute(self._component, "resources", new_values, self._component.resources))
        return resource.current

    def resource(self, name):
        pool = ResourcePool.from_data(
            {
                "schema": "asteria.resource_pool",
                "version": 1,
                "values": self._component.resources,
            }
        )
        return pool.get(name)

    def change_resource(self, name, delta):
        pool = ResourcePool.from_data(
            {
                "schema": "asteria.resource_pool",
                "version": 1,
                "values": self._component.resources,
            }
        )
        value = pool.change(name, delta)
        new_values = dict(pool.to_data()["values"])
        self._session._run(_SetAttribute(self._component, "resources", new_values, self._component.resources))
        return value

    def spend_resource(self, name, amount):
        pool = ResourcePool.from_data(
            {
                "schema": "asteria.resource_pool",
                "version": 1,
                "values": self._component.resources,
            }
        )
        if not pool.spend(name, amount):
            return False
        new_values = dict(pool.to_data()["values"])
        self._session._run(_SetAttribute(self._component, "resources", new_values, self._component.resources))
        return True

    def add_tag(self, tag):
        tags = TagSet(self._component.tags)
        if not tags.add(tag):
            return False
        self._session._run(_SetAttribute(self._component, "tags", list(tags.values()), self._component.tags))
        return True

    def remove_tag(self, tag):
        tags = TagSet(self._component.tags)
        if not tags.remove(tag):
            return False
        self._session._run(_SetAttribute(self._component, "tags", list(tags.values()), self._component.tags))
        return True

    def has_tag(self, tag):
        return TagSet(self._component.tags).contains(tag)

    def effective_stat(self, name, modifiers=None):
        modifiers = modifiers or ModifierSet()
        if not isinstance(modifiers, ModifierSet):
            raise TypeError("modifiers must be ModifierSet")
        return modifiers.evaluate(
            name,
            self.stat(name),
            tags=TagSet(self._component.tags),
        )

    def apply_effect(self, effect):
        if not isinstance(effect, Effect):
            raise TypeError("effect must be Effect")

        stats = StatBlock(self._component.stats)
        resources = ResourcePool.from_data(
            {
                "schema": "asteria.resource_pool",
                "version": 1,
                "values": self._component.resources,
            }
        )
        tags = TagSet(self._component.tags)
        result = apply_effect(effect, stats, resources, tags)
        if not result.applied:
            return result

        new_stats = dict(stats.to_data()["values"])
        new_resources = dict(resources.to_data()["values"])
        new_tags = list(tags.values())

        if new_stats != self._component.stats:
            self._session._run(_SetAttribute(self._component, "stats", new_stats, self._component.stats))
        if new_resources != self._component.resources:
            self._session._run(
                _SetAttribute(
                    self._component,
                    "resources",
                    new_resources,
                    self._component.resources,
                )
            )
        if new_tags != self._component.tags:
            self._session._run(_SetAttribute(self._component, "tags", new_tags, self._component.tags))
        return result


class AuthoringEntity:
    def __init__(self, session, scene, entity):
        self._session = session
        self._scene = scene
        self._entity = entity

    @property
    def id(self):
        return self._entity.id

    @property
    def name(self):
        return self._entity.name

    @name.setter
    def name(self, value):
        self._session._run(_SetAttribute(self._entity, "name", str(value), self._entity.name))

    @property
    def enabled(self):
        return self._entity.enabled

    @enabled.setter
    def enabled(self, value):
        self._session._run(_SetAttribute(self._entity, "enabled", bool(value), self._entity.enabled))

    @property
    def transform(self) -> AuthoringTransform:
        transform = self._entity.try_get(Transform)
        if transform is None:
            transform = Transform()
            self._session._run(_AddComponent(self._entity, transform))
        return AuthoringTransform(self._session, transform)

    @property
    def gameplay(self):
        component = self._entity.try_get(GameplayAttributesComponent)
        if component is None:
            component = GameplayAttributesComponent()
            self._session._run(_AddComponent(self._entity, component))
        return AuthoringGameplayAttributes(self._session, component)

    def event(self, name="Event", *, trigger="action") -> AuthoringEvent:
        project = self._session.raw_project
        program_id = new_id()
        binding_id = new_id()
        program = EventProgram((), name=str(name))
        binding = EventBinding(
            binding_id,
            self._entity.id,
            program_id,
            trigger=EventTriggerKind(str(trigger).lower()),
        )
        bindings = project.scene_event_bindings.setdefault(self._scene.id, SceneEventBindings())
        self._session._run(_AddProgram(project.event_programs, program_id, program))
        self._session._run(_AddBinding(bindings, binding))
        return AuthoringEvent(self._session, program_id)
