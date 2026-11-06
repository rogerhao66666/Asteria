"""D22 A9: the Real-Time Combat workspace (attacks, projectiles, rarities, affixes with live
previews), the scene
view's collider / hurtbox / hitbox overlay, and the Problems checks for real-time combat."""

from pathlib import Path

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
from asteria.runtime.character_control import (
    CharacterController2DComponent,
    Hitbox2DComponent,
    Hurtbox2DComponent,
)
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
    library.add_timeline(
        ActionTimeline("swing", [ActionCue("h", 0, "hitbox", {"hit_tag": "one", "duration": 0.1})])
    )
    library.projectiles["one"] = ProjectileDefinition("one", attack_id="one")
    assert set(api.usage("attacks", "one")) == {"projectile one", "timeline swing"}


def test_the_workspace_form_edits_the_record_and_previews_live():
    QApplication = pytest.importorskip("PySide6.QtWidgets").QApplication
    from asteria.editor.attack_preview import sample_damage
    from asteria.editor.combat_workspace import (
        AttackPreview,
        CombatWorkspace,
        ProjectilePreview,
        RarityPreview,
    )

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
    assert sample_damage(widget.preview.record, widget.preview.formulas) == (80, True)
    assert "Apply" in widget.status.text()
    widget.apply()
    attack = document.project.gameplay_library.attacks["slash"]
    assert (
        attack.knockdown
        and attack.damage.terms[0].key == "power"
        and attack.damage.multipliers[0].multiplier == 2.0
    )
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
    library.add_attack(
        AttackDefinition("bite", damage_formula_id="missing", apply_states=[{"state": "nope"}])
    )
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
        BehaviorTree(
            "brain",
            BehaviorNode("selector", {}, (BehaviorNode("use_ability", {"ability": "zap"}),)),
        )
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
        "hit property custom is not an attack",
        "Behavior tree Brain: the skill Zap is not in the project",
        "unknown ability nothing",
        "drop table no_table not found",
        "life resource hp is not among its resources",
    ):
        assert expected in text, expected
    located = next(p for m, p in messages.items() if "attack ghost" in m)
    assert (
        located.target == ("combat", "projectiles", "dart")
        and located.location == "projectiles / dart"
    )
    warning = next(p for m, p in messages.items() if "hit property custom" in m)
    assert warning.severity == "warning"


def test_the_record_actions_sit_at_the_foot_and_the_completion_list_closes_with_its_page():
    QtWidgets = pytest.importorskip("PySide6.QtWidgets")
    from asteria.editor.code_workspace import CodeWorkspaceWidget
    from asteria.editor.combat_workspace import CombatWorkspace

    qapp = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    document = _document()
    document.project.gameplay_library.add_attack(AttackDefinition("slash"))
    widget = CombatWorkspace(document)
    widget.resize(900, 700)  # narrow: the left column gets the least width it is given
    widget.show()
    qapp.processEvents()
    for button in (widget.new_button, widget.duplicate_button, widget.delete_button):
        needed = button.fontMetrics().horizontalAdvance(button.text())
        assert button.width() >= needed + 12, button.text()  # the whole label is visible
    # at the page's foot, right of Undo / Redo, as on every record page
    undo = widget.findChild(QtWidgets.QPushButton, "FormUndoButton")
    at = undo.mapTo(widget, undo.rect().topLeft())  # inside the Undo / Redo pair
    assert undo is not None and abs(widget.new_button.y() - at.y()) <= 4  # one row
    assert at.x() < widget.new_button.x() < widget.duplicate_button.x()
    assert widget.duplicate_button.x() < widget.delete_button.x()
    assert "Attack" in widget.new_button.toolTip()
    widget.close()

    code = CodeWorkspaceWidget(document)
    code.show()
    code.editor.setPlainText("ent")
    cursor = code.editor.textCursor()
    cursor.movePosition(cursor.MoveOperation.End)
    code.editor.setTextCursor(cursor)
    code.show_completions()
    qapp.processEvents()
    code.hide()  # switching to another workspace
    qapp.processEvents()
    assert not code.completer.popup().isVisible()
    code.close()


def _hit(**values):
    return AttackDefinition("hit", **values)


