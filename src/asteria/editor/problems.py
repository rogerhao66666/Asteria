"""Project-wide Problems list (EDT-15): every validation issue with a place to jump to.

``collect_problems(document)`` is Qt-free. It gathers what the per-area
validators check, keeping every issue (``Project.validate`` stops at the
first one), and gives each a ``target`` the shell can navigate to:

    ("record", family, category_id, record_id)   family: rpg | battle | presentation
    ("game_system", kind_id, record_id)          shops, quests, equipment sets, capture rules...
    ("scene", scene_id) / ("entity", scene_id, entity_id)
    ("sprite", asset_id) / ("sequence", sequence_id)
    ("script", path, line)
    ("combat", kind_id, record_id)               Real-Time Combat workspace (attacks, projectiles,
    rarities, affixes)
    ("behavior_tree", tree_id)
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
        if kind == "combat":
            return f"{self.target[1]} / {self.target[2]}"
        if kind in ("scene", "sprite", "sequence", "behavior_tree"):
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
    """Navigation target for an RPG reference message such as ``actor hero_01 references unknown
    class x``."""
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
            found.append(
                Problem("error", "Events", f"event bindings reference unknown scene {scene_id}")
            )
    for binding in project.lifecycle_event_bindings:
        if binding.event_program_id not in project.event_programs.ids():
            found.append(
                Problem(
                    "error",
                    "Events",
                    f"lifecycle binding references unknown program {binding.event_program_id}",
                )
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
                        "error",
                        "Field / Events",
                        f"{scene.name}: binding {binding.binding_id} entity missing",
                        target,
                    )
                )
            if project.event_programs.get(binding.program_id) is None:
                found.append(
                    Problem(
                        "error",
                        "Field / Events",
                        f"{scene.name}: binding {binding.binding_id} program missing",
                        target,
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
                        "error",
                        "Field / Events",
                        f"{scene.name}/{entity.name}: interaction binding missing",
                        target,
                    )
                )
            if comp.event_program_id and project.event_programs.get(comp.event_program_id) is None:
                found.append(
                    Problem(
                        "error",
                        "Field / Events",
                        f"{scene.name}/{entity.name}: interaction program missing",
                        target,
                    )
                )
        from asteria.presentation.particles import effect_definition
        from asteria.runtime.environment2d import ParticleEmitter2DComponent

        for entity in scene.entities():
            emitter = entity.try_get(ParticleEmitter2DComponent)
            if emitter is None or not emitter.enabled:
                continue
            if (
                not emitter.effect_id
                or effect_definition(project.assets, emitter.effect_id) is None
            ):
                found.append(
                    Problem(
                        "warning",
                        "Particle Effects",
                        f"{scene.name}/{entity.name}: particle effect '{emitter.effect_id}' "
                        f"not found (nothing shows)",
                        ("entity", scene.id, entity.id),
                    )
                )


def _combat(project, found):
    """Real-time combat references (D22): attacks, projectiles, timelines, abilities, behaviour
    trees and scene entities."""
    library, db = project.gameplay_library, project.rpg_database
    states = set(library.states.ids())
    attacks, projectiles, timelines = library.attacks, library.projectiles, library.timelines

    def add(severity, message, target):
        found.append(Problem(severity, "Real-Time Combat", message, target))

    for attack in attacks.values():
        target = ("combat", "attacks", attack.attack_id)
        if attack.damage_formula_id and attack.damage_formula_id not in library.formulas:
            add(
                "error",
                f"attack {attack.attack_id}: shared formula {attack.damage_formula_id} not found",
                target,
            )
        for entry in attack.apply_states:
            if entry["state"] not in states:
                add(
                    "error", f"attack {attack.attack_id}: state {entry['state']} not found", target
                )
    for projectile in projectiles.values():
        if projectile.attack_id and projectile.attack_id not in attacks:
            add(
                "error",
                f"projectile {projectile.projectile_id}: attack {projectile.attack_id} not found",
                ("combat", "projectiles", projectile.projectile_id),
            )
    for timeline in timelines.values():
        target = ("record", "rpg", "action_timelines", timeline.timeline_id)
        for cue in timeline.cues:
            kind, payload = cue.kind.value, cue.payload
            if kind == "projectile" and payload.get("projectile_id") not in projectiles:
                add(
                    "error",
                    f"timeline {timeline.timeline_id}: projectile "
                    f"{payload.get('projectile_id')} not found",
                    target,
                )
            if kind == "combo_window" and payload.get("next") and payload["next"] not in timelines:
                add(
                    "error",
                    f"timeline {timeline.timeline_id}: combo goes to unknown timeline "
                    f"{payload['next']}",
                    target,
                )
            if kind == "hitbox" and payload.get("hit_tag") and payload["hit_tag"] not in attacks:
                add(
                    "warning",
                    f"timeline {timeline.timeline_id}: hit tag {payload['hit_tag']} is not an "
                    f"attack (no damage)",
                    target,
                )
    for ability_id in library.abilities.ids():
        ability = library.abilities.require(ability_id)
        if ability.timeline_id and ability.timeline_id not in timelines:
            add(
                "error",
                f"ability {ability_id}: timeline {ability.timeline_id} not found",
                ("record", "rpg", "abilities", ability_id),
            )
    for tree in db.behavior_trees.values():
        for _path, node in tree.root.walk():
            p = node.params
            missing = None
            if (
                node.kind in ("use_ability", "ability_ready")
                and library.abilities.get(str(p.get("ability", ""))) is None
            ):
                missing = f"ability {p.get('ability')}"
            elif node.kind in ("apply_state", "has_state") and p.get("state") not in states:
                missing = f"state {p.get('state')}"
            elif node.kind == "summon" and project.prefabs.get(str(p.get("prefab", ""))) is None:
                missing = f"prefab {p.get('prefab')}"
            if missing:
                add(
                    "error",
                    f"behavior tree {tree.tree_id}: {node.kind} uses unknown {missing}",
                    ("behavior_tree", tree.tree_id),
                )
    from asteria.runtime.action_combat import ActionCombatComponent, parse_bindings
    from asteria.runtime.combat import CombatantComponent, parse_values

    for scene in project.scenes():
        for entity in scene.entities():
            target = ("entity", scene.id, entity.id)
            spec = entity.try_get(ActionCombatComponent)
            if spec is not None:
                try:
                    bindings = parse_bindings(spec.bindings)
                except ValueError as exc:
                    add("error", f"{scene.name}/{entity.name}: input bindings: {exc}", target)
                    bindings = {}
                for action, ability_id in (
                    (action, option)
                    for action, value in bindings.items()
                    for option in value.split("|")
                    if option.strip()
                ):
                    ability_id = ability_id.strip()
                    if library.abilities.get(ability_id) is None:
                        add(
                            "error",
                            f"{scene.name}/{entity.name}: {action} uses unknown ability "
                            f"{ability_id}",
                            target,
                        )
            combatant = entity.try_get(CombatantComponent)
            if combatant is not None:
                if combatant.drop_table_id and combatant.drop_table_id not in db.drop_tables:
                    add(
                        "error",
                        f"{scene.name}/{entity.name}: drop table {combatant.drop_table_id} not "
                        f"found",
                        target,
                    )
                try:
                    resources = parse_values(combatant.resources)
                except ValueError as exc:
                    add("error", f"{scene.name}/{entity.name}: resources: {exc}", target)
                    continue
                if (
                    combatant.life_resource
                    and combatant.life_resource not in resources
                    and not _linked(entity)
                ):
                    add(
                        "warning",
                        f"{scene.name}/{entity.name}: life resource {combatant.life_resource}"
                        " is not among its resources (it can never die)",
                        target,
                    )


def _linked(entity):
    from asteria.runtime.actor_link import ActorLinkComponent

    link = entity.try_get(ActorLinkComponent)
    return link is not None and bool(link.actor_id)


def _sprites(document, found, resource_root):
    from .animation_authoring import AnimationAuthoringController

    controller = AnimationAuthoringController(document, resource_root=resource_root)
    for asset_id in controller.sheets():
        try:
            messages = controller.problems(asset_id)
        except Exception as exc:  # noqa: BLE001
            messages = [f"{asset_id}: {exc}"]
        found.extend(
            Problem("error", "Sprite Animation", m, ("sprite", asset_id)) for m in messages
        )


def _timelines(document, found):
    from .action_timeline_authoring import ActionTimelineController

    controller = ActionTimelineController(document)
    for sequence_id in controller.sequences():
        try:
            messages = controller.problems(controller.get(sequence_id))
        except Exception as exc:  # noqa: BLE001
            messages = [f"{sequence_id}: {exc}"]
        found.extend(
            Problem("error", "Ability Timelines", m, ("sequence", sequence_id)) for m in messages
        )


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
                Problem(
                    "error",
                    "Scripts",
                    f"{script.name}: {exc.msg}",
                    ("script", str(script), exc.lineno or 1),
                )
            )
        except (OSError, UnicodeDecodeError) as exc:
            found.append(
                Problem("warning", "Scripts", f"{script.name}: {exc}", ("script", str(script), 1))
            )


def used_stats(project):
    """Every stat id the project's data names: base stats, gear, passives, formulas, battle
    checks, damage and state rules, the Status page's details (D91)."""
    from .data_translation import stat_ids

    db = project.rpg_database
    found = set(stat_ids(project))
    for enemy in db.enemies.values():
        found.update(enemy.stats)
    for rule in db.derived_stats.values():
        found.add(rule.stat_id)
        found.update(rule.terms)
    for check in db.outcome_checks.values():
        found.update(check.source_stat_terms or {})
        found.update(check.target_stat_terms or {})
    for rule in db.interaction_rules.values():
        for terms in (rule.source_stat_terms, rule.target_stat_terms):
            found.update(terms or {})
        found.update(rule.multiplier_source_terms or {})
        found.update(rule.multiplier_target_terms or {})
    for policy in db.battle_state_policies.values():
        found.update(policy.target_stat_terms or {})
    from asteria.rpg.menu_pages import menu_pages

    for page in menu_pages(db).values():  # D96: the pages' detail tables
        for block in page.blocks:
            found.update(line.stat_id for line in block.stat_lines)
            found.update(block.stat_rows)
    return {s for s in found if s}


