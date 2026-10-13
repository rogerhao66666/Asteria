"""The player's battle commands (BTL / UI): every known ability, items, concocting, boost and
target choice.

``BattleCommands`` is the controller between the keyboard and ``GameSessionRuntime`` - no pygame
here, so
tests drive it directly. It produces ``BattleActionEntry`` rows for the canonical battle screen's
menu:

* **root** (``style="root"``, the Octopath-style menu) - a short vertical list: *Attack* (the
  weapons' attacks), *Skills*, *Items*; Enter opens one, Esc comes back to it.
* **command** - categories *Skills* and *Items* (Tab switches); Up / Down choose; Left / Right set
  the boost
  level; a row that cannot be used now is shown disabled with the reason (``ability_unavailable``).
* **ingredients** - a concoct ability asks for one item per recipe step of its station.
* **target** - Up / Down pick the target among the valid candidates (self-only and all-target
  actions skip
  this); Enter acts, Esc goes back one step.

``press(key)`` takes ``"up" | "down" | "left" | "right" | "confirm" | "cancel" | "category"`` and
returns
``True`` once an action was taken (the host then ends the turn).
"""

from __future__ import annotations

from asteria.presentation.battle_action_menu import BattleActionEntry
from asteria.rpg.targeting import TargetRelation

CATEGORIES = ("Skills", "Items")
ROOT_CATEGORIES = ("Attack", "Skills", "Items")


def _constant(formula):
    """The value of a formula made only of constant terms (costs as authored), else None."""
    terms = getattr(formula, "terms", ())
    if not terms or any(str(getattr(t.source, "value", t.source)) != "constant" for t in terms):
        return None
    return sum(t.coefficient for t in terms)