def test_the_attack_preview_plays_the_hit_by_this_attacks_numbers():
    from asteria.editor.attack_preview import attacker_state, plan_for, target_state

    plan = plan_for(_hit(hitstop=0.2, hitstun=0.5, knockback=300, target_iframes=1.0))
    assert target_state(plan, plan.hit_at - 0.01).sheet == "idle"
    assert attacker_state(plan, plan.hit_at - 0.01).sheet == "swing"
    # both hold still through the freeze, the sword out and the target white
    frozen = target_state(plan, plan.moves_at - 0.01)
    assert frozen.flash and frozen.x == 0
    assert (
        attacker_state(plan, plan.hit_at).frame == attacker_state(plan, plan.moves_at - 0.01).frame
    )
    # then the push fades towards speed / decay, and the stun runs from there
    moving = target_state(plan, plan.moves_at + 0.1)
    assert moving.sheet == "hurt" and 0 < moving.x < plan.push_distance == 30
    assert target_state(plan, plan.moves_at + 0.6).sheet == "idle"
    assert plan.total > plan.hit_at + 1.0
    assert any(target_state(plan, plan.hit_at + 0.3 + i / 100).faint for i in range(10))
    # a knock-down replaces the stun: down for its time, then up again; a lift falls back
    down = plan_for(_hit(hitstun=9.0, knockdown=True, knockdown_time=0.8, knockback_lift=120))
    assert down.stun == 0 and down.down == 0.8 and down.lift == 120
    assert target_state(down, down.moves_at + 0.1).height > 0
    lying = target_state(down, down.moves_at + 0.7)
    assert (lying.sheet, lying.height) == ("down", 0)
    assert target_state(down, down.moves_at + 1.0).sheet == "down"
    assert target_state(down, down.moves_at + 1.4).sheet == "idle"
    # the angle turns the push: straight up is all lift, and it can come back at the swordsman
    assert abs(plan_for(_hit(knockback=100, knockback_angle=-90)).push) < 1e-6
    assert plan_for(_hit(knockback=100, knockback_angle=-90)).lift == 100
    assert plan_for(_hit(knockback=100, knockback_angle=180)).push_distance == -10


def test_the_attack_preview_shows_a_sample_of_the_damage_or_says_there_is_none():
    from asteria.editor.attack_preview import sample_damage
    from asteria.gameplay.formulas import ValueFormula

    assert sample_damage(_hit(), {}) == (None, False)
    assert sample_damage(_hit(damage=ValueFormula.constant(25)), {}) == (25, False)
    shared = _hit(damage_formula_id="f")
    assert sample_damage(shared, {"f": ValueFormula.constant(7)}) == (7, False)
    assert sample_damage(shared, {}) == (None, False)


def test_the_attack_preview_runs_only_while_seen_and_draws_without_the_art():
    QApplication = pytest.importorskip("PySide6.QtWidgets").QApplication
    from asteria.editor import attack_preview
    from asteria.editor.attack_preview import AttackPreview, plan_for

    qapp = QApplication.instance() or QApplication([])
    preview = AttackPreview()
    attack = _hit(hitstop=0.1, knockback=200, knockdown=True)
    preview.show_record(attack)
    preview.resize(380, 560)
    preview.show()
    qapp.processEvents()
    assert preview._timer.isActive()
    preview._tick()
    assert preview.time > 0
    preview.slow_check.setChecked(True)
    before = preview.time
    preview._tick()
    assert preview.time - before == pytest.approx(0.033 * attack_preview.SLOW)
    preview.seek(plan_for(attack).total - 0.001)
    preview._tick()
    assert preview.time < 0.1  # it loops
    preview._toggle_play()
    assert not preview._timer.isActive() and preview.play_button.text() == "Play"
    preview._toggle_play()
    assert preview._timer.isActive() and preview.play_button.text() == "Pause"
    preview.hide()
    assert not preview._timer.isActive()
    # another attack starts from its beginning; an edit of this one keeps playing where it is
    preview.seek(0.7)
    preview.show_record(_hit(hitstop=0.3))
    assert preview.time == 0.7
    preview.show_record(AttackDefinition("other"))
    assert preview.time == 0
    # with the art pack missing the same motion is drawn with stand-ins
    saved = dict(attack_preview._sprites)
    attack_preview._sprites.clear()
    real = attack_preview.find_pack
    attack_preview.find_pack = lambda name: Path("no such pack")
    try:
        preview.show_record(attack)
        for moment in (0.1, 0.5, 0.9, 1.5):
            preview.seek(moment)
            assert not preview.grab().isNull()
        assert attack_preview._sprites[("target", "idle")] is None
    finally:
        attack_preview.find_pack = real
        attack_preview._sprites.clear()
        attack_preview._sprites.update(saved)
    preview.show_record(None)
    assert not preview.grab().isNull()


