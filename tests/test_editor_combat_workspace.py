"""D22 A9: the Real-Time Combat workspace (attacks, projectiles, rarities, affixes with live previews), the scene
view's collider / hurtbox / hitbox overlay, and the Problems checks for real-time combat."""

import pytest

from asteria.core import Entity, Scene, Transform
from asteria.editor import EditorDocument
from asteria.editor.collision_overlay import build_combat_boxes
from asteria.editor.combat_authoring import KINDS, CombatAuthoringController, CombatAuthoringError
from asteria.editor.problems import collect_problems
from asteria.gameplay.action_timeline import ActionCue, ActionTimeline
from asteria.gameplay.attacks import AttackDefinition
from asteria.gameplay.projectiles import ProjectileDefinition
from asteria.project import Project
from asteria.rpg.behavior_tree import BehaviorNode, BehaviorTree
from asteria.runtime.action_combat import ActionCombatComponent
from asteria.runtime.character_control import CharacterController2DComponent, Hitbox2DComponent, Hurtbox2DComponent
from asteria.runtime.collision import Collider2DComponent
from asteria.runtime.combat import CombatantComponent


def _document():
    document = EditorDocument()
    document.set_project(Project("Combat"))
    return document


def test_every_kind_is_created_edited_duplicated_deleted_and_undone():
    document = _document()
    api = CombatAuthoringController(document)
    for spec in KINDS:
        api.create(spec.kind_id, "one")
        data = api.data(spec.kind_id, "one")
        data["display_name"] = "First"
        assert api.apply(spec.kind_id, "one", data).display_name == "First"
        api.create(spec.kind_id, "two", source="one")
        assert api.get(spec.kind_id, "two").display_name == "First"
        api.delete(spec.kind_id, "two")
        assert api.ids(spec.kind_id) == ("one",)
        with pytest.raises(CombatAuthoringError):
            api.create(spec.kind_id, "one")
        document.undo()  # the delete
        assert api.ids(spec.kind_id) == ("one", "two")
    with pytest.raises(CombatAuthoringError):
        api.apply("rarities", "one", dict(api.data("rarities", "one"), color="orange"))
    with pytest.raises(CombatAuthoringError):
        api.apply("attacks", "one", dict(api.data("attacks", "one"), attack_id="other"))
    library = document.project.gameplay_library
    library.add_timeline(ActionTimeline("swing", [ActionCue("h", 0, "hitbox", {"hit_tag": "one", "duration": 0.1})]))
    library.projectiles["one"] = ProjectileDefinition("one", attack_id="one")
    assert set(api.usage("attacks", "one")) == {"projectile one", "timeline swing"}


def test_the_workspace_form_edits_the_record_and_previews_live():
    QApplication = pytest.importorskip("PySide6.QtWidgets").QApplication
    from asteria.editor.combat_workspace import AttackPreview, CombatWorkspace, ProjectilePreview, RarityPreview

    qapp = QApplication.instance() or QApplication([])

    document = _document()
    document.project.gameplay_library.add_attack(AttackDefinition("slash"))
    widget = CombatWorkspace(document)
    widget.resize(1500, 900)
    widget.show()
    qapp.processEvents()
    assert widget.record_id == "slash" and isinstance(widget.preview, AttackPreview)
    widget.inputs["knockback"].setValue(240)
    widget.inputs["knockdown"].setChecked(True)
    formula = widget.inputs["damage"]
    formula.terms.add_row(["source_stat", "power", 0.8])
    formula.multipliers.add_row([2.0, "Element.Fire", "Creature.Plant"])
    formula.changed.emit()
    assert widget.preview.record.knockback == 240 and widget.preview.record.knockdown
    assert "Apply" in widget.status.text()
    widget.apply()
    attack = document.project.gameplay_library.attacks["slash"]
    assert attack.knockdown and attack.damage.terms[0].key == "power" and attack.damage.multipliers[0].multiplier == 2.0
    widget.show_kind("projectiles")
    assert widget.new_record("arrow") == "arrow" and isinstance(widget.preview, ProjectilePreview)
    widget.inputs["attack_id"].setCurrentText("slash")
    widget.inputs["homing_turn"].setValue(180)
    widget.apply()
    assert document.project.gameplay_library.projectiles["arrow"].attack_id == "slash"
    widget.show_kind("rarities")
    widget.new_record("mythic")
    widget.inputs["color"].set_color("#ff3355")
    widget.inputs["max_affixes"].setValue(6)
    widget.inputs["min_affixes"].setValue(7)  # more than the maximum: refused with the reason
    assert "affix" in widget.status.text().lower()
    widget.inputs["min_affixes"].setValue(5)
    widget.apply()
    assert (
        isinstance(widget.preview, RarityPreview)
        and document.project.rpg_database.rarities["mythic"].color == "#ff3355"
    )
    widget.show_kind("affixes")
    widget.new_record("of_fire")
    widget.inputs["modifiers"].add_row(["fire", "add", 2, 6, True, 1])
    widget.inputs["modifiers"].changed.emit()
    widget.apply()
    assert document.project.rpg_database.affixes["of_fire"].modifiers[0].per_level == 1
    for kind in ("attacks", "projectiles", "rarities", "affixes"):  # every preview paints
        widget.show_kind(kind)
        image = widget.preview.grab()
        assert not image.isNull()
    widget.select_id("of_fire")
    widget.delete_record(confirm=False)
    assert "of_fire" not in document.project.rpg_database.affixes


