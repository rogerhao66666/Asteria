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
* **steps** - an ability with Command Input Steps (``input_workflow``) asks each step's
  options in turn (a multiple-choice step toggles and ends on *Done*).
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
    def __init__(self, game, *, labels=None, style="categories", pages=None):
        self.game = game
        self.labels = dict(labels or {})  # ability id -> {"label": ...} (manifest skills)
        self.style = "root" if style == "root" else "categories"
        # Command Menu Pages (BattleInteractionProfile): its layers order, rename and hide the
        # top-level commands (layer_id = the command); past max_primary_layers they move to a
        # More page
        self.pages = pages
        self.reset()

    @property
    def categories(self):
        return ROOT_CATEGORIES if self.style == "root" else CATEGORIES

    BUILT_IN = ("Attack", "Skills", "Items")

    def custom_categories(self, actor_id):
        """Menu groups the actor's abilities ask for with ``menu_category`` (first use order)."""
        registry = self.game.battle.ability_runtime.registry
        found = []
        for ability_id in self.game.battle.member(actor_id).ability_ids:
            definition = registry.get(ability_id)
            name = getattr(definition, "menu_category", "") if definition is not None else ""
            if name and name not in self.BUILT_IN and name not in found:
                found.append(name)
        return tuple(found)

    def categories_for(self, actor_id):
        """The command categories to cycle for this actor: the built-in ones, then the
        project's own ``menu_category`` groups (before Items in the categories style)."""
        base = self.categories
        custom = self.custom_categories(actor_id)
        if not custom:
            return base
        head = tuple(c for c in base if c != "Items")
        return self._paged(head + custom + (("Items",) if "Items" in base else ()))

    def _layer(self, name):
        layers = getattr(self.pages, "layers", ()) if self.pages is not None else ()
        return next((x for x in layers if x.layer_id == name), None)

    def _paged(self, names):
        """Command names in the order the Command Menu Pages give (unlisted ones after, as they
        came), without the hidden or contextual ones."""
        if self.pages is None:
            return tuple(names)
        kept = []
        for index, name in enumerate(names):
            layer = self._layer(name)
            if layer is not None and (not layer.visible or layer.contextual):
                continue
            kept.append(((0, layer.order) if layer is not None else (1, index), name))
        return tuple(name for _, name in sorted(kept, key=lambda x: x[0]))

    def reset(self):
        self.mode = "root" if self.style == "root" else "command"
        self.category = self.categories[0] if self.style == "root" else CATEGORIES[0]
        self.cursor = 0
        self.boost = 0
        self.pending = None  # ("ability" | "item" | "concoct", id)
        self.form = None  # the casting form picked for a skill that has forms
        self.ingredients = {}
        self.message = ""
        self.more = False  # the root list shows the commands past max_primary_layers
        self.choices = {}  # step id -> chosen option ids (Command Input Steps)

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
        # Ability definitions are frozen, so each one's text is worked out once (the menu asks on
        # every frame); the definition is kept with it so a replaced one is worked out again.
        cache = getattr(self, "_costs", None)
        if cache is None:
            cache = self._costs = {}
        known = cache.get(id(definition))
        if known is None or known[0] is not definition:
            known = cache[id(definition)] = (definition, self._work_out_cost_text(definition))
        return known[1]

    def _work_out_cost_text(self, definition):
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
        for item in loadout.working():
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
                    icon_asset_id=getattr(definition, "icon_id", "") or None,
                    cost_text=self._cost_text(definition),
                    enabled=not reason,
                    disabled_reason=reason,
                    detail=getattr(definition, "description", ""),
                    order=len(rows),
                )
            )
        return rows

    def attack_rows(self, actor_id):
        """One row per weapon attack (root style's *Attack* category)."""
        return self._ability_rows(actor_id, self.weapon_ability_ids(actor_id), "Attack")

    def root_rows(self, actor_id):
        # Only how many rows each command opens is shown here, so the rows are counted, not
        # built (building them asks every ability why it cannot be used, on every frame).
        registry = self.game.battle.ability_runtime.registry
        weapons = sum(1 for a in self.weapon_ability_ids(actor_id) if registry.get(a) is not None)
        abilities = self._skill_groups(actor_id)
        skills = sum(1 for a, _ in abilities.get("Skills", ()) if a != "boost")
        skills += 1 if self.game.capture_targets() else 0
        items = sum(1 for _ in self._usable_items())
        rows = []
        groups = [("Attack", weapons, "Choose a weapon")]
        groups.append(("Skills", skills, "Abilities, concoct, capture"))
        for name in self.custom_categories(actor_id):
            groups.append((name, len(abilities.get(name, ())), "Abilities"))
        groups.append(("Items", items, "Use an item from the bag"))
        run = self.game.escape_chance()
        if run is not None:
            groups.append(("Escape", 1, f"{round(run * 100)}% to get away"))
        if self.pages is not None:
            by_name = {g[0]: g for g in groups}
            groups = [by_name[name] for name in self._paged(by_name)]
            top = self.pages.max_primary_layers
            if len(groups) > top:  # the rest wait on a More page
                if self.more:
                    groups = groups[top - 1 :] + [("Back", 1, "The first commands")]
                else:
                    rest = len(groups) - (top - 1)
                    groups = groups[: top - 1] + [("More", rest, "More commands")]
        for category, count, hint in groups:
            # the number beside a command: how many choices it opens; Escape shows its chance
            shown = (
                f"{round(run * 100)}%" if category == "Escape" else (str(count) if count else "")
            )
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

    def _skill_groups(self, actor_id):
        """The abilities ``skill_rows`` lists, by category: ``{category: [(id, definition)]}``."""
        groups = {}
        registry = self.game.battle.ability_runtime.registry
        known = self.game.battle.member(actor_id).ability_ids
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
            category = getattr(definition, "menu_category", "") or "Skills"
            groups.setdefault(category, []).append((ability_id, definition))
        return groups

    def skill_rows(self, actor_id, category="Skills"):
        return self._skill_rows(actor_id, category, self._skill_groups(actor_id))

    def command_rows(self, actor_id):
        """The rows of every category the command list shows, ``{category: rows}`` in menu
        order: *Attack* (root style), *Skills*, the project's own groups, then *Items*."""
        abilities = self._skill_groups(actor_id)
        groups = {"Attack": self.attack_rows(actor_id)} if self.style == "root" else {}
        groups["Skills"] = self._skill_rows(actor_id, "Skills", abilities)
        for name in self.custom_categories(actor_id):  # a project's own menu groups
            groups[name] = self._skill_rows(actor_id, name, abilities)
        groups["Items"] = self.item_rows()
        return groups

    def _skill_rows(self, actor_id, category, abilities):
        game, rows = self.game, []
        for ability_id, definition in abilities.get(category, ()):
            reason = game.ability_unavailable(actor_id, ability_id)
            rows.append(
                BattleActionEntry(
                    ability_id,
                    self._name(ability_id),
                    category=category,
                    icon_asset_id=getattr(definition, "icon_id", "") or None,
                    cost_text=self._cost_text(definition),
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

    def _usable_items(self):
        """``(item id, item, count)`` of the items in the bag that can be used in battle."""
        inventory = self.game.save.rpg_state.inventory
        for item_id, item in sorted(self.game.project.rpg_database.items.items()):
            count = inventory.count(item_id)
            if count > 0 and (item.battle_ability or item.use_effects):
                yield item_id, item, count

    def item_rows(self):
        rows = []
        for item_id, item, count in self._usable_items():
            rows.append(
                BattleActionEntry(
                    item_id,
                    f"{item.display_name}",
                    category="Items",
                    icon_asset_id=getattr(item, "icon_id", "") or None,
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

    def form_rows(self, actor_id):
        """The ways to cast the pending skill: its forms, each with its extra cost."""
        definition = self._definition(self.pending[1])
        rows = []
        for form in definition.forms:
            reason = self.game.form_unavailable(actor_id, form)
            extra = [f"{v:g} {self._short(k)}" for k, v in form.get("resource_costs", {}).items()]
            extra += [f"{v:g} {self._short(k)}" for k, v in form.get("battle_costs", {}).items()]
            rows.append(
                BattleActionEntry(
                    form["form_id"],
                    form["label"],
                    category="Form",
                    cost_text=", ".join(extra),
                    enabled=not reason,
                    disabled_reason=reason,
                    order=len(rows),
                )
            )
        return rows

    def _workflow(self):
        if not self.pending or self.pending[0] != "ability":
            return None
        return self.game.input_workflow(self.pending[1])

    def _step(self):
        workflow = self._workflow()
        done = [x for x in workflow.steps if x.step_id in self.choices]
        return workflow.steps[len(done)] if len(done) < len(workflow.steps) else None

    def step_rows(self, actor_id):
        """The options of the current input step (each with its extra cost); a step that takes
        several ends on a *Done* row once enough are picked."""
        step = self._step()
        picked = self.choices.get(f"~{step.step_id}", [])
        rows = []
        for option in step.options:
            payload = dict(option.payload)
            extra = {
                "resource_costs": payload.get("resource_costs", {}),
                "battle_costs": payload.get("battle_costs", {}),
            }
            reason = option.disabled_reason if not option.enabled else ""
            reason = reason or self.game.form_unavailable(actor_id, extra)
            costs = [f"{v:g}{self._short(k)}" for k, v in extra["resource_costs"].items()]
            costs += [f"{v:g}{self._short(k)}" for k, v in extra["battle_costs"].items()]
            mark = "* " if option.option_id in picked else ""
            rows.append(
                BattleActionEntry(
                    option.option_id,
                    mark + option.label,
                    category=step.label,
                    icon_asset_id=option.icon_asset_id,
                    cost_text=" ".join(costs),
                    enabled=not reason,
                    disabled_reason=reason,
                    detail=option.detail,
                    order=len(rows),
                )
            )
        if step.selection_mode == "multiple":
            enough = len(picked) >= step.minimum_selections
            rows.append(
                BattleActionEntry(
                    "step:done",
                    self._workflow().confirmation_label,
                    category=step.label,
                    cost_text=f"{len(picked)}/{step.maximum_selections}",
                    enabled=enough,
                    disabled_reason="" if enough else f"Pick {step.minimum_selections}",
                    order=len(rows),
                )
            )
        return rows

    def _choose_step(self, actor_id, row):
        """A step's option picked: a single step moves on, a multiple one toggles until Done."""
        step = self._step()
        key = f"~{step.step_id}"  # the picks of a step still open
        picked = self.choices.setdefault(key, [])
        if row.action_id != "step:done":
            if not row.enabled:
                self.message = row.disabled_reason
                return False
            if row.action_id in picked:
                picked.remove(row.action_id)
            elif len(picked) < step.maximum_selections:
                picked.append(row.action_id)
            if step.selection_mode == "multiple":
                return False
        elif not row.enabled:
            self.message = row.disabled_reason
            return False
        self.choices[step.step_id] = self.choices.pop(key)
        self.cursor = 0
        if self._step() is not None:
            return False
        if self._definition(self.pending[1]).forms:
            self.mode, self.form = "forms", None
            return False
        return self._choose_target_or_act(actor_id)

    def _step_back(self):
        """Esc in the steps: undo the last finished step, or leave for the command list."""
        open_key = next((k for k in self.choices if k.startswith("~")), None)
        if open_key is not None:
            self.choices.pop(open_key)
        done = [k for k in self.choices if not k.startswith("~")]
        if done and open_key is None:
            self.choices.pop(done[-1])
        elif not done:
            self.mode, self.pending, self.choices = "command", None, {}
        self.cursor = 0

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
        if key == "pet" and self.game.pet_name(number):
            return self.game.pet_name(number)
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
        if self.mode == "steps":
            return self.step_rows(actor_id)
        if self.mode == "forms":
            return self.form_rows(actor_id)
        if self.mode == "root":
            return self.root_rows(actor_id)
        if self.category == "Attack":
            return self.attack_rows(actor_id)
        if self.category == "Items":
            return self.item_rows()
        return self.skill_rows(actor_id, self.category)

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
        if key == "auto" and self.mode in ("command", "root"):
            # the manifest's auto key: this turn is played by ``auto_battle_choice``
            self.reset()
            return self.game.auto_battle_act(actor_id) is not None
        if key == "category" and self.mode == "command":
            cats = self.categories_for(actor_id)
            current = cats.index(self.category) if self.category in cats else -1
            self.category = cats[(current + 1) % len(cats)]
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
            if self.mode == "steps":
                self._step_back()
                return False
            if (
                self.mode in ("target", "forms")
                and self._workflow() is not None
                and (self.mode == "forms" or self.form is None)
            ):  # back into the last input step
                self.mode, self.form = "steps", None
                self.choices.pop(next(reversed(self.choices)), None) if self.choices else None
                self.cursor = 0
                return False
            if self.mode == "target" and self.pending and self.pending[0] == "concoct":
                self.ingredients.popitem() if self.ingredients else None
                self.mode = "ingredients"
            elif self.mode == "target" and self.form is not None:
                self.mode, self.form = "forms", None
            elif self.mode == "forms":
                self.mode, self.pending, self.form = "command", None, None
            elif self.mode == "ingredients" and self.ingredients:
                self.ingredients.popitem()
            elif self.mode == "command" and self.style == "root":
                self.mode = "root"
                names = [r.action_id.split(":", 1)[1] for r in self.root_rows(actor_id)]
                self.cursor = names.index(self.category) if self.category in names else 0
                return False
            elif self.mode == "root":
                self.more = False  # back from the More page
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
            if row.action_id in ("root:More", "root:Back"):
                self.more, self.cursor = row.action_id == "root:More", 0
                return False
            if row.action_id == "root:Escape":
                reason = self.game.escape_unavailable()
                if reason:
                    self.message = reason
                    return False
                self.game.attempt_escape(actor_id)
                return True  # a failed attempt still uses the turn
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
                if self._workflow() is not None:  # its input steps come first
                    self.mode, self.cursor, self.choices = "steps", 0, {}
                    return False
                if self._definition(row.action_id).forms:  # which form comes before the target
                    self.mode, self.cursor, self.form = "forms", 0, None
                    return False
            return self._choose_target_or_act(actor_id)
        if self.mode == "forms":
            if not row.enabled:
                self.message = row.disabled_reason
                return False
            self.form = row.action_id
            return self._choose_target_or_act(actor_id)
        if self.mode == "steps":
            return self._choose_step(actor_id, row)
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
                game.use_ability(
                    actor_id,
                    key,
                    targets,
                    boost_level=self.boost,
                    form=self.form,
                    choices=self.choices or None,
                )
        except Exception as exc:  # shown in the menu footer; the turn is not used
            self.message = str(exc)
            self.mode, self.cursor = ("root" if self.style == "root" else "command"), 0
            self.pending, self.ingredients, self.choices = None, {}, {}
            return False
        self.reset()
        return True

    def selected_target(self, actor_id):
        if self.mode != "target":
            return None
        rows = self.entries(actor_id)
        return rows[self.cursor].action_id if rows else None