def test_combat_fields_are_picked_and_keep_values_not_on_the_list():
    QApplication = pytest.importorskip("PySide6.QtWidgets").QApplication
    from asteria.editor.combat_workspace import CombatWorkspace
    from asteria.editor.record_form import ChipList
    from asteria.gameplay.projectiles import ProjectileDefinition as Shot

    qapp = QApplication.instance() or QApplication([])
    document = _document()
    library = document.project.gameplay_library
    library.add_attack(AttackDefinition("slash", "Big Slash", on_hit_event="old_event"))
    library.projectiles["arrow"] = Shot("arrow", attack_id="gone", wall_mask=0b101)
    widget = CombatWorkspace(document)
    widget.resize(1500, 900)
    widget.show()
    qapp.processEvents()
    # an empty value reads in words; a name no list has stays, ready to apply unchanged
    assert widget.inputs["damage_resource"].itemText(0) == "The target's life"
    assert widget.inputs["on_hit_event"].currentText() == "old_event"
    assert isinstance(widget.inputs["tags"], ChipList)
    widget.inputs["tags"].values = ["Element.Fire"]
    widget.inputs["tags"].edited.emit()
    assert widget.preview.record.tags == ("element.fire",)
    widget.apply()
    assert library.attacks["slash"].on_hit_event == "old_event"
    # the formula's reads follow its source; a constant reads nothing
    formula = widget.inputs["damage"]
    formula.terms.add_row()
    cell = formula.terms.table.cellWidget(0, 1).field
    assert not cell.isEnabled()
    source = formula.terms.table.cellWidget(0, 0).field
    source.setCurrentIndex(source.findData("source_stat"))
    assert cell.isEnabled()

    widget.show_kind("projectiles")
    assert widget.inputs["attack_id"].currentText() == "gone"
    widget.inputs["attack_id"].setCurrentText("slash")
    assert widget.inputs["attack_id"].itemText(widget.inputs["attack_id"].currentIndex()) == (
        "Big Slash"
    )
    # the wall layers are ticked; layers past the menu's end stay as they are
    layers = widget.inputs["wall_mask"]
    assert layers.value == 0b101 and layers.text() == "Layer 1, 3"
    layers.layers[1].setChecked(True)
    assert widget.preview.record.wall_mask == 0b111
    layers.set_value(0xFFFFFFFF)
    assert layers.text() == "Every layer"
    layers.layers[0].setChecked(False)
    assert layers.value == 0xFFFFFFFE


def test_a_damage_formula_keeps_its_exact_numbers_through_the_form():
    QApplication = pytest.importorskip("PySide6.QtWidgets").QApplication
    from asteria.editor.combat_workspace import FormulaEditor

    QApplication.instance() or QApplication([])
    editor = FormulaEditor()
    editor.terms.add_row(["source_stat", "power", 1.278])
    assert editor.terms.rows()[0] == ["source_stat", "power", 1.278]
    assert editor.terms.table.cellWidget(0, 2).field.text() == "1.278"


def test_the_swing_is_a_cut_from_above_and_always_shows_the_slash():
    from asteria.editor import attack_preview as ap

    # the swordsman stands on the right: facing left the art comes down as drawn
    assert ap.SHEETS[("attacker", "swing")][1] == "Left/Png/WarriorLeftAttack01.png"
    assert ap.SHEETS[("target", "idle")][1] == "Right/Png/SkeletonWithSwordRightIdle.png"
    for attack in (_hit(), _hit(hitstop=0.2)):
        plan = ap.plan_for(attack)
        steps = int((plan.moves_at + ap.FOLLOW - ap.LEAD) / 0.01)
        frames = []
        for step in range(steps):
            figure = ap.attacker_state(plan, ap.LEAD + step * 0.01)
            if figure.sheet == "swing" and (not frames or frames[-1] != figure.frame):
                frames.append(figure.frame)
        assert frames == [0, 1, 2, 3, 4, 5]
        assert ap.attacker_state(plan, plan.hit_at).frame == ap.SWING_HIT_FRAME
    # it steps in for the blow, and is back where it started when the swing is over
    plan = ap.plan_for(_hit())
    assert ap.attacker_state(plan, ap.LEAD - 0.01).x == 0
    assert ap.attacker_state(plan, plan.hit_at).x == ap.LUNGE
    assert ap.attacker_state(plan, plan.moves_at + ap.FOLLOW).x == 0