def test_the_scene_view_outlines_colliders_hurtboxes_and_facing_hitboxes():
    from asteria.editor.viewport import ViewportCamera

    scene = Scene("S")
    hero = scene.add_entity(Entity("Hero"))
    hero.add_component(Transform(0, 0))
    hero.add_component(CharacterController2DComponent()).facing = "left"
    hit = hero.add_component(Hitbox2DComponent())
    hit.width, hit.height, hit.offset_x, hit.follow_facing = 20, 10, 15, True
    hero.add_component(Hurtbox2DComponent())
    for name, fields in (
        ("Ramp", {"shape": "slope_right"}),
        ("Ladder", {"ladder": True}),
        ("Ledge", {"one_way": True}),
    ):
        e = scene.add_entity(Entity(name))
        e.add_component(Transform(50, 0))
        collider = e.add_component(Collider2DComponent())
        for k, v in fields.items():
            setattr(collider, k, v)
    boxes = build_combat_boxes(scene, ViewportCamera())
    kinds = sorted(b.kind for b in boxes)
    assert kinds == ["hitbox", "hurtbox", "ladder", "one_way", "slope_right"]
    hitbox = next(b for b in boxes if b.kind == "hitbox")
    assert max(x for x, _ in hitbox.points) < 0  # facing left: the box reaches left
    assert len(next(b for b in boxes if b.kind == "slope_right").points) == 3


def test_problems_name_broken_real_time_combat_references():
    document = _document()
    project = document.project
    library = project.gameplay_library
    library.add_attack(AttackDefinition("bite", damage_formula_id="missing", apply_states=[{"state": "nope"}]))
    library.add_projectile(ProjectileDefinition("dart", attack_id="ghost"))
    library.add_timeline(
        ActionTimeline(
            "bad",
            [
                ActionCue("p", 0, "projectile", {"projectile_id": "none"}),
                ActionCue("c", 0, "combo_window", {"duration": 0.1, "next": "lost"}),
                ActionCue("h", 0, "hitbox", {"hit_tag": "custom", "duration": 0.1}),
            ],
        )
    )
    project.rpg_database.add_behavior_tree(
        BehaviorTree("brain", BehaviorNode("selector", {}, (BehaviorNode("use_ability", {"ability": "zap"}),)))
    )
    scene = project.create_scene("Arena") if hasattr(project, "create_scene") else None
    if scene is None:
        scene = Scene("Arena")
        project.add_scene(scene)
    fighter = scene.add_entity(Entity("Fighter"))
    fighter.add_component(Transform())
    fighter.add_component(ActionCombatComponent()).bindings = "attack=nothing"
    combatant = fighter.add_component(CombatantComponent())
    combatant.resources, combatant.drop_table_id = "mana=5", "no_table"
    messages = {p.message: p for p in collect_problems(document) if p.area == "Real-Time Combat"}
    text = " | ".join(messages)
    for expected in (
        "shared formula missing",
        "state nope not found",
        "attack ghost not found",
        "projectile none not found",
        "unknown timeline lost",
        "hit tag custom is not an attack",
        "unknown ability zap",
        "unknown ability nothing",
        "drop table no_table not found",
        "life resource hp is not among its resources",
    ):
        assert expected in text, expected
    located = next(p for m, p in messages.items() if "attack ghost" in m)
    assert located.target == ("combat", "projectiles", "dart") and located.location == "projectiles / dart"
    warning = next(p for m, p in messages.items() if "hit tag custom" in m)
    assert warning.severity == "warning"
