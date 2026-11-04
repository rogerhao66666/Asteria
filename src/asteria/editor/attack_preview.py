"""The attack preview: a swordsman hits a monster, and this attack's own numbers play out.

``plan_for`` turns an attack into times and speeds the way the engine reads them (hit-stop, then a
push that fades, a lift that falls back, stun or a knock-down, i-frames), and ``target_state`` /
``attacker_state`` say where everyone is at any moment, so the drawing holds no rules of its own.
Silent, and it only runs while it can be seen.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetrics, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QPushButton, QWidget

from ..assets.library import find_pack
from ..gameplay.formulas import FormulaContext, ValueSource
from ..gameplay.tags import TagSet
from .i18n import translate
from .record_vocabulary import tag_label

# the engine's defaults for what a character brings to a hit (it is not part of the attack)
PUSH_DECAY = 10.0
GRAVITY = 600.0
DOWN_TIME = 1.0
GETUP_TIME = 0.5

LEAD = 0.3  # idle before the swing
SWING_STEP = 0.05  # a frame of the swing, as the game's own attack clip plays it
# the swordsman stands on the right: the pack draws the swing facing left from the top down (the
# one facing right goes from the bottom up, whatever order it plays in)
SWING_ORDER = (0, 1, 2, 3, 4, 5)
SWING_HIT_FRAME = 2  # the slash itself
SWING_HIT_STEP = SWING_ORDER.index(SWING_HIT_FRAME)
WINDUP = SWING_HIT_STEP * SWING_STEP
FOLLOW = (len(SWING_ORDER) - SWING_HIT_STEP) * SWING_STEP  # the slash and what comes after it
FLASH = 0.1
FLASH_WHITE = 0.6
FLINCH = 0.16  # the red frames of the monster's hurt sheet; after them a stun just stands dazed
FLINCH_FRAME = 2
FALL = 0.4
REST = 0.8  # standing again before the loop starts over
LOOP_FADE = 0.15  # a pushed monster fades back to where it started
SLOW = 0.25
TICK_MS = 33

FRAME = 48  # the sheets' frame size
FEET = 41  # the row under the characters' feet
REACH = 39  # how far apart the two stand
LUNGE = 16  # the step in: from there the slash reaches the monster
ATTACKER_RIGHT = 36  # the swordsman's back in the frame
TARGET_LEFT, TARGET_RIGHT = 10, 39  # the monster in its frame, falling included
TARGET_CHEST = 25  # where in its frame the monster is struck
FOOT_MIDDLE = 25

WARRIOR = "Foozle_2DC0009_Lucifer_Warrior_Pixel_Art"
SKELETON = "Foozle_2DC0018_Lucifer_Skeleton_Grunt_Pixel_Art"
SHEETS = {
    ("attacker", "idle"): (WARRIOR, "Left/Png/WarriorLeftIdle.png"),
    ("attacker", "swing"): (WARRIOR, "Left/Png/WarriorLeftAttack01.png"),
    ("target", "idle"): (SKELETON, "Right/Png/SkeletonWithSwordRightIdle.png"),
    ("target", "hurt"): (SKELETON, "Right/Png/SkeletonWithSwordRightHurt.png"),
    ("target", "down"): (SKELETON, "Right/Png/SkeletonWithSwordRightDeath.png"),
}
LYING_FRAME = 5  # flat on the ground


@dataclass(frozen=True)
class HitPlan:
    hit_at: float
    freeze: float
    stun: float
    down: float  # 0 = stays standing
    getup: float
    iframes: float
    push: float  # sideways speed; + is away from the swordsman
    lift: float  # upward speed

    @property
    def moves_at(self):
        """The freeze is over."""
        return self.hit_at + self.freeze

    @property
    def push_distance(self):
        return self.push / PUSH_DECAY

    @property
    def peak(self):
        return self.lift * self.lift / (2 * GRAVITY)

    @property
    def total(self):
        moved = self.moves_at
        return REST + max(
            moved + FOLLOW,
            moved + self.stun,
            moved + self.down + self.getup,
            moved + 2 * self.lift / GRAVITY,
            moved + (0.5 if self.push else 0.0),  # the push has faded by then
            self.hit_at + self.iframes,
        )


def plan_for(attack):
    """The numbers of a swordsman left of the monster, facing it: "away", "attacker_facing" and
    "fixed" all start from the right there and turn by the angle. The stage shows that scene turned
    round, because the art swings from the top down when it faces left."""
    angle = math.radians(attack.knockback_angle)
    down = (attack.knockdown_time or DOWN_TIME) if attack.knockdown else 0.0
    upward = attack.knockback_lift - math.sin(angle) * attack.knockback
    return HitPlan(
        hit_at=LEAD + WINDUP,
        freeze=max(0.0, attack.hitstop),
        stun=0.0 if down else max(0.0, attack.hitstun),  # a knock-down replaces the stun
        down=down,
        getup=GETUP_TIME if down else 0.0,
        iframes=max(0.0, attack.target_iframes),
        push=math.cos(angle) * attack.knockback,
        lift=max(0.0, upward),
    )


@dataclass(frozen=True)
class Figure:
    sheet: str
    frame: int
    x: float = 0.0  # world units from where it started: + is leftwards on the stage
    height: float = 0.0
    flash: bool = False
    faint: bool = False  # can't be hit right now
    dazed: bool = False  # stunned, past the flinch


def _idle_frame(t, frames):
    return int(t / 0.12) % frames


def _lunge(plan, t):
    """Steps in over the wind-up, and back at the end of the swing."""
    end = plan.moves_at + FOLLOW
    if t < LEAD or t >= end:
        return 0.0
    if t < plan.hit_at:
        return LUNGE * (t - LEAD) / WINDUP
    back = 2 * SWING_STEP
    return LUNGE * min(1.0, (end - t) / back)


def attacker_state(plan, t):
    x = _lunge(plan, t)
    if t < LEAD or t >= plan.moves_at + FOLLOW:
        return Figure("idle", _idle_frame(t, 5), x)
    if t < plan.hit_at:
        return Figure("swing", SWING_ORDER[int((t - LEAD) / SWING_STEP)], x)
    if t < plan.moves_at:
        return Figure("swing", SWING_HIT_FRAME, x)  # held through the freeze
    step = int((t - plan.moves_at) / SWING_STEP)  # the slash still shows without a freeze
    return Figure("swing", SWING_ORDER[min(len(SWING_ORDER) - 1, SWING_HIT_STEP + step)], x)


def target_state(plan, t):
    if t < plan.hit_at:
        return Figure("idle", _idle_frame(t, 6))
    since = max(0.0, t - plan.moves_at)  # nothing moves during the freeze
    x = plan.push_distance * (1 - math.exp(-PUSH_DECAY * since))
    height = max(0.0, plan.lift * since - 0.5 * GRAVITY * since * since)
    flash = t < plan.hit_at + max(plan.freeze, FLASH)
    faint = not flash and t < plan.hit_at + plan.iframes and int(t / 0.08) % 2 == 0
    sheet, frame = _target_pose(plan, since)
    dazed = not plan.down and FLINCH <= since < plan.stun
    return Figure(sheet, frame, x, height, flash, faint, dazed)


def target_fade(plan, t):
    """How much of the monster shows: one that was pushed fades back to its place at the loop."""
    if not plan.push_distance:
        return 1.0
    return max(0.0, min(1.0, t / LOOP_FADE, (plan.total - t) / LOOP_FADE))


def _target_pose(plan, since):
    if plan.down:
        fall = min(FALL, plan.down)
        if since < fall:
            return "down", min(LYING_FRAME, int(since / fall * (LYING_FRAME + 1)))
        if since < plan.down:
            return "down", LYING_FRAME
        if since < plan.down + plan.getup:
            left = (plan.down + plan.getup - since) / plan.getup
            return "down", min(LYING_FRAME, int(left * (LYING_FRAME + 1)))
    elif since < plan.stun:
        if since < FLINCH:
            return "hurt", FLINCH_FRAME + int(since / (FLINCH / 2))
        return "idle", 0  # dazed: it stops breathing, and stars circle its head
    return "idle", _idle_frame(since, 6)


class _SampleValues:
    """Stats and resources of nobody in particular: every one of them is 100."""

    SAMPLE = 100.0

    def get(self, _name, _default=0.0):
        return self.SAMPLE

    def current(self, _name):
        return self.SAMPLE

    def maximum(self, _name):
        return self.SAMPLE


def sample_damage(attack, formulas):
    """(the number a hit shows, whether it depends on stats); (None, False) without a formula, or
    when this formula can't be worked out without a real character."""
    formula = formulas.get(attack.damage_formula_id) if attack.damage_formula_id else attack.damage
    if formula is None:
        return None, False
    values = _SampleValues()
    context = FormulaContext(
        source_stats=values,
        source_resources=values,
        source_tags=TagSet(attack.tags),
        target_stats=values,
        target_resources=values,
        target_tags=TagSet(),
    )
    try:
        value = formula.evaluate(context)
    except Exception:  # an expression may read what a sample doesn't have
        return None, False
    reads_stats = bool(formula.expression) or any(
        term.source != ValueSource.CONSTANT for term in formula.terms
    )
    return value, reads_stats