def test_a_long_stun_flinches_red_then_stands_dazed_and_a_pushed_monster_fades_back():
    from asteria.editor import attack_preview as ap

    plan = ap.plan_for(_hit(hitstun=2.0, knockback=100))
    flinch = ap.target_state(plan, plan.moves_at + 0.02)
    assert flinch.sheet == "hurt" and not flinch.dazed
    dazed = ap.target_state(plan, plan.moves_at + 1.0)
    assert (dazed.sheet, dazed.frame, dazed.dazed) == ("idle", 0, True)
    assert not ap.target_state(plan, plan.moves_at + 2.1).dazed
    assert ap.target_fade(plan, 0.0) == 0 and ap.target_fade(plan, plan.total) == 0
    assert ap.target_fade(plan, 1.0) == 1
    still = ap.plan_for(_hit(hitstun=2.0))
    assert ap.target_fade(still, 0.0) == 1  # it never left


def test_the_attack_preview_names_the_attack_and_every_setting_shows():
    QApplication = pytest.importorskip("PySide6.QtWidgets").QApplication
    from asteria.editor.attack_preview import AttackPreview

    qapp = QApplication.instance() or QApplication([])
    preview = AttackPreview()
    preview.resize(380, 520)
    preview.names = {"luk": "Luck", "mp": "MP"}
    preview.show_record(AttackDefinition("a", display_name="First"))
    preview.time = 0.1
    qapp.processEvents()
    first = preview.grab().toImage()
    preview.show_record(AttackDefinition("b", display_name="Second"))
    preview.time = 0.1
    qapp.processEvents()
    assert preview.grab().toImage() != first  # the same numbers, but it says which attack

    def words(**values):
        attack = _hit(**values)
        return " | ".join(text for text, _color in preview._chips(attack, None, False))

    assert "Crit 10% ×1.5" in words(critical_chance=0.1)
    assert "Crit 0% + Luck ×2" in words(critical_chance_stat="luk", critical_multiplier=2.0)
    assert "Lowers MP" in words(damage_resource="mp")
    assert "Targets ≤ 3" in words(max_targets=3)
    assert "On Hit: boom" in words(on_hit_event="boom")
    assert "Push 100/s 30°" in words(knockback=100, knockback_angle=30)
    assert "Fixed direction" in words(knockback=100, knockback_direction="fixed")
    assert "Freezes the whole game" in words(hitstop=0.1, hitstop_scope="global")
    assert "Freezes" not in words(hitstop=0.1)
    assert "Weapon: Ring" in words(tags=("capability.weapon.ring",))
    preview.close()


def test_an_attack_a_projectile_carries_is_thrown_at_the_shots_real_speed():
    from asteria.editor import attack_preview as ap
    from asteria.gameplay.projectiles import ProjectileDefinition as Shot

    stone = Shot("stone", attack_id="hit", speed=220.0, lifetime=0.7, width=6.0, height=6.0)
    plan = ap.plan_for(_hit(hitstop=0.1), stone)
    assert plan.shot.distance == ap.THROW_DISTANCE
    assert plan.shot.flight == pytest.approx(ap.THROW_DISTANCE / 220)
    assert plan.hit_at == pytest.approx(ap.LEAD + ap.THROW_WINDUP + plan.shot.flight)
    assert plan.spacing > ap.REACH  # from afar
    # the hand goes up with no slash drawn, and it never steps in
    frames = {ap.attacker_state(plan, plan.released_at + i / 100) for i in range(-30, 80)}
    assert all(f.x == 0 for f in frames)
    assert ap.SWING_HIT_FRAME not in {f.frame for f in frames if f.sheet == "swing"}
    # the shot flies from the hand to the monster's chest, and the blow lands when it arrives
    assert ap.shot_state(plan, plan.released_at - 0.01) is None
    assert ap.shot_state(plan, plan.released_at)[0] == 0
    flown, height, _angle = ap.shot_state(plan, plan.hit_at - 0.001)
    assert flown == pytest.approx(ap.THROW_DISTANCE, abs=0.3) and height == ap.CHEST_HEIGHT
    assert ap.shot_state(plan, plan.hit_at) is None
    assert plan.spacing + ap.HAND - plan.shot.distance == ap.TARGET_CHEST
    assert not ap.target_state(plan, plan.hit_at - 0.01).flash
    assert ap.target_state(plan, plan.hit_at).flash
    # a swing is as it was
    assert ap.plan_for(_hit()).shot is None and ap.plan_for(_hit()).spacing == ap.REACH


