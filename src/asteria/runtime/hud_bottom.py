"""The bottom of the real-time HUD (D23): resource orbs, the action bar and the status row.

* **Orbs** - the life resource fills a red globe on the left, the first other resource a globe on
  the right (blue for mana-like names), like Diablo; more resources are thin bars above the bar.
* **Action bar** - one slot per ability binding: the two non-numbered ones (attack, dodge) larger
  at the left, then the numbered skills. Each slot shows its key as a keycap (read from the
  project's input map), the ability's name, a cooldown sweep with seconds, a count badge in the
  lower right when the ability spends items, and the cost in the lower left. A slot whose
  ability cannot be paid right now is dimmed.
* **Status row** - every active state of the player as a square: green frame for a boon, red for
  a harm (judged from what the state does: stat changes, damage or healing over time), the time
  left as a sweep with seconds, a badge for stacks. A resource called shield / barrier / ward is
  a bar of its own.
* a one-line control hint at the top that fades after a few seconds.

Everything is read from engine state and the project; nothing is game-specific.
"""

from __future__ import annotations

from math import sqrt

KEY_NAMES = {
    "left shift": "SHIFT",
    "right shift": "SHIFT",
    "left ctrl": "CTRL",
    "right ctrl": "CTRL",
    "left alt": "ALT",
    "right alt": "ALT",
    "space": "SPACE",
    "return": "ENTER",
    "escape": "ESC",
    "tab": "TAB",
    "backspace": "BKSP",
}
MANA_WORDS = ("mp", "mana", "magic", "spirit", "technique", "focus", "energy", "ap")
HARM_WORDS = (
    "poison",
    "burn",
    "bleed",
    "stun",
    "slow",
    "chill",
    "curse",
    "silence",
    "sleep",
    "fear",
)
SHIELD_WORDS = ("shield", "barrier", "ward", "guard")


def key_label(rt, action):
    """The key (or button) shown for an input action, from the project's input map."""
    from .action_play import ARPG_ACTIONS

    bindings = []
    input_map = getattr(rt.project, "input_map", None)
    if input_map is not None:
        bindings = [(b.device, b.code) for b in input_map.bindings(action)]
    if not bindings:
        bindings = list(ARPG_ACTIONS.get(action, ()))
    for device, code in bindings:
        if device in ("key", "keyboard"):
            return KEY_NAMES.get(str(code).lower(), str(code).upper())
    if bindings:
        return f"PAD {bindings[0][1]}"
    return action.replace("skill_", "").upper()[:5]


def resource_color(name, life=False):
    """``(dark, light)`` colours of a resource's orb or bar."""
    n = name.lower()
    if life:
        return (110, 14, 18), (232, 54, 48)
    if any(w in n for w in SHIELD_WORDS):
        return (90, 110, 130), (200, 226, 250)
    if any(w in n for w in ("rage", "fury", "anger")):
        return (120, 54, 10), (240, 130, 40)
    if any(w in n for w in ("stamina", "energy", "focus")):
        return (110, 100, 14), (236, 214, 70)
    return (18, 38, 120), (66, 128, 245)


def state_kind(definition):
    """``"buff"`` or ``"debuff"`` for a state, from what it does."""
    score = 0.0
    for modifier in getattr(definition, "modifiers", ()):
        value = float(modifier.value)
        if modifier.operation.value == "multiply":
            score += value - 1.0
        else:
            score += value
    for periodic in getattr(definition, "periodic", ()):
        for operation in periodic.effect.operations:
            if operation.kind.value in ("resource_delta", "stat_delta") and isinstance(
                operation.value, (int, float)
            ):
                score += float(operation.value)
    if score < 0:
        return "debuff"
    if score > 0:
        return "buff"
    text = " ".join([definition.state_id, *definition.contributed_tags]).lower()
    return "debuff" if any(w in text for w in HARM_WORDS) else "buff"


def active_statuses(game, state):
    """``[{id, name, abbr, kind, remaining, total, stacks}]`` for the player's active states."""
    runtime = getattr(state, "states", None)
    if runtime is None:
        return []
    out = []
    for active in runtime.active_states():
        definition = runtime.registry.get(active.state_id)
        if definition is None:
            continue
        words = active.state_id.replace(".", " ").replace("_", " ").split()
        out.append(
            {
                "id": active.state_id,
                "name": " ".join(w.capitalize() for w in words),
                # two words: their initials; one word: its first two letters
                "abbr": (
                    "".join(w[0] for w in words[:2]) if len(words) > 1 else active.state_id[:2]
                ).upper()
                or "?",
                "kind": state_kind(definition),
                "remaining": float(active.remaining),
                "total": max(0.001, float(definition.duration)),
                "stacks": int(active.stacks),
            }
        )
    return out