_sprites = {}


def _sheet(side, name):
    """(picture, the same picture in solid white), or None when the art pack isn't there."""
    key = (side, name)
    if key not in _sprites:
        pack, path = SHEETS[key]
        image = QImage(str(find_pack(pack) / path))
        if image.isNull():
            _sprites[key] = None
        else:
            white = image.convertToFormat(QImage.Format_ARGB32_Premultiplied)
            painter = QPainter(white)
            painter.setCompositionMode(QPainter.CompositionMode_SourceAtop)
            painter.fillRect(white.rect(), QColor(255, 255, 255))
            painter.end()
            _sprites[key] = (QPixmap.fromImage(image), QPixmap.fromImage(white))
    return _sprites[key]


class _Preview(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.record = None
        self.setMinimumSize(190, 260)

    def show_record(self, record):
        self.record = record
        self.update()

    def _start(self):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(20, 22, 30))
        return painter

    @staticmethod
    def _caption(painter, x, y, text, color=QColor(170, 178, 196), size=10, bold=False):
        font = QFont()
        font.setPointSize(size)
        font.setBold(bold)
        painter.setFont(font)
        painter.setPen(color)
        painter.drawText(QPointF(x, y), text)


@dataclass(frozen=True)
class _Layout:
    chips: tuple  # (x, y, width, words, colour)
    top: float  # where the stage starts
    scale: int
    origin: float  # x of the monster's frame
    ground: float
    controls: float  # y of Pause and Slow Motion
    bars: float  # y of the time line under them


