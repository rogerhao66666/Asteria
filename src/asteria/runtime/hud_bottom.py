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

Everything is read from engine state and the project; nothing is game-specific. Every piece
is an element of the ``hud_action`` layout (V3): the orbs (their frame, liquid and empty
pictures, colours, the title and value words; or bars instead), the bar's plate and slots
(size, gap, frame pictures), the keycap, the cooldown (a strip whose frame follows the time
left), the badge and cost, the experience strip, the statuses, the other resources' bars, the
controls hint, the target frame, the banner and the "fell" overlay. Without a layout the HUD
draws exactly as before; the menu theme's resource colours replace the colours guessed from a
resource's name.
"""

from __future__ import annotations

from math import cos, pi, sin, sqrt

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


def resource_color(name, life=False, theme=None):
    """``(dark, light)`` colours of a resource's orb or bar: the menu theme's colour for it
    (``theme``), else guessed from its name."""
    own = theme.resource_color(name) if theme is not None and name else None
    if own is not None:
        return tuple(int(v * 0.45) for v in own[:3]), tuple(own[:3])
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
        shown = game.name_of(definition) or ""
        label = shown or " ".join(w.capitalize() for w in words)
        initials = label.split() if shown else words
        out.append(
            {
                "id": active.state_id,
                "name": label,
                "icon": definition.icon_id,
                # two words: their initials; one word: its first two letters
                "abbr": (
                    "".join(w[0] for w in initials[:2]) if len(initials) > 1 else label[:2]
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
    FLASH_SECONDS = 0.3

    def __init__(self):
        self.hint_left = self.HINT_SECONDS
        self._orb_cache = {}
        self._cooling = {}  # ability id -> seconds left at the last frame (for the ready flash)
        self._flash = {}

    def tick(self, dt):
        self.hint_left = max(0.0, self.hint_left - dt)
        for key in list(self._flash):
            self._flash[key] -= dt
            if self._flash[key] <= 0:
                del self._flash[key]

    def _sweep(self, rt, rect, done):
        """The cooldown clock: the slot goes dark, and a bright wedge opens clockwise from the top
        until the whole slot is bright again. ``done`` is the part of the cooldown that passed."""
        pg = rt.pg
        w, h = rect.width - 4, rect.height - 4
        shade = pg.Surface((w, h), pg.SRCALPHA)
        shade.fill((0, 0, 0, 185))
        cx, cy = w / 2, h / 2
        reach = (w + h) * 0.75
        angle = 2 * pi * max(0.0, min(1.0, done))
        points = [(cx, cy), (cx, cy - reach)]
        steps = max(2, int(done * 24) + 1)
        for k in range(1, steps + 1):  # along the circle, so the wedge is exact past 90 degrees
            a = angle * k / steps
            points.append((cx + sin(a) * reach, cy - cos(a) * reach))
        if done > 0:
            pg.draw.polygon(shade, (0, 0, 0, 0), points)
        rt.screen.blit(shade, (rect.x + 2, rect.y + 2))
        if 0 < done < 1:  # the sweeping edge
            end = (cx + sin(angle) * reach, cy - cos(angle) * reach)
            clip = rt.screen.get_clip()
            rt.screen.set_clip(rect.inflate(-4, -4))
            pg.draw.line(
                rt.screen,
                (235, 240, 255),
                (rect.x + 2 + cx, rect.y + 2 + cy),
                (rect.x + 2 + end[0], rect.y + 2 + end[1]),
                2,
            )
            rt.screen.set_clip(clip)

    # -- pieces ----------------------------------------------------------------------------------
    def _orb(self, rt, c, orb_id, rect, fraction, colors, title, value_text):
        pg, screen = rt.pg, rt.screen
        x, y, w, h = (int(v) for v in rect)
        cx, cy, radius = x + w // 2, y + h // 2, max(4, min(w, h) // 2)
        element = c.element(orb_id)
        dark = (element.fill if element is not None and element.fill else None) or colors[0]
        light = (element.color if element is not None and element.color else None) or colors[1]
        colors = (tuple(dark[:3]), tuple(light[:3]))
        dark, light = colors
        fraction = max(0.0, min(1.0, fraction))
        if self._drawn_orb(rt, c, orb_id, (x, y, w, h), fraction):
            self._orb_words(rt, c, orb_id, cx, cy, radius, title, value_text)
            return
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
        self._orb_words(rt, c, orb_id, cx, cy, radius, title, value_text)

    @staticmethod
    def _drawn_orb(rt, c, orb_id, rect, fraction):
        """The orb from the author's pictures (``<orb>_empty`` under, ``<orb>_fill`` shown up
        to the fill line, ``<orb>``'s own picture over them); False when there are none."""
        names = (f"{orb_id}_empty", f"{orb_id}_fill", orb_id)
        if not any(c.element(n) is not None and (c.element(n).image or c.element(n).skin)
                   for n in names):  # fmt: skip
            return False
        x, y, w, h = rect
        c.picture(names[0], rect, repeated=True, pictures_only=True)
        top = y + h - int(round(h * fraction))
        clip = rt.screen.get_clip()
        rt.screen.set_clip(rt.pg.Rect(x, top, w, y + h - top).clip(clip))
        c.picture(names[1], rect, repeated=True, pictures_only=True)
        rt.screen.set_clip(clip)
        c.picture(orb_id, rect, repeated=True, pictures_only=True)
        return True

    @staticmethod
    def _orb_words(rt, c, orb_id, cx, cy, radius, title, value_text):
        c.text(
            f"{orb_id}_title",
            title,
            cx,
            cy - radius * 0.38,
            size=max(15, radius // 3),
            color=(240, 240, 245),
            anchor="center",
        )
        c.text(
            f"{orb_id}_value",
            value_text,
            cx,
            cy + radius * 0.12,
            size=max(16, radius // 3 + 2),
            color=(255, 255, 255),
            anchor="center",
        )

    def _slot(self, rt, c, game, x, y, size, action, value, labels, slot_id="slot"):
        from .action_combat import ITEM_COST

        pg, screen = rt.pg, rt.screen
        rect = pg.Rect(x, y, size, size)
        ability_id = game.action_combat.bound_ability(game.player, value)
        framed = c.picture(slot_id, rect, repeated=True, pictures_only=True)  # the author's
        if not framed:
            pg.draw.rect(screen, (22, 26, 40), rect, border_radius=6)
        key = key_label(rt, action)
        if not ability_id:  # nothing learned for this slot yet
            if not framed:
                pg.draw.rect(screen, (60, 66, 86), rect, 2, border_radius=6)
            rt.text(
                "—", rect.centerx, rect.centery, size=20, color=(100, 108, 128), anchor="center"
            )
        else:
            ability = game.project.gameplay_library.abilities.get(ability_id)
            prices = game.action_combat._prices(game.player, ability) if ability else []
            usable = not isinstance(prices, str)
            name = (
                (game.name_of(ability) or "")
                or labels.get(ability_id, {}).get("label")
                or ability_id.split("_", 1)[-1]
            )
            icon_id = getattr(ability, "icon_id", "")
            if not framed:
                pg.draw.rect(
                    screen, (70, 78, 108) if usable else (46, 50, 72), rect, 2, border_radius=6
                )
            words = name.split()
            lines = [name] if len(name) <= 8 or len(words) < 2 else [words[0], " ".join(words[1:])]
            if icon_id and rt._draw_icon(icon_id, rect.x + 5, rect.y + 5, size - 10):
                lines = []  # the picture says what the skill is
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
            seen = self._cooling.get(ability_id, 0.0)
            if seen > 0 and left <= 0:  # ready again: a short flash
                self._flash[ability_id] = self.FLASH_SECONDS
            self._cooling[ability_id] = left
            if left > 0 and total > 0:
                done = 1.0 - min(1.0, left / total)
                if not c.picture("cooldown", rect, float(done), repeated=True,
                                 pictures_only=True):  # fmt: skip
                    self._sweep(rt, rect, done)
                rt.text(
                    f"{left:.1f}" if left < 10 else f"{left:.0f}",
                    rect.centerx,
                    rect.centery,
                    size=20,
                    color=(255, 255, 255),
                    anchor="center",
                )
            elif self._flash.get(ability_id, 0.0) > 0:
                glow = pg.Surface((size - 4, size - 4), pg.SRCALPHA)
                glow.fill((255, 255, 255, int(150 * self._flash[ability_id] / self.FLASH_SECONDS)))
                screen.blit(glow, (rect.x + 2, rect.y + 2))
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
                        c=c,
                    )
                    break
            else:
                if isinstance(prices, list) and prices:
                    resource, amount = prices[0]
                    colors = resource_color(resource, theme=c.theme)
                    self._cost(rt, c, rect.x + 3, rect.bottom - 3, f"{amount:g}", colors)
        # the keycap, half outside the slot's top-left corner
        cap_w = max(18, len(key) * 8 + 10)
        cap = pg.Rect(rect.x - 4, rect.y - 7, cap_w, 17)
        if not c.picture("keycap", cap, repeated=True):
            pg.draw.rect(screen, (214, 218, 228), cap, border_radius=4)
            pg.draw.rect(screen, (90, 96, 112), cap, 1, border_radius=4)
        color = c.color("keycap", (30, 34, 46))
        rt.text(key, cap.centerx, cap.centery, size=14, color=color, anchor="center")
        return rect

    def _cost(self, rt, c, x, y, text, colors):
        """A resource cost: a small orb of the resource's colour and the amount, on a dark pill
        in the lower left corner of a slot (``x``, ``y`` is the pill's bottom-left)."""
        pg, screen = rt.pg, rt.screen
        w = 20 + len(text) * 8
        pill = pg.Rect(0, 0, w, 17)
        pill.bottomleft = (x, y)
        if not c.picture("cost", pill, repeated=True):
            pg.draw.rect(screen, (10, 12, 22), pill, border_radius=8)
            pg.draw.rect(screen, colors[0], pill, 1, border_radius=8)
        cx, cy = pill.x + 9, pill.centery
        pg.draw.circle(screen, colors[0], (cx, cy), 5)
        pg.draw.circle(screen, colors[1], (cx, cy + 1), 4)
        pg.draw.circle(screen, (255, 255, 255), (cx - 1, cy - 1), 1)
        rt.text(text, pill.x + 16, pill.centery, size=15, color=colors[1], anchor="midleft")

    def _badge(self, rt, x, y, text, anchor, fill, color, c=None):
        """A small rounded square with a number (counts), anchored to a corner of a slot."""
        pg = rt.pg
        w = max(18, len(text) * 8 + 8)
        rect = pg.Rect(0, 0, w, 18)
        setattr(rect, anchor, (x, y))
        if c is None or not c.picture("badge", rect, repeated=True):
            pg.draw.rect(rt.screen, fill, rect, border_radius=4)
            pg.draw.rect(rt.screen, (150, 160, 180), rect, 1, border_radius=4)
        color = c.color("badge", color) if c is not None else color
        rt.text(text, rect.centerx, rect.centery, size=15, color=color, anchor="center")

    def _status(self, rt, c, x, y, size, entry):
        pg, screen = rt.pg, rt.screen
        good = entry["kind"] == "buff"
        frame = (96, 214, 130) if good else (226, 92, 84)
        fill = (20, 52, 32) if good else (62, 22, 24)
        rect = pg.Rect(x, y, size, size)
        look = "status_buff" if good else "status_debuff"
        framed = c.picture(look, rect, repeated=True)
        if not framed:
            pg.draw.rect(screen, fill, rect, border_radius=5)
        icon = entry.get("icon", "")
        if not (icon and rt._draw_icon(icon, rect.x + 4, rect.y + 4, size - 8)):
            rt.text(
                entry["abbr"],
                rect.centerx,
                rect.centery - 2,
                size=20,
                color=frame,
                anchor="center",
            )
        fraction = max(0.0, min(1.0, entry["remaining"] / entry["total"]))
        if fraction < 1.0:  # time left drains from the top
            shade = pg.Surface((size - 4, int((size - 4) * (1.0 - fraction))), pg.SRCALPHA)
            shade.fill((0, 0, 0, 150))
            screen.blit(shade, (rect.x + 2, rect.y + 2))
        if not framed:
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
                c=c,
            )

    def _bar(self, rt, x, y, w, h, fraction, colors, label, c=None, bar_id=""):
        pg, screen = rt.pg, rt.screen
        element = c.element(bar_id) if c is not None and bar_id else None
        back = element.fill if element is not None and element.fill else (44, 48, 62)
        colour = element.color if element is not None and element.color else colors[1]
        pg.draw.rect(screen, (14, 16, 24), (x - 1, y - 1, w + 2, h + 2), border_radius=3)
        pg.draw.rect(screen, back, (x, y, w, h), border_radius=3)
        pg.draw.rect(
            screen, colour, (x, y, int(w * max(0.0, min(1.0, fraction))), h), border_radius=3
        )
        if element is not None:  # the author's frame over it
            c.picture(bar_id, (x, y, w, h), repeated=True, pictures_only=True)
        size = element.size if element is not None and element.size else 13
        rt.text(label, x + 4, y + h / 2, size=size, color=(240, 244, 250), anchor="midleft")

    # -- the whole bottom ------------------------------------------------------------------------
    def draw(self, rt, game):
        """The bottom of the HUD; returns its canvas (``hud_action``) for the rest of the HUD,
        which finishes it."""
        from .action_combat import ActionCombatComponent, parse_bindings
        from .combat import CombatantComponent

        pg, screen = rt.pg, rt.screen
        width, height = rt.width, rt.height
        c = rt.menu_canvas("hud_action")
        c.begin()
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
            for orb_id, name, centre, colors in (
                ("orb_life", life, left_c, resource_color(life, life=True, theme=c.theme)),
                ("orb_second", second, right_c, resource_color(second or "", theme=c.theme)),
            ):
                if name and name in names:
                    value = state.resources.get(name)
                    frac = value.current / value.maximum if value.maximum else 0.0
                    title = name.upper() if len(name) <= 3 else name.capitalize()
                    amount = f"{value.current:.0f}/{value.maximum:.0f}"
                    box = (centre[0] - radius, centre[1] - radius, radius * 2, radius * 2)
                    if c.shown(orb_id):
                        self._orb(rt, c, orb_id, c.rect(orb_id, box), frac, colors, title,
                                  amount)  # fmt: skip
                    bar_id = orb_id.replace("orb_", "") + "_bar"  # life_bar, second_bar
                    bar = c.element(bar_id)
                    if bar is not None and bar.visible and bar.rect is not None:
                        x, y, w, h = c.rect(bar_id, box)
                        self._bar(rt, x, y, w, h, frac, colors, f"{title}  {amount}", c, bar_id)
            extras = [n for n in names if n not in (life, second)]

        # the action bar
        spec = game.player.try_get(ActionCombatComponent)
        bindings = list(parse_bindings(spec.bindings).items()) if spec is not None else []
        primary = [b for b in bindings if not b[0].startswith("skill_")]
        numbered = [b for b in bindings if b[0].startswith("skill_")]
        big = c.number("slot_main", "cell", max(48, min(64, radius + 8)))
        small = c.number("slot", "cell", max(44, min(56, radius + 2)))
        gap = c.number("slot", "gap", 8)
        total = len(primary) * (big + gap) + len(numbered) * (small + gap) - gap
        bar_left = left_c[0] + radius + 22
        bar_right = right_c[0] - radius - 22
        x = max(bar_left, min((width - total) // 2, bar_right - total))
        base_y = height - 40 - big
        plate = pg.Rect(x - 12, base_y - 10, total + 24, big + 22)
        moved = pg.Rect(c.rect("plate", plate))  # the slots go with their plate
        x, base_y = x + moved.x - plate.x, base_y + moved.y - plate.y
        plate = moved
        c.panel(
            "plate",
            (plate.x, plate.y, plate.width, plate.height),
            fill=(12, 14, 24, 235),
            border=(110, 118, 142),
        )
        labels = rt.manifest.get("battle", {}).get("skills", {})
        cursor = x
        for action, value in primary:
            self._slot(rt, c, game, cursor, base_y, big, action, value, labels, "slot_main")
            cursor += big + gap
        for action, value in numbered:
            self._slot(rt, c, game, cursor, base_y + (big - small), small, action, value, labels)
            cursor += small + gap

        # experience strip under the bar, with the level
        actor_id = game._actor_of(game.player)
        strip = pg.Rect(c.rect("exp", (plate.x, plate.bottom + 4, plate.width, 14)))
        exp = c.element("exp")
        shown = c.shown("exp")
        if shown:
            pg.draw.rect(screen, (14, 16, 24), strip.inflate(2, 2), border_radius=4)
            back = exp.fill if exp is not None and exp.fill else (44, 48, 62)
            pg.draw.rect(screen, back, strip, border_radius=4)
        if actor_id is not None and shown:
            progress = game.ensure_actor_progression(actor_id)
            threshold = float(game.action_progression.get("level_threshold", 1000.0))
            into = progress.experience - (progress.level - 1) * threshold
            fraction = max(0.0, min(1.0, into / threshold if threshold else 0.0))
            pg.draw.rect(
                screen,
                exp.color if exp is not None and exp.color else (214, 172, 58),
                (strip.x, strip.y, int(strip.width * fraction), strip.height),
                border_radius=4,
            )
            c.picture("exp", strip, repeated=True, pictures_only=True)  # a frame over it
            c.text(
                "level",
                game.tr("hud.level", "Lv {level}", level=progress.level),
                strip.centerx,
                strip.centery,
                size=14,
                color=(255, 255, 255),
                anchor="center",
            )

        # statuses above the bar (left) and the other resources (right)
        if state is not None:
            row_y = plate.y - 14 - 36 - 12
            cell = c.number("statuses", "cell", 34)
            step = cell + c.number("statuses", "gap", 8)
            row = c.rect("statuses", (plate.x, row_y, 12 * step - (step - cell), cell))
            if c.shown("statuses"):
                for k, entry in enumerate(active_statuses(game, state)[:12]):
                    self._status(rt, c, row[0] + k * step, row[1], cell, entry)
            place = c.rect("resource_bars", (plate.right - 150, plate.y - 20, 150, 14))
            step = c.row_height("resource_bars", 20)
            for k, name in enumerate(extras[:3] if c.shown("resource_bars") else ()):
                value = state.resources.get(name)
                frac = value.current / value.maximum if value.maximum else 0.0
                label = f"{name.capitalize()}  {value.current:.0f}/{value.maximum:.0f}"
                self._bar(
                    rt,
                    place[0],
                    place[1] - k * step,
                    place[2],
                    place[3],
                    frac,
                    resource_color(name, theme=c.theme),
                    label,
                    c,
                    "resource_bars",
                )

        # the controls, top centre, on a dark strip, fading out
        if self.hint_left > 0 and c.shown("hint"):
            alpha = min(1.0, self.hint_left / 2.0)
            if len(numbered) > 1:
                skills = game.tr("hud.skills", "Skills 1-{last}", last=len(numbered))
            else:
                skills = game.tr("hud.skill", "Skill 1")
            text = game.tr(
                "hud.controls",
                "Move WASD   Attack J   Dodge K   {skills}   Lock L   Pick up F   "
                "Bag B   Skill tree C   Pause Esc",
                skills=skills,
            )
            measure = getattr(rt, "text_size", None)
            if measure is not None:  # the face the line is drawn in (a CJK one for Chinese)
                w, h = measure(text, 17)
            else:
                font = rt._fonts.get(17) or rt._fonts.setdefault(17, pg.font.Font(None, 17))
                w, h = font.size(text)
            box = c.rect("hint", (width / 2 - (w + 24) / 2, 8, w + 24, h + 10))
            strip = pg.Surface((box[2], box[3]), pg.SRCALPHA)
            pg.draw.rect(strip, (8, 10, 18, int(190 * alpha)), strip.get_rect(), border_radius=8)
            screen.blit(strip, (box[0], box[1]))
            colour = tuple(int(60 + 170 * alpha) for _ in range(3))
            centre = (box[0] + box[2] / 2, box[1] + box[3] / 2)
            rt.text(text, *centre, size=17, color=colour, anchor="center")
        return c


def draw_status_pips(rt, x, y, entries, size=12, limit=6):
    """A compact row of status squares (frame colour = boon or harm, drain = time left), for the
    entities of the world (enemy overhead bars). ``x`` is the row's left edge."""
    pg, screen = rt.pg, rt.screen
    for k, entry in enumerate(entries[:limit]):
        good = entry["kind"] == "buff"
        frame = (96, 214, 130) if good else (226, 92, 84)
        rect = pg.Rect(int(x + k * (size + 2)), int(y), size, size)
        pg.draw.rect(screen, (20, 52, 32) if good else (62, 22, 24), rect, border_radius=3)
        icon = entry.get("icon", "")
        if not (icon and rt._draw_icon(icon, rect.x + 1, rect.y + 1, size - 2)):
            pg.draw.circle(screen, frame, rect.center, max(2, size // 4))
        fraction = max(0.0, min(1.0, entry["remaining"] / entry["total"]))
        if fraction < 1.0:
            shade = pg.Surface((size - 2, max(0, int((size - 2) * (1.0 - fraction)))), pg.SRCALPHA)
            shade.fill((0, 0, 0, 150))
            screen.blit(shade, (rect.x + 1, rect.y + 1))
        pg.draw.rect(screen, frame, rect, 1, border_radius=3)


def draw_target_frame(rt, game, entity, c=None):
    """The locked-on enemy at the top centre: its name, a life bar, and each boon / harm on it
    with its name and the seconds left (the small squares over its head say only which kind).
    ``c``: the HUD's canvas (the ``target`` element moves and reskins it)."""
    from .combat import CombatantComponent

    pg, screen = rt.pg, rt.screen
    c = c if c is not None else rt.menu_canvas("hud_action")
    if not c.shown("target"):
        return
    combatant = entity.try_get(CombatantComponent)
    state = combatant.state if combatant is not None else None
    if state is None or not combatant.life_resource:
        return
    entries = active_statuses(game, state)
    width = 320
    rows = max(1, min(4, len(entries)))
    height = 54 + (rows * 20 + 4 if entries else 0)
    x, y = rt.width // 2 - width // 2, 44
    x, y, width, _h = c.rect("target", (x, y, width, height))
    c.panel("target", (x, y, width, height), fill=(12, 14, 24, 225), border=(150, 110, 100))
    rt.text(entity.name, x + 12, y + 8, size=22, color=c.color("target", (255, 226, 190)))
    pool = state.resources.get(combatant.life_resource)
    fraction = pool.current / pool.maximum if pool.maximum else 0.0
    bar = pg.Rect(x + 12, y + 34, width - 24, 10)
    pg.draw.rect(screen, (20, 22, 30), bar.inflate(2, 2), border_radius=4)
    pg.draw.rect(screen, (60, 30, 30), bar, border_radius=4)
    pg.draw.rect(
        screen,
        (226, 70, 64),
        (bar.x, bar.y, int(bar.w * max(0.0, min(1.0, fraction))), bar.h),
        0,
        4,
    )
    for k, entry in enumerate(entries[:4]):
        row_y = y + 54 + k * 20
        good = entry["kind"] == "buff"
        frame = (96, 214, 130) if good else (226, 92, 84)
        chip = pg.Rect(x + 12, row_y, 16, 16)
        pg.draw.rect(screen, (20, 52, 32) if good else (62, 22, 24), chip, border_radius=3)
        icon = entry.get("icon", "")
        if not (icon and rt._draw_icon(icon, chip.x + 1, chip.y + 1, 14)):
            pg.draw.circle(screen, frame, chip.center, 4)
        pg.draw.rect(screen, frame, chip, 1, border_radius=3)
        stacks = f" x{entry['stacks']}" if entry["stacks"] > 1 else ""
        rt.text(entry["name"] + stacks, x + 36, row_y + 1, size=17, color=(225, 230, 240))
        seconds = entry["remaining"]
        rt.text(
            f"{seconds:.0f}s" if seconds >= 1 else f"{seconds:.1f}s",
            x + width - 12,
            row_y + 1,
            size=17,
            color=(170, 210, 240),
            anchor="topright",
        )


__all__ = [
    "BottomHud",
    "draw_target_frame",
    "active_statuses",
    "draw_status_pips",
    "key_label",
    "resource_color",
    "state_kind",
]