def test_a_shot_starts_only_as_far_as_it_can_arrive_from():
    from asteria.editor import attack_preview as ap
    from asteria.gameplay.projectiles import ProjectileDefinition as Shot

    short = ap.shot_path(Shot("s", speed=100.0, lifetime=0.3))
    assert short.distance == pytest.approx(30) and short.flight == pytest.approx(0.3)
    assert ap.shot_path(Shot("s", speed=0.0)).flight == 0
    # gravity bends it, and the monster stands where it still meets the falling shot
    lobbed = ap.shot_path(Shot("s", speed=220.0, lifetime=2.0, gravity=600.0))
    assert lobbed.distance < ap.THROW_DISTANCE
    assert lobbed.rise(lobbed.flight) == pytest.approx(ap.CHEST_HEIGHT - ap.BODY_REACH)
    plan = ap.plan_for(_hit(), Shot("s", speed=220.0, lifetime=2.0, gravity=600.0))
    assert plan.hit_height == pytest.approx(ap.CHEST_HEIGHT - ap.BODY_REACH)
    assert ap.shot_state(plan, plan.hit_at - 0.01)[2] != 180  # it turns as it falls
    still = ap.plan_for(_hit(), Shot("s", gravity=600.0, align_to_velocity=False))
    assert ap.shot_state(still, still.released_at + 0.01)[2] == 0


def test_the_preview_throws_the_first_carrier_and_names_them_all():
    QApplication = pytest.importorskip("PySide6.QtWidgets").QApplication
    from PySide6.QtGui import QPixmap

    from asteria.editor.attack_preview import AttackPreview
    from asteria.gameplay.projectiles import ProjectileDefinition as Shot

    qapp = QApplication.instance() or QApplication([])
    preview = AttackPreview()
    preview.resize(380, 520)
    attack = _hit()
    alone = preview._plan(attack)
    assert alone.shot is None
    preview.projectiles = {
        "zed": Shot("zed", "Zed", attack_id="hit", speed=50.0),
        "arrow": Shot("arrow", "Arrow", attack_id="hit", speed=300.0, sprite="sheet"),
        "other": Shot("other", attack_id="something else", speed=10.0),
    }
    assert preview._plan(attack).shot.speed == 300  # the same one every time
    assert "Projectile: Arrow, Zed" in [text for text, _ in preview._chips(attack, None, False)]
    asked = []

    def picture(sprite):
        asked.append(sprite)
        return QPixmap(8, 4)

    preview.shot_picture = picture
    preview.show_record(attack)
    qapp.processEvents()
    plan = preview._plan(attack)
    swung = preview.grab().toImage()
    preview.seek(plan.released_at + plan.shot.flight / 2)
    assert not preview.grab().isNull()
    assert preview.grab().toImage() != swung
    preview.seek(plan.released_at + plan.shot.flight / 3)
    assert not preview.grab().isNull()
    assert asked == ["sheet"]  # read once
    # no sprite: a small box; a sprite that can't be read: the same box
    preview.shot_picture = lambda _sprite: None
    preview._shot_pictures.clear()
    assert preview._shot_picture("sheet") is None and preview._shot_picture("") is None
    assert not preview.grab().isNull()
    preview.close()