class AttackPreview(_Preview):
    """The hit, looping, with Pause under it and the time line of what it does under that; a
    playhead ties the two together."""

    BAR_ROW = 20
    BAR_LEFT = 112
    CHIPS_TOP = 36
    WORDS_HEIGHT = 40
    SKY = 36  # the most room over the figures

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(320)
        self.formulas = {}
        self.names = {}  # what the chips call a stat or a resource
        self.time = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(TICK_MS)
        self._timer.timeout.connect(self._tick)
        self.play_button = QPushButton(translate("Pause"))
        self.play_button.clicked.connect(self._toggle_play)
        self.slow_check = QCheckBox(translate("Slow Motion"))
        self.playing = True
        self.controls = QWidget(self)
        row = QHBoxLayout(self.controls)
        row.setContentsMargins(12, 0, 12, 0)
        row.addWidget(self.play_button)
        row.addWidget(self.slow_check)
        row.addStretch(1)

    # -- playing ----------------------------------------------------------------------------------
    def show_record(self, record):
        same = (
            record is not None
            and self.record is not None
            and record.attack_id == self.record.attack_id
        )
        if not same:
            self.time = 0.0
        super().show_record(record)
        self._place_controls()

    def seek(self, seconds):
        self.time = seconds
        self.update()

    def _tick(self):
        if self.record is None:
            return
        speed = SLOW if self.slow_check.isChecked() else 1.0
        self.seek((self.time + TICK_MS / 1000 * speed) % plan_for(self.record).total)

    def _toggle_play(self):
        self.playing = not self.playing
        self.play_button.setText(translate("Pause" if self.playing else "Play"))
        if self.playing and self.isVisible():
            self._timer.start()
        else:
            self._timer.stop()

    def showEvent(self, event):  # noqa: N802 - Qt API
        super().showEvent(event)
        if self.playing:
            self._timer.start()

    def hideEvent(self, event):  # noqa: N802 - Qt API
        super().hideEvent(event)
        self._timer.stop()

    def resizeEvent(self, event):  # noqa: N802 - Qt API
        super().resizeEvent(event)
        self._place_controls()

    def _place_controls(self):
        self.controls.setVisible(self.record is not None)
        if self.record is not None:
            height = self.controls.sizeHint().height()
            y = round(self._layout(self.record).controls)
            self.controls.setGeometry(0, y, self.width(), height)

    # -- drawing ----------------------------------------------------------------------------------
    def _name_of(self, key):
        return self.names.get(key) or key

    def _chips(self, attack, damage, reads_stats):
        chips = []
        if reads_stats:
            chips.append((translate("Sample: every stat is 100"), QColor(170, 178, 196)))
        plan = plan_for(attack)
        if not damage and not self._nothing_happens(attack, plan, damage):
            chips.append((translate("No damage"), QColor(170, 178, 196)))
        if attack.damage_resource:
            words = f"{translate('Lowers')} {self._name_of(attack.damage_resource)}"
            chips.append((words, QColor(255, 150, 150)))
        if attack.critical_chance or attack.critical_chance_stat:
            chips.append((self._critical_words(attack), QColor(255, 226, 120)))
        if attack.knockback:
            chips.append((self._push_words(attack), QColor(255, 196, 90)))
        if attack.knockback_lift:
            chips.append(
                (f"{translate('Lift')} {attack.knockback_lift:g}/s", QColor(255, 196, 90))
            )
        if attack.knockdown:
            chips.append((translate("Knocks down"), QColor(255, 140, 90)))
        if attack.hitstop and attack.hitstop_scope == "global":
            chips.append((translate("Freezes the whole game"), QColor(255, 220, 120)))
        if attack.max_targets:
            words = f"{translate('Targets')} ≤ {attack.max_targets}"
            chips.append((words, QColor(140, 200, 255)))
        if attack.armor_break:
            words = f"{translate('Breaks armor')} ≤ {attack.armor_break}"
            chips.append((words, QColor(200, 140, 255)))
        if attack.poise_damage:
            words = f"{translate('Poise')} −{attack.poise_damage:g}"
            chips.append((words, QColor(120, 200, 255)))
        if attack.on_hit_event:
            words = f"{translate('On Hit')}: {attack.on_hit_event}"
            chips.append((words, QColor(140, 220, 160)))
        if attack.tags:
            words = ", ".join(tag_label(tag, self.names) for tag in attack.tags)
            chips.append((words, QColor(140, 220, 160)))
        return chips

    def _critical_words(self, attack):
        words = f"{translate('Crit')} {attack.critical_chance * 100:g}%"
        if attack.critical_chance_stat:
            words += f" + {self._name_of(attack.critical_chance_stat)}"
        return f"{words} ×{attack.critical_multiplier:g}"

    @staticmethod
    def _push_words(attack):
        words = f"{translate('Push')} {attack.knockback:g}/s"
        if attack.knockback_angle:
            words += f" {attack.knockback_angle:g}°"
        if attack.knockback_direction == "attacker_facing":
            words += f" ({translate('Where the attacker faces')})"
        elif attack.knockback_direction == "fixed":
            words += f" ({translate('Fixed direction')})"
        return words

    def _chip_rects(self, chips):
        """Wrapping to the width: (the chips placed, where the stage can start)."""
        font = QFont()
        font.setPointSize(10)
        metrics = QFontMetrics(font)
        widest = max(40, self.width() - 24)
        x, y = 12, self.CHIPS_TOP
        placed = []
        for text, color in chips:
            text = metrics.elidedText(text, Qt.ElideRight, widest - 14)
            width = metrics.horizontalAdvance(text) + 14
            if x > 12 and x + width > self.width() - 12:
                x, y = 12, y + 24
            placed.append((x, y, width, text, color))
            x += width + 6
        return tuple(placed), y + 24 if chips else y

    def _draw_chips(self, painter, placed):
        for x, y, width, text, color in placed:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(color.red(), color.green(), color.blue(), 50))
            painter.drawRoundedRect(QRectF(x, y, width, 20), 9, 9)
            self._caption(painter, x + 7, y + 14, text, color)

    def _bar_rows(self, plan):
        rows = (
            ("Freeze on hit", plan.hit_at, plan.freeze, QColor(255, 220, 120)),
            ("Target stunned", plan.moves_at, plan.stun, QColor(255, 140, 120)),
            ("Knocked down", plan.moves_at, plan.down, QColor(255, 110, 90)),
            ("Can't be hit", plan.hit_at, plan.iframes, QColor(120, 200, 255)),
        )
        return [row for row in rows if row[2]]

    def _under_stage(self, attack, plan, damage):
        """The height of what goes under Pause: the time line, or the words saying why not."""
        if self._nothing_happens(attack, plan, damage):
            return self.WORDS_HEIGHT
        return len(self._bar_rows(plan)) * self.BAR_ROW

    def _layout(self, attack):
        """Name, chips, stage, Pause, time line, one under the other. The figures scale by whole
        pixels; what's left of a tall panel stays below it all, not between."""
        plan = plan_for(attack)
        damage, reads_stats = sample_damage(attack, self.formulas)
        placed, top = self._chip_rects(self._chips(attack, damage, reads_stats))
        controls = self.controls.sizeHint().height()
        below = 10 + controls + 10 + self._under_stage(attack, plan, damage) + 12
        left = TARGET_LEFT - max(0.0, plan.push_distance)
        right = max(REACH + ATTACKER_RIGHT, TARGET_RIGHT - plan.push_distance)
        across = (self.width() - 24) / (right - left)
        up = (self.height() - top - below - 8) / (FEET + plan.peak)
        scale = max(1, min(4, math.floor(min(across, up))))
        origin = (self.width() - (right - left) * scale) / 2 - left * scale
        tall = (FEET + plan.peak) * scale + 8
        spare = max(0.0, self.height() - top - below - tall)
        ground = top + min(spare, self.SKY) + tall
        controls_y = ground + 10
        return _Layout(placed, top, scale, origin, ground, controls_y, controls_y + controls + 10)

    def _draw_figure(self, painter, side, figure, x, ground, scale, fade=1.0):
        pictures = _sheet(side, figure.sheet)
        foot_x = x - figure.x * scale
        foot_y = ground - figure.height * scale
        shrink = 1 / (1 + figure.height / 40)  # the shadow stays down, and shrinks as it rises
        painter.setOpacity(fade)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 110))
        painter.drawEllipse(
            QPointF(foot_x + FOOT_MIDDLE * scale, ground), 11 * scale * shrink, 2 * scale * shrink
        )
        painter.setOpacity(fade * (0.35 if figure.faint else 1.0))
        if pictures is None:
            self._draw_stand_in(painter, side, figure, foot_x, foot_y, scale)
        else:
            source = QRectF(figure.frame * FRAME, 0, FRAME, FRAME)
            target = QRectF(foot_x, foot_y - FEET * scale, FRAME * scale, FRAME * scale)
            painter.drawPixmap(target, pictures[0], source)
            if figure.flash:  # part white: all white would melt into the slash, which is white
                painter.setOpacity(fade * FLASH_WHITE)
                painter.drawPixmap(target, pictures[1], source)
        if figure.dazed:
            self._draw_stars(painter, foot_x + FOOT_MIDDLE * scale, foot_y - 32 * scale, scale)
        painter.setOpacity(1.0)

    def _draw_stars(self, painter, x, y, scale):
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(255, 226, 120))
        for index in range(3):
            turn = self.time * 7 + index * 2 * math.pi / 3
            at = QPointF(x + math.cos(turn) * 9 * scale, y + math.sin(turn) * 2 * scale)
            painter.drawEllipse(at, scale, scale)

    @staticmethod
    def _draw_stand_in(painter, side, figure, x, y, scale):
        """No art pack: circles that move the same way."""
        lying = figure.sheet == "down" and figure.frame == LYING_FRAME
        center_x = x + FRAME / 2 * scale
        rx = 12 * scale
        ry = (5 if lying else 12) * scale
        if figure.flash:
            color = QColor(255, 255, 255)
        else:
            color = QColor(90, 170, 255) if side == "attacker" else QColor(224, 92, 100)
        painter.setPen(Qt.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(QPointF(center_x, y - ry), rx, ry)
        if figure.sheet == "swing" and figure.frame == SWING_HIT_FRAME:
            painter.setPen(QPen(QColor(230, 236, 250), 3))
            painter.drawLine(
                QPointF(center_x, y - 12 * scale),
                QPointF(x, y - 12 * scale),
            )

    def _draw_hit(self, painter, plan, x, ground, scale, damage):
        """The burst where the blow lands, and the number rising off the target."""
        since = self.time - plan.hit_at
        if since < 0:
            return
        at = x + TARGET_CHEST * scale
        high = ground - 22 * scale
        if since < max(plan.freeze, FLASH):
            grown = min(1.0, 0.4 + since / 0.06)
            painter.setPen(QPen(QColor(255, 240, 170), max(2.0, scale)))
            for index in range(8):
                turn = index * math.pi / 4 + math.pi / 8
                inner, outer = 3 * scale, (7 if index % 2 else 11) * scale * grown
                painter.drawLine(
                    QPointF(at + math.cos(turn) * inner, high + math.sin(turn) * inner),
                    QPointF(at + math.cos(turn) * outer, high + math.sin(turn) * outer),
                )
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(255, 252, 230))
            painter.drawEllipse(QPointF(at, high), 2.5 * scale, 2.5 * scale)
        if damage and since < 0.8:
            words = f"−{damage:g}" if damage > 0 else f"+{-damage:g}"
            fade = 1.0 if since < 0.5 else (0.8 - since) / 0.3
            y = ground - 38 * scale - min(since, 0.4) * 60
            painter.setOpacity(fade)
            self._caption(painter, at + 1, y + 1, words, QColor(0, 0, 0), 15, True)
            self._caption(painter, at, y, words, QColor(255, 226, 120), 15, True)
            painter.setOpacity(1.0)

    def _draw_bars(self, painter, plan, top):
        rows = self._bar_rows(plan)
        if not rows:
            return
        width = self.width() - self.BAR_LEFT - 16
        per_second = width / plan.total
        for index, (label, start, seconds, color) in enumerate(rows):
            y = top + index * self.BAR_ROW
            self._caption(painter, 12, y + 11, translate(label))
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(44, 48, 62))
            painter.drawRoundedRect(QRectF(self.BAR_LEFT, y, width, 12), 4, 4)
            bar_x = self.BAR_LEFT + start * per_second
            bar_width = max(3.0, seconds * per_second)
            painter.setBrush(color)
            painter.drawRoundedRect(QRectF(bar_x, y, bar_width, 12), 4, 4)
            words = f"{seconds:g}s"
            metrics = QFontMetrics(painter.font())
            words_x = bar_x + bar_width + 4
            if words_x + metrics.horizontalAdvance(words) > self.BAR_LEFT + width:
                words_x = bar_x - metrics.horizontalAdvance(words) - 4
            self._caption(painter, words_x, y + 11, words, color)
        head = self.BAR_LEFT + self.time * per_second
        painter.setPen(QPen(QColor(235, 240, 250), 1.5))
        painter.drawLine(QPointF(head, top - 4), QPointF(head, top + len(rows) * self.BAR_ROW - 4))

    def _nothing_happens(self, attack, plan, damage):
        return not (plan.freeze or plan.stun or plan.down or plan.iframes or damage) and not (
            attack.knockback or attack.knockback_lift
        )

    def _no_effect_words(self, damage):
        if damage:
            return "No push, stun or freeze: this hit only deals its damage."
        return "No damage, push, stun or freeze: this hit does nothing yet."

    def paintEvent(self, _event):  # noqa: N802 - Qt API
        painter = self._start()
        attack = self.record
        if attack is None:
            painter.end()
            return
        plan = plan_for(attack)
        damage, _reads_stats = sample_damage(attack, self.formulas)
        layout = self._layout(attack)
        width = self.width()
        scale, origin, ground = layout.scale, layout.origin, layout.ground
        self._caption(painter, 12, 25, attack.display_name or attack.attack_id, size=13, bold=True)
        self._draw_chips(painter, layout.chips)
        painter.setPen(QPen(QColor(70, 76, 96), 2))
        painter.drawLine(QPointF(12, ground), QPointF(width - 12, ground))
        painter.setRenderHint(QPainter.SmoothPixmapTransform, False)
        painter.setClipRect(QRectF(0, layout.top, width, ground + scale - layout.top))
        attacker = attacker_state(plan, self.time)
        target = target_state(plan, self.time)
        self._draw_figure(painter, "attacker", attacker, origin + REACH * scale, ground, scale)
        self._draw_figure(
            painter, "target", target, origin, ground, scale, target_fade(plan, self.time)
        )
        self._draw_hit(painter, plan, origin - target.x * scale, ground, scale, damage)
        painter.setClipping(False)
        if self._nothing_happens(attack, plan, damage):
            painter.setPen(QColor(170, 178, 196))
            painter.drawText(
                QRectF(12, layout.bars, width - 24, self.WORDS_HEIGHT),
                Qt.TextWordWrap | Qt.AlignLeft | Qt.AlignTop,
                translate(self._no_effect_words(damage)),
            )
        else:
            self._draw_bars(painter, plan, layout.bars)
        painter.end()
