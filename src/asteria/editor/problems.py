"""Project-wide Problems list (EDT-15): every validation issue with a place to jump to.

``collect_problems(document)`` is Qt-free. It gathers what the per-area
validators check, keeping every issue (``Project.validate`` stops at the
first one), and gives each a ``target`` the shell can navigate to:

    ("record", family, category_id, record_id)   family: rpg | battle | presentation | runtime_ui
    ("game_system", kind_id, record_id)          shops, quests, equipment sets, capture rules...
    ("scene", scene_id) / ("entity", scene_id, entity_id)
    ("sprite", asset_id) / ("sequence", sequence_id)
    ("script", path, line)
    ()                                           no single location
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Problem:
    severity: str  # "error" | "warning"
    area: str
    message: str
    target: tuple = ()

    @property
    def location(self):
        kind = self.target[0] if self.target else None
        if kind in ("record", "game_system"):
            return f"{self.target[-2]} / {self.target[-1]}"
        if kind == "script":
            return f"{Path(self.target[1]).name}:{self.target[2]}"
        if kind in ("scene", "sprite", "sequence"):
            return self.target[1]
        if kind == "entity":
            return f"{self.target[1]} / {self.target[2]}"
        return ""


# Leading words of RPG reference messages -> where that record is edited (longest prefix first).
_OWNERS = (
    ("ability evolution", ("record", "rpg", "evolutions")),
    ("progression graph", ("record", "rpg", "graphs")),
    ("progression", ("record", "rpg", "tracks")),
    ("equipment growth", ("record", "rpg", "growth")),
    ("equipment set", ("game_system", "equipment_sets")),
    ("equipment", ("record", "rpg", "equipment")),
    ("attachment", ("record", "rpg", "attachments")),
    ("passive", ("record", "rpg", "passives")),
    ("party setup", ("record", "rpg", "parties")),
    ("composition recipe", ("record", "rpg", "recipes")),
    ("capture rule", ("game_system", "capture_rules")),
    ("shop", ("game_system", "shops")),
    ("quest", ("game_system", "quests")),
    ("encounter", ("record", "rpg", "encounters")),
    ("enemy behavior binding", None),
    ("enemy", ("record", "rpg", "enemies")),
    ("actor", ("record", "rpg", "actors")),
    ("class", ("record", "rpg", "classes")),
)


def locate_record_message(message):
    """Navigation target for an RPG reference message such as ``actor hero_01 references unknown class x``."""
    for prefix, where in _OWNERS:
        found = re.match(rf"{re.escape(prefix)} (\S+)", message)
        if found:
            return () if where is None else (*where, found.group(1))
    return ()


def _attempt(found, area, check, target=()):
    try:
        check()
    except Exception as exc:  # noqa: BLE001 - every validator failure becomes one problem
        found.append(Problem("error", area, str(exc), target))


def _structure(project, found):
    if not project.scenes():
        found.append(Problem("error", "Project", "project requires at least one scene"))
    elif project.startup_scene_id not in {s.id for s in project.scenes()}:
        found.append(Problem("error", "Project", "startup scene is not set to an existing scene"))
    _attempt(found, "Assets", project.assets.validate)
    _attempt(found, "Battle Presentation", project.battle_presentation_library.validate)
    _attempt(found, "Game Start", lambda: project.game_start.validate(project))
    scenes = {s.id for s in project.scenes()}
    for scene_id in project.scene_event_bindings:
        if scene_id not in scenes:
            found.append(Problem("error", "Events", f"event bindings reference unknown scene {scene_id}"))
    for binding in project.lifecycle_event_bindings:
        if binding.event_program_id not in project.event_programs.ids():
            found.append(
                Problem("error", "Events", f"lifecycle binding references unknown program {binding.event_program_id}")
            )


def _references(project, found):
    for message in project.rpg_database.reference_errors():
        found.append(Problem("error", "Game Data", message, locate_record_message(message)))
    for message in project.ability_reference_errors():
        found.append(Problem("error", "Abilities", message, locate_record_message(message)))


def _field(project, found):
    from asteria.runtime.components2d import Interaction2DComponent

    from .event_editing import bindings_for_scene

    for scene in project.scenes():
        bindings = bindings_for_scene(project, scene)
        for binding in bindings.bindings.values():
            entity = scene.get_entity(binding.entity_id)
            target = ("entity", scene.id, entity.id) if entity is not None else ("scene", scene.id)
            if entity is None:
                found.append(
                    Problem(
                        "error", "Field / Events", f"{scene.name}: binding {binding.binding_id} entity missing", target
                    )
                )
            if project.event_programs.get(binding.program_id) is None:
                found.append(
                    Problem(
                        "error", "Field / Events", f"{scene.name}: binding {binding.binding_id} program missing", target
                    )
                )
        for entity in scene.entities():
            comp = entity.try_get(Interaction2DComponent)
            if comp is None or not comp.enabled:
                continue
            target = ("entity", scene.id, entity.id)
            if comp.event_binding_id and comp.event_binding_id not in bindings.bindings:
                found.append(
                    Problem(
                        "error", "Field / Events", f"{scene.name}/{entity.name}: interaction binding missing", target
                    )
                )
            if comp.event_program_id and project.event_programs.get(comp.event_program_id) is None:
                found.append(
                    Problem(
                        "error", "Field / Events", f"{scene.name}/{entity.name}: interaction program missing", target
                    )
                )
        from asteria.presentation.particles import effect_definition
        from asteria.runtime.environment2d import ParticleEmitter2DComponent

        for entity in scene.entities():
            emitter = entity.try_get(ParticleEmitter2DComponent)
            if emitter is None or not emitter.enabled:
                continue
            if not emitter.effect_id or effect_definition(project.assets, emitter.effect_id) is None:
                found.append(
                    Problem(
                        "warning",
                        "Particle Effects",
                        f"{scene.name}/{entity.name}: particle effect '{emitter.effect_id}' not found (nothing shows)",
                        ("entity", scene.id, entity.id),
                    )
                )


def _sprites(document, found, resource_root):
    from .animation_authoring import AnimationAuthoringController

    controller = AnimationAuthoringController(document, resource_root=resource_root)
    for asset_id in controller.sheets():
        try:
            messages = controller.problems(asset_id)
        except Exception as exc:  # noqa: BLE001
            messages = [f"{asset_id}: {exc}"]
        found.extend(Problem("error", "Sprite Animation", m, ("sprite", asset_id)) for m in messages)


def _timelines(document, found):
    from .action_timeline_authoring import ActionTimelineController

    controller = ActionTimelineController(document)
    for sequence_id in controller.sequences():
        try:
            messages = controller.problems(controller.get(sequence_id))
        except Exception as exc:  # noqa: BLE001
            messages = [f"{sequence_id}: {exc}"]
        found.extend(Problem("error", "Ability Timelines", m, ("sequence", sequence_id)) for m in messages)


def _scripts(document, found):
    path = getattr(document, "file_path", None)
    if not path:
        return
    folder = Path(path).parent / "scripts"
    if not folder.is_dir():
        return
    for script in sorted(folder.glob("*.py")):
        try:
            compile(script.read_text(encoding="utf-8"), str(script), "exec")
        except SyntaxError as exc:
            found.append(
                Problem("error", "Scripts", f"{script.name}: {exc.msg}", ("script", str(script), exc.lineno or 1))
            )
        except (OSError, UnicodeDecodeError) as exc:
            found.append(Problem("warning", "Scripts", f"{script.name}: {exc}", ("script", str(script), 1)))


def collect_problems(document, *, resource_root=None):
    project = document.project
    if project is None:
        return []
    found = []
    for area, step in (
        ("Project", lambda: _structure(project, found)),
        ("RPG Database", lambda: _references(project, found)),
        ("Field / Events", lambda: _field(project, found)),
        ("Sprites", lambda: _sprites(document, found, resource_root)),
        ("Action Timeline", lambda: _timelines(document, found)),
        ("Scripts", lambda: _scripts(document, found)),
    ):
        _attempt(found, area, step)
    # A validator that wraps others (Game Start validates the RPG database too) repeats their messages
    # without a location; keep only the located copies.
    located = [p.message for p in found if p.target]
    found = [p for p in found if p.target or not any(m in p.message for m in located)]
    # Safety net: anything Project.validate rejects must be visible even if no collector above names it.
    try:
        project.validate()
    except Exception as exc:  # noqa: BLE001
        text = str(exc)
        if not any(p.message in text or text in p.message for p in found):
            found.append(Problem("error", "Project", text))
    return found