def test_a_state_shows_as_a_chip_and_only_an_empty_hit_says_it_does_nothing():
    QApplication = pytest.importorskip("PySide6.QtWidgets").QApplication
    from asteria.editor.attack_preview import AttackPreview, sample_damage
    from asteria.gameplay.formulas import ValueFormula

    QApplication.instance() or QApplication([])
    preview = AttackPreview()
    preview.state_names = {"blind": "Blind"}

    def words(**values):
        return [text for text, _ in preview._chips(_hit(**values), None, False)]

    def nothing(**values):
        attack = _hit(**values)
        damage = sample_damage(attack, {})[0]
        return preview._nothing_happens(attack, preview._plan(attack), damage)

    timed = {"state": "blind", "chance": 1.0, "duration": 3.0}
    assert "Blind 100% 3s" in words(apply_states=(timed,))
    # no time of its own: the state's lasts; a state the list doesn't know keeps its id
    assert "Poison 25%" not in words(apply_states=({"state": "poison", "chance": 0.25},))
    assert "poison 25%" in words(apply_states=({"state": "poison", "chance": 0.25},))
    assert nothing()
    assert words() == []
    for values in (
        {"apply_states": (timed,)},
        {"damage_resource": "mp"},
        {"critical_chance": 0.1},
        {"critical_chance_stat": "luk"},
        {"max_targets": 2},
        {"armor_break": 1},
        {"poise_damage": 5.0},
        {"on_hit_event": "boom"},
        {"tags": ("weak.fire",)},
        {"knockback": 50.0},
        {"knockback_lift": 50.0},
        {"knockdown": True},
        {"hitstop": 0.1},
        {"hitstun": 0.1},
        {"target_iframes": 0.1},
        {"damage": ValueFormula.constant(5)},
    ):
        assert not nothing(**values), values
    # settings that change nothing while what they qualify is empty stay quiet
    assert nothing(hitstop_scope="global", critical_multiplier=3.0, knockback_angle=30.0)
    assert "No damage" in words(on_hit_event="boom")
    assert "No damage" not in words()
    preview.close()


def test_the_workspace_gives_the_preview_its_projectiles_and_state_names():
    QApplication = pytest.importorskip("PySide6.QtWidgets").QApplication
    from asteria.editor.attack_preview import AttackPreview
    from asteria.editor.combat_workspace import CombatWorkspace
    from asteria.gameplay.projectiles import ProjectileDefinition as Shot

    qapp = QApplication.instance() or QApplication([])
    document = _document()
    library = document.project.gameplay_library
    library.add_attack(AttackDefinition("slash", "Slash"))
    library.add_attack(AttackDefinition("stone_hit", "Stone Hit"))
    library.projectiles["stone"] = Shot("stone", "Stone", attack_id="stone_hit", speed=220.0)
    widget = CombatWorkspace(document)
    widget.resize(1500, 900)
    widget.show()
    qapp.processEvents()
    assert isinstance(widget.preview, AttackPreview)
    widget.select_id("slash")
    assert widget.preview._plan(widget.preview.record).shot is None
    widget.select_id("stone_hit")
    assert widget.preview._plan(widget.preview.record).shot.speed == 220
    assert widget.preview.shot_picture("") is None
    widget.close()


def test_pause_sits_right_under_the_stage_with_room_around_it():
    QApplication = pytest.importorskip("PySide6.QtWidgets").QApplication
    from asteria.editor.attack_preview import AttackPreview, plan_for
    from asteria.gameplay.projectiles import ProjectileDefinition

    qapp = QApplication.instance() or QApplication([])
    preview = AttackPreview()
    for attack in (_hit(), _hit(hitstop=0.1, hitstun=0.5, knockdown=True, target_iframes=0.5)):
        for height in (320, 500, 900):
            preview.resize(380, height)
            preview.show_record(attack)
            qapp.processEvents()
            layout = preview._layout(attack)
            box = preview.controls.geometry()
            assert box.top() == round(layout.ground + 10)
            assert box.bottom() < layout.bars <= height
            assert preview.play_button.pos().x() >= 12
            assert (
                layout.bars + len(preview._bar_rows(plan_for(attack))) * preview.BAR_ROW <= height
            )
    # a throw needs a wider stage, and its controls follow as soon as the record is shown again
    swung = preview._layout(_hit()).scale
    preview.projectiles = {"s": ProjectileDefinition("s", attack_id="hit", speed=220.0)}
    assert preview._layout(_hit()).scale < swung
    preview.show_record(_hit())
    assert preview.controls.geometry().top() == round(preview._layout(_hit()).ground + 10)
    preview.close()
