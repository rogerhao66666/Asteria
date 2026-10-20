"""The battle command menu counts the rows of its top-level commands and builds each category's
rows once per frame: the menu it shows is the same, frame by frame, as the one the row-by-row
builders gave (Full Verification boss fight: 124 skills, menu groups, Command Menu Pages)."""

import random
import sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import pytest

DEMO = Path(__file__).resolve().parents[1] / "reference_projects" / "full_verification_demo"
sys.path.insert(0, str(DEMO))

import run_trial_smoke as smoke  # noqa: E402

from asteria.presentation.battle_action_menu import (  # noqa: E402
    BattleActionEntry,
    BattleActionMenuRuntime,
)
from asteria.runtime.battle_commands import BattleCommands  # noqa: E402
from asteria.runtime.battle_presentation_adapters import CanonicalBattleAdapter  # noqa: E402

VESPER = "hero_03"
KEYS = ("up", "down", "down", "category", "confirm", "confirm", "cancel", "left", "right")


# -- the builders as they were: every row built, then counted --------------------------------
def _old_skill_rows(self, actor_id, category="Skills"):
    game, rows = self.game, []
    registry = game.battle.ability_runtime.registry
    known = game.battle.member(actor_id).ability_ids
    if self.style == "root":
        weapons = set(self.weapon_ability_ids(actor_id))
        known = tuple(a for a in known if a not in weapons)
    ordered = [a for a in self.labels if a in known] + [a for a in known if a not in self.labels]
    for ability_id in ordered:
        definition = registry.get(ability_id)
        if definition is None:
            continue
        if (getattr(definition, "menu_category", "") or "Skills") != category:
            continue
        reason = game.ability_unavailable(actor_id, ability_id)
        rows.append(
            BattleActionEntry(
                ability_id,
                self._name(ability_id),
                category=category,
                icon_asset_id=getattr(definition, "icon_id", "") or None,
                cost_text=self._work_out_cost_text(definition),
                enabled=not reason,
                disabled_reason=reason,
                detail=(
                    "Pick ingredients"
                    if definition.concoct_station
                    else getattr(definition, "description", "")
                ),
                order=len(rows),
            )
        )
    if category != "Skills":
        return rows
    capture = game.capture_targets()
    if capture:
        best = max(chance for _, chance, _ in capture)
        rows.append(
            BattleActionEntry(
                "capture", f"X  Capture ({best * 100:.0f}%)", category="Skills", order=len(rows)
            )
        )
    rules = game.rules
    if rules.boost_enabled and game.max_boost_level(actor_id) > 0:
        amount = game.battle.battle_resources.current(actor_id, rules.boost_resource_id)
        name = rules.boost_resource_id.replace("_", " ").title()
        rows.append(
            BattleActionEntry(
                "boost",
                f"Boost x{self.boost + 1}",
                category="Skills",
                cost_text=f"{name} {amount:g}",
                detail="Left / Right (or Enter here) set the boost for the next action",
                order=len(rows),
            )
        )
    return rows


def _old_root_rows(self, actor_id):
    weapons = self.attack_rows(actor_id)
    skills = [r for r in _old_skill_rows(self, actor_id) if r.action_id not in ("boost",)]
    items = self.item_rows()
    groups = [("Attack", len(weapons), "Choose a weapon")]
    groups.append(("Skills", len(skills), "Abilities, concoct, capture"))
    for name in self.custom_categories(actor_id):
        groups.append((name, len(_old_skill_rows(self, actor_id, name)), "Abilities"))
    groups.append(("Items", len(items), "Use an item from the bag"))
    run = self.game.escape_chance()
    if run is not None:
        groups.append(("Escape", 1, f"{round(run * 100)}% to get away"))
    if self.pages is not None:
        by_name = {g[0]: g for g in groups}
        groups = [by_name[name] for name in self._paged(by_name)]
        top = self.pages.max_primary_layers
        if len(groups) > top:
            if self.more:
                groups = groups[top - 1 :] + [("Back", 1, "The first commands")]
            else:
                groups = groups[: top - 1] + [("More", len(groups) - (top - 1), "More commands")]
    rows = []
    for category, count, hint in groups:
        shown = f"{round(run * 100)}%" if category == "Escape" else (str(count) if count else "")
        layer = self._layer(category)
        rows.append(
            BattleActionEntry(
                f"root:{category}",
                layer.label if layer is not None else category,
                category="Command",
                cost_text=shown,
                enabled=count > 0,
                disabled_reason="Nothing to use" if not count else "",
                detail=hint,
                order=len(rows),
            )
        )
    return rows


def _old_entries(self, actor_id):
    if self.mode == "root":
        rows = _old_root_rows(self, actor_id)
    elif self.mode == "command" and self.category not in ("Attack", "Items"):
        rows = _old_skill_rows(self, actor_id, self.category)
    else:
        rows = self.rows(actor_id)
    self.cursor = min(self.cursor, max(0, len(rows) - 1))
    return rows