def _stats(project, found):
    """A project that defines its stats (Game Systems ▸ Stats) defines every one it uses."""
    defined = project.rpg_database.stat_definitions
    if not defined:
        return  # an older project: its stats are its data's names
    for stat_id in sorted(used_stats(project) - set(defined)):
        found.append(
            Problem(
                "warning",
                "Stats",
                f"stat {stat_id} is used but not defined: add it in Game Systems ▸ Stats",
                ("game_system", "stat_definitions", ""),
            )
        )


def _tags(project, found):
    """A project that defines its tags (Game Systems ▸ Tags) defines every one it uses, alone
    or by a family (``rune.*``)."""
    from asteria.rpg.tag_definitions import definition_for

    from .tag_usage import project_tags

    defined = project.rpg_database.tag_definitions
    if not defined:
        return  # an older project: its tags are words its rules agree on
    for tag in sorted(project_tags(project)):
        if definition_for(defined, tag) is None:
            found.append(
                Problem(
                    "warning",
                    "Tags",
                    f"tag {tag} is used but not defined: add it in Game Systems ▸ Tags",
                    ("game_system", "tag_definitions", ""),
                )
            )


def project_formulas(project):
    """Every formula the project writes: ``(where, text, names)`` - the record (a table and its
    id) and the names the formula may use (``FORMULA_FIELDS``), however deep it sits."""
    from asteria.gameplay.expressions import FORMULA_FIELDS

    out = []

    def walk(value, where):
        if isinstance(value, list):
            for x in value:
                walk(x, where)
        elif isinstance(value, dict):
            for (owner, key), names in FORMULA_FIELDS.items():
                text = value.get(key) if value.get("schema") == owner else None
                if isinstance(text, str) and text.strip():
                    out.append((where, text.strip(), names))
            for x in value.values():
                walk(x, where)

    tables = dict(project.rpg_database.to_data())
    tables.update({f"lib.{k}": v for k, v in project.gameplay_library.to_data().items()})
    for table, records in tables.items():
        if not isinstance(records, list):
            continue
        for record in records:
            if isinstance(record, dict):
                rid = next((v for k, v in record.items() if k.endswith("_id")), "")
                walk(record, f"{table.removeprefix('lib.')} {rid}".strip())
    return out