class BottomHud:
    """Drawn each frame by ``ActionHud.draw_overlay``; remembers only the hint timer."""

    HINT_SECONDS = 12.0

    def __init__(self):
        self.hint_left = self.HINT_SECONDS
        self._orb_cache = {}

    def tick(self, dt):
        self.hint_left = max(0.0, self.hint_left - dt)

    # -- pieces ----------------------------------------------------------------------------------
    def _orb(self, rt, cx, cy, radius, fraction, colors, title, value_text):
        pg, screen = rt.pg, rt.screen
        dark, light = colors
        fraction = max(0.0, min(1.0, fraction))
        d = radius * 2
        key = (radius, round(fraction * radius * 2), colors)
        image = self._orb_cache.get(key)
        if image is None:
            image = pg.Surface((d, d), pg.SRCALPHA)
            pg.draw.circle(image, (14, 14, 20, 255), (radius, radius), radius)
            top = d - int(round(fraction * d))
            for y in range(top, d):  # the liquid: one chord per row, lighter toward the surface
                half = sqrt(max(0.0, radius * radius - (y - radius) ** 2))
                t = (y - top) / max(1, d - top)
                color = tuple(int(light[i] + (dark[i] - light[i]) * t) for i in range(3))
                pg.draw.line(image, color, (radius - half, y), (radius + half - 1, y))
            if fraction > 0:  # the surface line
                half = sqrt(max(0.0, radius * radius - (top - radius) ** 2))
                pg.draw.line(
                    image,
                    tuple(min(255, c + 40) for c in light),
                    (radius - half, top),
                    (radius + half - 1, top),
                    2,
                )
            shine = pg.Surface((d, d), pg.SRCALPHA)
            pg.draw.ellipse(
                shine,
                (255, 255, 255, 46),
                (radius * 0.35, radius * 0.18, radius * 0.7, radius * 0.5),
            )
            image.blit(shine, (0, 0))
            self._orb_cache = {k: v for k, v in self._orb_cache.items() if k[0] == radius}
            self._orb_cache[key] = image
        pg.draw.circle(screen, (8, 8, 12), (cx, cy), radius + 4)
        screen.blit(image, (cx - radius, cy - radius))
        pg.draw.circle(screen, (120, 128, 150), (cx, cy), radius + 4, 3)
        rt.text(
            title,
            cx,
            cy - radius * 0.38,
            size=max(15, radius // 3),
            color=(240, 240, 245),
            anchor="center",
        )
        rt.text(
            value_text,
            cx,
            cy + radius * 0.12,
            size=max(16, radius // 3 + 2),
            color=(255, 255, 255),
            anchor="center",
        )

    def _slot(self, rt, game, x, y, size, action, value, labels):
        from .action_combat import ITEM_COST

        pg, screen = rt.pg, rt.screen
        rect = pg.Rect(x, y, size, size)
        ability_id = game.action_combat.bound_ability(game.player, value)
        pg.draw.rect(screen, (22, 26, 40), rect, border_radius=6)
        key = key_label(rt, action)
        if not ability_id:  # nothing learned for this slot yet
            pg.draw.rect(screen, (60, 66, 86), rect, 2, border_radius=6)
            rt.text(
                "—", rect.centerx, rect.centery, size=20, color=(100, 108, 128), anchor="center"
            )
        else:
            ability = game.project.gameplay_library.abilities.get(ability_id)
            prices = game.action_combat._prices(game.player, ability) if ability else []
            usable = not isinstance(prices, str)
            name = labels.get(ability_id, {}).get("label") or ability_id.split("_", 1)[-1]
            pg.draw.rect(
                screen, (70, 78, 108) if usable else (46, 50, 72), rect, 2, border_radius=6
            )
            words = name.split()
            lines = [name] if len(name) <= 8 or len(words) < 2 else [words[0], " ".join(words[1:])]
            for k, line in enumerate(lines[:2]):
                rt.text(
                    line[:9],
                    rect.centerx,
                    rect.centery - 2 + (k - (len(lines) - 1) / 2) * 15,
                    size=15 if size < 58 else 16,
                    color=(235, 238, 248) if usable else (130, 138, 160),
                    anchor="center",
                )
            left = game.action_combat.cooldown(game.player, ability_id)
            total = getattr(ability, "cooldown_seconds", 0.0) or left
            if left > 0 and total > 0:
                shade = pg.Surface(
                    (size - 4, int((size - 4) * min(1.0, left / total))), pg.SRCALPHA
                )
                shade.fill((0, 0, 0, 175))
                screen.blit(shade, (rect.x + 2, rect.y + 2))
                rt.text(
                    f"{left:.1f}" if left < 10 else f"{left:.0f}",
                    rect.centerx,
                    rect.centery,
                    size=20,
                    color=(255, 255, 255),
                    anchor="center",
                )
            elif not usable:
                tint = pg.Surface((size - 4, size - 4), pg.SRCALPHA)
                tint.fill((20, 30, 80, 120))
                screen.blit(tint, (rect.x + 2, rect.y + 2))
            for cost in getattr(ability, "costs", ()):
                if cost.resource.startswith(ITEM_COST):  # items: the count, as a corner badge
                    have = game.save.rpg_state.inventory.count(cost.resource[len(ITEM_COST) :])
                    self._badge(
                        rt,
                        rect.right - 2,
                        rect.bottom - 2,
                        str(have),
                        "bottomright",
                        (24, 70, 44),
                        (170, 240, 190),
                    )
                    break
            else:
                if isinstance(prices, list) and prices:
                    resource, amount = prices[0]
                    colors = resource_color(resource)
                    rt.text(
                        f"{amount:g}",
                        rect.x + 5,
                        rect.bottom - 4,
                        size=15,
                        color=colors[1],
                        anchor="bottomleft",
                    )
        # the keycap, half outside the slot's top-left corner
        cap_w = max(18, len(key) * 8 + 10)
        cap = pg.Rect(rect.x - 4, rect.y - 7, cap_w, 17)
        pg.draw.rect(screen, (214, 218, 228), cap, border_radius=4)
        pg.draw.rect(screen, (90, 96, 112), cap, 1, border_radius=4)
        rt.text(key, cap.centerx, cap.centery, size=14, color=(30, 34, 46), anchor="center")
        return rect

    def _badge(self, rt, x, y, text, anchor, fill, color):
        """A small rounded square with a number (counts), anchored to a corner of a slot."""
        pg = rt.pg
        w = max(18, len(text) * 8 + 8)
        rect = pg.Rect(0, 0, w, 18)
        setattr(rect, anchor, (x, y))
        pg.draw.rect(rt.screen, fill, rect, border_radius=4)
        pg.draw.rect(rt.screen, (150, 160, 180), rect, 1, border_radius=4)
        rt.text(text, rect.centerx, rect.centery, size=15, color=color, anchor="center")

    def _status(self, rt, x, y, size, entry):
        pg, screen = rt.pg, rt.screen
        good = entry["kind"] == "buff"
        frame = (96, 214, 130) if good else (226, 92, 84)
        fill = (20, 52, 32) if good else (62, 22, 24)
        rect = pg.Rect(x, y, size, size)
        pg.draw.rect(screen, fill, rect, border_radius=5)
        rt.text(
            entry["abbr"], rect.centerx, rect.centery - 2, size=20, color=frame, anchor="center"
        )
        fraction = max(0.0, min(1.0, entry["remaining"] / entry["total"]))
        if fraction < 1.0:  # time left drains from the top
            shade = pg.Surface((size - 4, int((size - 4) * (1.0 - fraction))), pg.SRCALPHA)
            shade.fill((0, 0, 0, 150))
            screen.blit(shade, (rect.x + 2, rect.y + 2))
        pg.draw.rect(screen, frame, rect, 2, border_radius=5)
        seconds = entry["remaining"]
        rt.text(
            f"{seconds:.0f}s" if seconds >= 1 else f"{seconds:.1f}",
            rect.centerx,
            rect.bottom + 8,
            size=14,
            color=(220, 226, 238),
            anchor="center",
        )
        if entry["stacks"] > 1:
            self._badge(
                rt,
                rect.right + 2,
                rect.y - 2,
                str(entry["stacks"]),
                "topright",
                (40, 40, 60),
                (255, 230, 150),
            )

    def _bar(self, rt, x, y, w, h, fraction, colors, label):
        pg, screen = rt.pg, rt.screen
        pg.draw.rect(screen, (14, 16, 24), (x - 1, y - 1, w + 2, h + 2), border_radius=3)
        pg.draw.rect(screen, (44, 48, 62), (x, y, w, h), border_radius=3)
        pg.draw.rect(
            screen, colors[1], (x, y, int(w * max(0.0, min(1.0, fraction))), h), border_radius=3
        )
        rt.text(label, x + 4, y + h / 2, size=13, color=(240, 244, 250), anchor="midleft")

    # -- the whole bottom ------------------------------------------------------------------------
    def draw(self, rt, game):
        from .action_combat import ActionCombatComponent, parse_bindings
        from .combat import CombatantComponent

        pg, screen = rt.pg, rt.screen
        width, height = rt.width, rt.height
        combatant = game.player.try_get(CombatantComponent)
        state = game.combat.state(game.player) if combatant is not None else None
        radius = max(36, min(58, int(height * 0.078)))
        margin = 14
        left_c = (margin + radius + 4, height - margin - radius - 4)
        right_c = (width - margin - radius - 4, left_c[1])

        extras = []
        if state is not None:
            names = list(state.resources.names())
            life = combatant.life_resource
            second = next(
                (n for n in names if n != life and not any(w in n.lower() for w in SHIELD_WORDS)),
                None,
            )
            for name, centre, colors in (
                (life, left_c, resource_color(life, life=True)),
                (second, right_c, resource_color(second or "")),
            ):
                if name and name in names:
                    value = state.resources.get(name)
                    frac = value.current / value.maximum if value.maximum else 0.0
                    self._orb(
                        rt,
                        centre[0],
                        centre[1],
                        radius,
                        frac,
                        colors,
                        name.upper() if len(name) <= 3 else name.capitalize(),
                        f"{value.current:.0f}/{value.maximum:.0f}",
                    )
            extras = [n for n in names if n not in (life, second)]

        # the action bar
        spec = game.player.try_get(ActionCombatComponent)
        bindings = list(parse_bindings(spec.bindings).items()) if spec is not None else []
        primary = [b for b in bindings if not b[0].startswith("skill_")]
        numbered = [b for b in bindings if b[0].startswith("skill_")]
        big = max(48, min(64, radius + 8))
        small = max(44, min(56, radius + 2))
        gap = 8
        total = len(primary) * (big + gap) + len(numbered) * (small + gap) - gap
        bar_left = left_c[0] + radius + 22
        bar_right = right_c[0] - radius - 22
        x = max(bar_left, min((width - total) // 2, bar_right - total))
        base_y = height - 40 - big
        plate = pg.Rect(x - 12, base_y - 10, total + 24, big + 22)
        rt.panel(
            (plate.x, plate.y, plate.width, plate.height),
            fill=(12, 14, 24, 235),
            border=(110, 118, 142),
        )
        labels = rt.manifest.get("battle", {}).get("skills", {})
        cursor = x
        for action, value in primary:
            self._slot(rt, game, cursor, base_y, big, action, value, labels)
            cursor += big + gap
        for action, value in numbered:
            self._slot(rt, game, cursor, base_y + (big - small), small, action, value, labels)
            cursor += small + gap

        # experience strip under the bar, with the level
        actor_id = game._actor_of(game.player)
        strip = pg.Rect(plate.x, plate.bottom + 4, plate.width, 14)
        pg.draw.rect(screen, (14, 16, 24), strip.inflate(2, 2), border_radius=4)
        pg.draw.rect(screen, (44, 48, 62), strip, border_radius=4)
        if actor_id is not None:
            progress = game.ensure_actor_progression(actor_id)
            threshold = float(game.action_progression.get("level_threshold", 1000.0))
            into = progress.experience - (progress.level - 1) * threshold
            fraction = max(0.0, min(1.0, into / threshold if threshold else 0.0))
            pg.draw.rect(
                screen,
                (214, 172, 58),
                (strip.x, strip.y, int(strip.width * fraction), strip.height),
                border_radius=4,
            )
            rt.text(
                f"Lv {progress.level}",
                strip.centerx,
                strip.centery,
                size=14,
                color=(255, 255, 255),
                anchor="center",
            )

        # statuses above the bar (left) and the other resources (right)
        if state is not None:
            row_y = plate.y - 14 - 36 - 12
            for k, entry in enumerate(active_statuses(game, state)[:12]):
                self._status(rt, plate.x + k * 42, row_y, 34, entry)
            for k, name in enumerate(extras[:3]):
                value = state.resources.get(name)
                frac = value.current / value.maximum if value.maximum else 0.0
                label = f"{name.capitalize()}  {value.current:.0f}/{value.maximum:.0f}"
                self._bar(
                    rt,
                    plate.right - 150,
                    plate.y - 20 - k * 20,
                    150,
                    14,
                    frac,
                    resource_color(name),
                    label,
                )

        # the controls, top centre, on a dark strip, fading out
        if self.hint_left > 0:
            alpha = min(1.0, self.hint_left / 2.0)
            text = (
                "Move WASD   Attack J   Dodge K   Skills 1-4   Lock L   Pick up F   "
                "Bag B   Skill tree C   Pause Esc"
            )
            font = rt._fonts.get(17) or rt._fonts.setdefault(17, pg.font.Font(None, 17))
            w, h = font.size(text)
            strip = pg.Surface((w + 24, h + 10), pg.SRCALPHA)
            pg.draw.rect(strip, (8, 10, 18, int(190 * alpha)), strip.get_rect(), border_radius=8)
            screen.blit(strip, (width / 2 - (w + 24) / 2, 8))
            colour = tuple(int(60 + 170 * alpha) for _ in range(3))
            rt.text(text, width / 2, 8 + (h + 10) / 2, size=17, color=colour, anchor="center")


__all__ = ["BottomHud", "active_statuses", "key_label", "resource_color", "state_kind"]