class BattleCommands:
    def __init__(self, game, *, labels=None, style="categories"):
        self.game = game
        self.labels = dict(labels or {})  # ability id -> {"label": ...} (manifest skills)
        self.style = "root" if style == "root" else "categories"
        self.reset()

    @property
    def categories(self):
        return ROOT_CATEGORIES if self.style == "root" else CATEGORIES

    def reset(self):
        self.mode = "root" if self.style == "root" else "command"
        self.category = self.categories[0] if self.style == "root" else CATEGORIES[0]
        self.cursor = 0
        self.boost = 0
        self.pending = None  # ("ability" | "item" | "concoct", id)
        self.ingredients = {}
        self.message = ""

    # -- what the menu shows ----------------------------------------------------------------------
    def _name(self, ability_id):
        meta = self.labels.get(ability_id) or {}
        return meta.get("label") or ability_id.replace("_", " ").title()

    def _short(self, resource_id):
        """A resource's short label: the battle HUD's (technique -> SP), else its first letters."""
        labels = getattr(self, "_labels", None)
        if labels is None:
            labels = self._labels = {}
            library = self.game.project.battle_presentation_library
            for hud_id in library.ids("hud"):
                for style in getattr(library.require("hud", hud_id), "resources", ()):
                    labels.setdefault(style.resource_id, style.label)
        return labels.get(resource_id) or resource_id.upper()[:3]

    def _cost_text(self, definition):
        parts = []
        for cost in definition.costs:
            amount = _constant(cost.amount)
            if amount:
                parts.append(f"{amount:g}{self._short(cost.resource)}")
        for resource_id, amount in definition.battle_costs.items():
            parts.append(f"{amount:g}{self._short(resource_id)}")
        if len(definition.hits) > 1:
            parts.append(f"x{len(definition.hits)}")
        return " ".join(parts)

    def weapon_ability_ids(self, actor_id):
        """The abilities the actor's equipped weapons give (the root menu's *Attack*)."""
        game = self.game
        loadout = game.save.rpg_state.loadouts.get(str(actor_id))
        if loadout is None:
            return ()
        known = set(game.battle.member(actor_id).ability_ids)
        found = []
        for item in loadout.equipped():
            for ability_id in item.equipment.granted_abilities:
                if ability_id in known and ability_id not in found:
                    found.append(ability_id)
        return tuple(found)

    def _ability_rows(self, actor_id, ability_ids, category):
        game, rows = self.game, []
        registry = game.battle.ability_runtime.registry
        for ability_id in ability_ids:
            definition = registry.get(ability_id)
            if definition is None:
                continue
            reason = game.ability_unavailable(actor_id, ability_id)
            rows.append(
                BattleActionEntry(
                    ability_id,
                    self._name(ability_id),
                    category=category,
                    cost_text=self._cost_text(definition),
                    enabled=not reason,
                    disabled_reason=reason,
                    order=len(rows),
                )
            )
        return rows

    def attack_rows(self, actor_id):
        """One row per weapon attack (root style's *Attack* category)."""
        return self._ability_rows(actor_id, self.weapon_ability_ids(actor_id), "Attack")

    def root_rows(self, actor_id):
        weapons = self.attack_rows(actor_id)
        skills = [r for r in self.skill_rows(actor_id) if r.action_id not in ("boost",)]
        items = self.item_rows()
        rows = []
        for category, count, hint in (
            ("Attack", len(weapons), "Choose a weapon"),
            ("Skills", len(skills), "Abilities, concoct, capture"),
            ("Items", len(items), "Use an item from the bag"),
        ):
            rows.append(
                BattleActionEntry(
                    f"root:{category}",
                    category,
                    category="Command",
                    cost_text=str(count) if count else "",
                    enabled=count > 0,
                    disabled_reason="Nothing to use" if not count else "",
                    detail=hint,
                    order=len(rows),
                )
            )
        return rows

    def skill_rows(self, actor_id):
        game, rows = self.game, []
        registry = game.battle.ability_runtime.registry
        known = game.battle.member(actor_id).ability_ids
        if self.style == "root":  # the weapons' attacks have their own category
            weapons = set(self.weapon_ability_ids(actor_id))
            known = tuple(a for a in known if a not in weapons)
        ordered = [a for a in self.labels if a in known] + [
            a for a in known if a not in self.labels
        ]
        for ability_id in ordered:  # the authored skills first (they are also on keys 1-4)
            definition = registry.get(ability_id)
            if definition is None:
                continue
            reason = game.ability_unavailable(actor_id, ability_id)
            rows.append(
                BattleActionEntry(
                    ability_id,
                    self._name(ability_id),
                    category="Skills",
                    cost_text=self._cost_text(definition),
                    enabled=not reason,
                    disabled_reason=reason,
                    detail="Pick ingredients" if definition.concoct_station else "",
                    order=len(rows),
                )
            )
        capture = game.capture_targets()
        if capture:
            best = max(chance for _, chance, _ in capture)
            rows.append(
                BattleActionEntry(
                    "capture",
                    f"X  Capture ({best * 100:.0f}%)",
                    category="Skills",
                    order=len(rows),
                )
            )
        game_rules = game.rules
        if game_rules.boost_enabled and game.max_boost_level(actor_id) > 0:
            amount = game.battle.battle_resources.current(actor_id, game_rules.boost_resource_id)
            name = game_rules.boost_resource_id.replace("_", " ").title()
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

    def item_rows(self):
        game, rows = self.game, []
        inventory = game.save.rpg_state.inventory
        for item_id, item in sorted(game.project.rpg_database.items.items()):
            count = inventory.count(item_id)
            if count <= 0 or not (item.battle_ability or item.use_effects):
                continue
            rows.append(
                BattleActionEntry(
                    item_id,
                    f"{item.display_name}",
                    category="Items",
                    cost_text=f"x{count}",
                    order=len(rows),
                )
            )
        return rows

    def _steps(self):
        station = self._definition(self.pending[1]).concoct_station
        steps = []
        for recipe in self.game.project.rpg_database.composition_recipes.values():
            if recipe.station == station:
                steps.extend(s.step_id for s in recipe.selections if s.step_id not in steps)
        return steps

    def ingredient_rows(self):
        step = self._steps()[len(self.ingredients)]
        station = self._definition(self.pending[1]).concoct_station
        inventory = self.game.save.rpg_state.inventory
        chosen = [i for values in self.ingredients.values() for i in values]
        ids = set()
        for recipe in self.game.project.rpg_database.composition_recipes.values():
            if recipe.station == station:
                for selection in recipe.selections:
                    if selection.step_id == step:
                        ids.update(selection.item_ids)
        rows = []
        for item_id in sorted(ids):
            left = inventory.count(item_id) - chosen.count(item_id)
            if left > 0:
                item = self.game.project.rpg_database.items.get(item_id)
                name = item.display_name if item else item_id
                rows.append(
                    BattleActionEntry(
                        item_id, name, category=step.title(), cost_text=f"x{left}", order=len(rows)
                    )
                )
        return rows

    def target_rows(self, actor_id):
        game = self.game
        battle = game.battle
        rows = []
        for member_id in self.candidates(actor_id):
            member = battle.member(member_id)
            name = self.display_name(member_id)
            pool = member.subject.resources
            hp = game.rules.knockout_resource_id
            detail = f"{pool.current(hp):g}" if pool.contains(hp) else ""
            rows.append(
                BattleActionEntry(
                    member_id, name, category="Target", cost_text=detail, order=len(rows)
                )
            )
        return rows

    def display_name(self, member_id):
        """The actor's or enemy's display name (several of one enemy are numbered)."""
        db = self.game.project.rpg_database
        key, _, number = str(member_id).partition(":")
        record = db.actors.get(key) or db.enemies.get(key)
        name = getattr(record, "display_name", None) or key.replace("_", " ").title()
        same = [m for m in self.game.battle.members if m.split(":", 1)[0] == key]
        return f"{name} {number}" if number and len(same) > 1 else name

    def rows(self, actor_id):
        if actor_id is None:
            return []
        if self.mode == "target":
            return self.target_rows(actor_id)
        if self.mode == "ingredients":
            return self.ingredient_rows()
        if self.mode == "root":
            return self.root_rows(actor_id)
        if self.category == "Attack":
            return self.attack_rows(actor_id)
        return self.skill_rows(actor_id) if self.category == "Skills" else self.item_rows()

    def entries(self, actor_id):
        rows = self.rows(actor_id)
        self.cursor = min(self.cursor, max(0, len(rows) - 1))
        return rows

    # -- targets ----------------------------------------------------------------------------------
    def _definition(self, ability_id):
        return self.game.battle.ability_runtime.registry.get(ability_id)

    def _action_ability(self):
        kind, key = self.pending
        if kind == "item":
            return self.game.project.rpg_database.items[key].battle_ability or None
        if kind == "concoct":
            return self._concoct_product_ability()
        return key

    def _concoct_product_ability(self):
        from asteria.rpg import CompositionRuntime

        station = self._definition(self.pending[1]).concoct_station
        recipes = [
            r
            for r in self.game.project.rpg_database.composition_recipes.values()
            if r.station == station
        ]
        recipe = CompositionRuntime(recipes).resolve(self.ingredients)
        if recipe is None or not recipe.outputs:
            return None
        item = self.game.project.rpg_database.items.get(recipe.outputs[0].item_id)
        return item.battle_ability if item is not None else None

    def candidates(self, actor_id):
        ability_id = self._action_ability()
        battle = self.game.battle
        if ability_id is None:  # a plain item: the acting side
            side = battle.member(actor_id).side
            return tuple(
                m.member_id
                for m in battle.members.values()
                if m.side == side and battle.is_active(m)
            )
        return tuple(
            m
            for m in battle.targeting.candidates(actor_id, ability_id)
            if battle.is_active(battle.member(m))
        )

    def _needs_target(self, actor_id):
        ability_id = self._action_ability()
        if ability_id is None:
            return True
        definition = self.game.battle.targeting.definition_for(ability_id)
        if definition is not None and definition.relation == TargetRelation.SELF:
            return False
        candidates = self.candidates(actor_id)
        maximum = 1 if definition is None else definition.maximum_targets
        return len(candidates) > 1 and maximum < len(candidates)

    # -- input ------------------------------------------------------------------------------------
    def press(self, key, actor_id):
        if actor_id is None:
            return False
        rows = self.entries(actor_id)
        if key in ("up", "down"):
            if rows:
                self.cursor = (self.cursor + (-1 if key == "up" else 1)) % len(rows)
            return False
        if key == "category" and self.mode == "command":
            cats = self.categories
            self.category = cats[(cats.index(self.category) + 1) % len(cats)]
            self.cursor = 0
            return False
        if key in ("boost_down", "boost_up") and self.mode in ("command", "root"):
            top = self.game.max_boost_level(actor_id) if self.game.rules.boost_enabled else 0
            self.boost = max(0, min(top, self.boost + (1 if key == "boost_up" else -1)))
            return False
        if key in ("left", "right") and self.mode in ("command", "root"):
            top = self.game.max_boost_level(actor_id) if self.game.rules.boost_enabled else 0
            self.boost = max(0, min(top, self.boost + (1 if key == "right" else -1)))
            return False
        if key == "cancel":
            if self.mode == "target" and self.pending and self.pending[0] == "concoct":
                self.ingredients.popitem() if self.ingredients else None
                self.mode = "ingredients"
            elif self.mode == "ingredients" and self.ingredients:
                self.ingredients.popitem()
            elif self.mode == "command" and self.style == "root":
                self.mode, self.cursor = "root", self.categories.index(self.category)
                return False
            elif self.mode == "root":
                return False
            else:
                self.mode, self.pending, self.ingredients = "command", None, {}
            self.cursor = 0
            return False
        if key != "confirm" or not rows:
            return False
        row = rows[self.cursor]
        if self.mode == "root":
            if not row.enabled:
                self.message = row.disabled_reason
                return False
            self.mode, self.category, self.cursor = (
                "command",
                row.action_id.split(":", 1)[1],
                0,
            )
            return False
        if self.mode == "command" and row.action_id == "capture" and self.category == "Skills":
            self.message = "capture"  # the host opens its capture prompt
            return False
        if self.mode == "command" and row.action_id == "boost" and self.category == "Skills":
            top = self.game.max_boost_level(actor_id)
            self.boost = 0 if self.boost >= top else self.boost + 1
            return False
        if self.mode == "command":
            if not row.enabled:
                self.message = row.disabled_reason
                return False
            if self.category == "Items":
                self.pending = ("item", row.action_id)
            elif self._definition(row.action_id).concoct_station:
                self.pending, self.ingredients, self.mode, self.cursor = (
                    ("concoct", row.action_id),
                    {},
                    "ingredients",
                    0,
                )
                return False
            else:
                self.pending = ("ability", row.action_id)
            return self._choose_target_or_act(actor_id)
        if self.mode == "ingredients":
            step = self._steps()[len(self.ingredients)]
            self.ingredients[step] = [row.action_id]
            self.cursor = 0
            if len(self.ingredients) < len(self._steps()):
                return False
            if self._concoct_product_ability() is None:
                self.message = "These ingredients make nothing"
                self.ingredients.popitem()
                return False
            return self._choose_target_or_act(actor_id)
        return self._act(actor_id, (row.action_id,))  # target mode

    def _choose_target_or_act(self, actor_id):
        if self._needs_target(actor_id):
            self.mode, self.cursor = "target", 0
            return False
        ability_id = self._action_ability()
        targets = None
        if ability_id is not None:
            definition = self.game.battle.targeting.definition_for(ability_id)
            if definition is None or definition.relation != TargetRelation.SELF:
                targets = self.candidates(actor_id)
        return self._act(actor_id, targets)

    def _act(self, actor_id, targets):
        game = self.game
        kind, key = self.pending
        try:
            if kind == "item":
                game.use_battle_item(actor_id, key, targets)
            elif kind == "concoct":
                game.concoct(actor_id, key, dict(self.ingredients), targets)
            else:
                game.use_ability(actor_id, key, targets, boost_level=self.boost)
        except Exception as exc:  # shown in the menu footer; the turn is not used
            self.message = str(exc)
            self.mode, self.cursor = ("root" if self.style == "root" else "command"), 0
            self.pending, self.ingredients = None, {}
            return False
        self.reset()
        return True

    def selected_target(self, actor_id):
        if self.mode != "target":
            return None
        rows = self.entries(actor_id)
        return rows[self.cursor].action_id if rows else None