def _formulas(project, found):
    """Every formula parses and reads only declared variables: a project that defines its stats
    (Game Systems ▸ Stats) may only read those stats, and resources it has (D94)."""
    from .formula_field import declared, formula_problem
    from .record_vocabulary import ProjectVocabulary

    stats, resources, strict = declared(ProjectVocabulary(project))
    stat_ids, resource_ids = [c.value for c in stats], [c.value for c in resources]
    for where, text, names in project_formulas(project):
        problem = formula_problem(text, names, stat_ids, resource_ids, strict)
        if problem:
            found.append(Problem("error", "Formulas", f"{where}: {text} - {problem}", ()))


def collect_problems(document, *, resource_root=None):
    project = document.project
    if project is None:
        return []
    found = []
    for area, step in (
        ("Project", lambda: _structure(project, found)),
        ("RPG Database", lambda: _references(project, found)),
        ("Field / Events", lambda: _field(project, found)),
        ("Real-Time Combat", lambda: _combat(project, found)),
        ("Stats", lambda: _stats(project, found)),
        ("Tags", lambda: _tags(project, found)),
        ("Formulas", lambda: _formulas(project, found)),
        ("Sprites", lambda: _sprites(document, found, resource_root)),
        ("Action Timeline", lambda: _timelines(document, found)),
        ("Scripts", lambda: _scripts(document, found)),
    ):
        _attempt(found, area, step)
    # A validator that wraps others (Game Start validates the RPG database too) repeats their
    # messages
    # without a location; keep only the located copies.
    located = [p.message for p in found if p.target]
    found = [p for p in found if p.target or not any(m in p.message for m in located)]
    # Safety net: anything Project.validate rejects must be visible even if no collector above
    # names it.
    try:
        project.validate()
    except Exception as exc:  # noqa: BLE001
        text = str(exc)
        if not any(p.message in text or text in p.message for p in found):
            found.append(Problem("error", "Project", text))
    return found