def _old_show(menu, feedback, commands, actor):
    """``CanonicalBattleAdapter._show_commands`` as it was, from the menu policy on."""
    rows = _old_entries(commands, actor)
    if commands.mode == "root":
        menu.show(rows, "Command", commands.cursor)
    elif commands.mode == "command":
        everything = _old_skill_rows(commands, actor)
        for name in commands.custom_categories(actor):
            everything = everything + _old_skill_rows(commands, actor, name)
        everything = everything + commands.item_rows()
        if commands.style == "root":
            everything = commands.attack_rows(actor) + everything
        menu.show(everything, commands.category, commands.cursor)
    else:
        menu.show(rows, rows[0].category if rows else "Target", commands.cursor)
    target = rows[commands.cursor].action_id if commands.mode == "target" and rows else None
    feedback.target_ids, feedback.primary_target_id = ((target,), target) if target else ((), None)


# -- the menu each frame ---------------------------------------------------------------------
def _adapter(pages):
    feedback = SimpleNamespace(target_ids=(), primary_target_id=None)
    screen = SimpleNamespace(action_menu=BattleActionMenuRuntime(), camera_feedback=feedback)
    return SimpleNamespace(screen=screen, _command_pages=lambda: pages)


def _shown(fake):
    """Everything the menu holds and shows except ``revision``, and the target highlight."""
    menu, feedback = fake.screen.action_menu, fake.screen.camera_feedback
    view = menu.view
    shown = (view.categories, view.active_category, view.entries, view.page, view.page_count)
    held = (menu._source, menu.policy, view.total_count, view.cursor)
    return shown + held + (feedback.target_ids, feedback.primary_target_id)


def _frame(commands, actor, pages):
    """The menu the adapter shows now, and the one the old builders gave for the same state."""
    new, old = _adapter(pages), _adapter(pages)
    cursor = commands.cursor
    CanonicalBattleAdapter._show_commands(new, commands, actor)
    after, commands.cursor = commands.cursor, cursor
    CanonicalBattleAdapter._show_commands(old, commands, None)  # the same menu policy
    _old_show(old.screen.action_menu, old.screen.camera_feedback, commands, actor)
    assert commands.cursor == after
    return _shown(new), _shown(old)


def _game():
    _project, game = smoke.load()
    smoke.prepare(game, Counter(), "hero")
    game.join_party(VESPER)
    game.start_encounter("boss_room")
    return game


@pytest.mark.parametrize("style", ["root", "categories"])
@pytest.mark.parametrize("paged", [True, False])
def test_the_menu_is_the_same_frame_by_frame_as_the_row_by_row_builders(style, paged):
    game = _game()
    library = game.project.battle_presentation_library
    pages = library.require("interaction", "trial_commands") if paged else None
    some = game.battle.member(smoke.HERO).ability_ids[5:9]
    labels = {a: {"label": a.upper()} for a in reversed(some)}  # authored skills go first
    commands = BattleCommands(game, labels=labels, style=style, pages=pages)
    usable = next(
        i for i, item in sorted(game.project.rpg_database.items.items()) if item.battle_ability
    )
    rng, seen = random.Random(11), Counter()
    for step in range(260):
        if game.battle is None:
            break
        actor = (smoke.HERO, VESPER)[step // 130]
        if step == 40:  # the bag gets something to use
            game.save.rpg_state.inventory.add(usable, 2)
        if step == 80:  # out of technique: many skills turn disabled with a reason
            for hero in (smoke.HERO, VESPER):
                pool = game.battle.member(hero).subject.resources
                if pool.contains("technique"):
                    pool.set_current("technique", 0)
        if step == 130:
            commands.reset()
        if step % 17 == 16:  # a cursor past the rows (the open category lost some) is clamped
            commands.cursor += 50
        new, old = _frame(commands, actor, pages)
        assert new == old, (step, commands.mode, commands.category)
        seen[(commands.mode, commands.category)] += 1
        commands.press(rng.choice(KEYS), actor)
    modes = {mode for mode, _ in seen}
    assert "command" in modes and len({c for m, c in seen if m == "command"}) >= 3, seen
    if style == "root":
        assert "root" in modes


def test_root_rows_count_what_the_categories_open():
    game = _game()
    commands = BattleCommands(game, style="root")
    for actor in (smoke.HERO, VESPER):
        counts = {r.action_id: r.cost_text for r in commands.root_rows(actor)}
        assert counts == {r.action_id: r.cost_text for r in _old_root_rows(commands, actor)}
        groups = commands.command_rows(actor)
        assert counts["root:Combo"] == str(len(groups["Combo"]))
        skills = [r for r in groups["Skills"] if r.action_id != "boost"]
        assert counts["root:Skills"] == str(len(skills))


def test_cost_text_is_worked_out_again_for_a_replaced_definition():
    import dataclasses

    game = _game()
    commands = BattleCommands(game)
    registry = game.battle.ability_runtime.registry
    ability_id = next(
        a for a in game.battle.member(smoke.HERO).ability_ids if registry.get(a).battle_costs
    )
    definition = registry.get(ability_id)
    assert commands._cost_text(definition) == commands._work_out_cost_text(definition)
    changed = dataclasses.replace(definition, battle_costs={"boost_points": 9})
    assert "9" in commands._cost_text(changed)
    assert commands._cost_text(changed) == commands._work_out_cost_text(changed)
