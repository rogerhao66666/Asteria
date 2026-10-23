from __future__ import annotations

from dataclasses import dataclass, fields
from math import isfinite

from asteria.runtime import Camera2D

from .battle import BattlePresentationScene
from .battle_action_menu import BattleActionMenuView
from .battle_action_workflow import BattleActionWorkflowView
from .battle_camera_feedback import BattleCameraFeedbackFrame
from .battle_feedback import BattleFeedbackRuntime, BattleValueKind
from .battle_hud import BattleHudMember
from .battle_party_layout import BattlePartyLayoutPolicy
from .battle_result import BattleResultView
from .battle_runtime import BattlePresentationFrame
from .battle_turn_timeline import BattleTurnTimelineView
from .battle_ui_polish import BattleUiPolishProfile
from .text_cells import cells, cut, wrap

# what the command menu's layout reads: every field of the menu view but its revision count
# (the adapter sets the same entries again each frame, and each set counts)
_MENU_LAYOUT_FIELDS = tuple(f.name for f in fields(BattleActionMenuView) if f.name != "revision")

# where a party card shows its member's portrait (``BattleUiLayoutProfile.hud_portraits``)
HUD_PORTRAITS = ("left", "right", "above", "off")
PORTRAIT_MIN = 10.0  # layout units: a card with less room than this for a portrait shows none
PORTRAIT_LARGE = 32.0  # a portrait this large or larger shows the large picture, else the small
BAR_MIN = 24.0  # the narrowest a card's bars get to make room for its portrait
BOTTOM_ROW_HEIGHT = 24.0  # a bottom-row party cell without a portrait


def _value_text(value):
    """A floating number: whole from 10 up (a share of health is not 604.444, a million is
    not 1e+06), as written below that (a 0.5 gauge step)."""
    return str(round(value)) if abs(value) >= 10 else f"{value:g}"


def _finite(value, label):
    value = float(value)
    if not isfinite(value):
        raise ValueError(f"{label} must be finite")
    return value


@dataclass(frozen=True, slots=True)
class BattleUiLayoutProfile:
    virtual_width: int = 320
    virtual_height: int = 180
    margin: float = 8.0
    hud_panel_width: float = 112.0
    hud_row_height: float = 10.0
    timeline_y: float = 7.0
    result_panel_width: float = 196.0
    result_panel_height: float = 116.0
    # Side-view staging options (defaults keep the original column HUD):
    # party_hud "column" | "bottom_row" (one compact cell per member along the bottom) |
    # "side_list" (a panel per member down the party's edge: name, status chips, one
    # "label  current / maximum" line with a bar per resource - the Octopath Traveler look);
    # overhead_zones: placement zones whose members show a bar over their sprite
    # instead of a HUD panel; action_menu_placement "bottom" | "actor" (beside the
    # acting member); stage_top: fraction of the height where the ground begins;
    # stage_front: how far in from each edge the front columns stand (fraction of the stage width).
    party_hud: str = "column"
    overhead_zones: tuple = ()
    # hidden_zones: placement zones whose members get no HUD at all (no panel, bar or name),
    # e.g. enemies in a game that never shows their health
    hidden_zones: tuple = ()
    # front_large_zones: placement zones where oversized combatants (a summon, a mount) stand in
    # front of the others, toward the centre of the stage, instead of behind them
    front_large_zones: tuple = ()
    action_menu_placement: str = "bottom"
    # column_size: how many combatants of one side share a column of the stage before the next
    # column starts behind them
    column_size: int = 3
    # menu_over_stage: the command menu stands right beside the acting member even when it
    # overlaps the other party members (it is drawn see-through); it never covers the acting
    # member or an enemy
    menu_over_stage: bool = False
    # row_buttons: every row of a menu gets a panel of its own (roles button, button:selected,
    # button:disabled) so a skin can draw buttons; off = rows are plain text
    row_buttons: bool = False
    # overhead_below: an overhead name and bar sit under the sprite's feet (they never cover the
    # body or the combatant behind); off = floating above the head
    overhead_below: bool = True
    # command_counts: a top-level command shows a number beside it (how many choices it opens,
    # Escape's chance); off = names alone
    command_counts: bool = False
    # overhead_bars: an overhead member shows its top resource as a bar under the name; off = the
    # name alone (a game that keeps enemy health hidden)
    overhead_bars: bool = True
    stage_top: float = 0.0
    stage_front: float = 0.30
    # stage_front_right: the same for the side standing on the right (None = stage_front), so the
    # party can stand nearer its edge while the foes stand nearer the middle
    stage_front_right: float | None = None
    # column_spacing: how far apart neighbouring columns of one side stand, centre to centre
    # (layout units); 0 = automatic: far enough that their whole frames never overlap. A column
    # holding an oversized combatant (a boss) always keeps the automatic distance
    column_spacing: float = 0.0
    # column_spacing_right: the same for the side standing on the right (None = column_spacing)
    column_spacing_right: float | None = None
    # feet_on_ground: every combatant's feet stay on the ground band (stage_top down to the
    # bottom of the stage), also where a Side-View Positions or Portrait Party Layout record puts
    # them higher or lower; a sprite's own offset still lifts a flyer. Off = a record's positions
    # are used as written
    feet_on_ground: bool = True
    # stage_template: a Side-View Positions or Portrait Party Layout record the combatants stand
    # by ("" = the automatic columns); an encounter's ``stage:<id>`` tag picks one for its fight
    stage_template: str = ""
    # command_pages: the Command Menu Pages record that orders, renames and hides the top-level
    # commands and sets how many rows one page of a list shows ("" = every command and row)
    command_pages: str = ""
    # hud_portraits: where a party card shows its member's portrait (set on the member's
    # Combatant Sprites record): "left" or "right" of the name and bars, "above" them (the card
    # grows taller) or "off"; a card without a portrait is drawn as it always was
    hud_portraits: str = "left"
    # hud_portrait_size: the side of the portrait's square, layout units (0 = as tall as the
    # card's rows); never more than leaves the name and bars their room, and beside them never
    # taller than they are (a larger one needs "above")
    hud_portrait_size: float = 0.0

    def __post_init__(self):
        if self.virtual_width <= 0 or self.virtual_height <= 0:
            raise ValueError("virtual battle UI size must be positive")
        object.__setattr__(self, "overhead_zones", tuple(str(x) for x in self.overhead_zones))
        object.__setattr__(self, "hidden_zones", tuple(str(x) for x in self.hidden_zones))
        object.__setattr__(
            self, "front_large_zones", tuple(str(x) for x in self.front_large_zones)
        )
        if int(self.column_size) < 1:
            raise ValueError("column_size must be >= 1")
        if self.party_hud not in {"column", "bottom_row", "side_list"}:
            raise ValueError("party_hud must be 'column', 'bottom_row' or 'side_list'")
        if self.action_menu_placement not in {"bottom", "actor", "actor_bottom_right"}:
            raise ValueError(
                "action_menu_placement must be 'bottom', 'actor' or 'actor_bottom_right'"
            )
        hud_portraits = self.hud_portraits
        if hud_portraits not in HUD_PORTRAITS:  # the editor offers these values (engine_enums)
            raise ValueError("hud_portraits must be 'left', 'right', 'above' or 'off'")
        if not 0.0 <= float(self.stage_top) < 1.0:
            raise ValueError("stage_top must be in [0, 1)")
        if self.stage_front_right is not None and not 0.0 <= float(self.stage_front_right) <= 0.5:
            raise ValueError("stage_front_right must be in [0, 0.5]")
        if not 0.0 <= float(self.stage_front) <= 0.5:
            raise ValueError("stage_front must be in [0, 0.5]")
        if self.column_spacing_right is not None:
            if _finite(self.column_spacing_right, "column_spacing_right") < 0:
                raise ValueError("column_spacing_right must be >= 0")
        for name in (
            "column_spacing",
            "margin",
            "hud_panel_width",
            "hud_row_height",
            "result_panel_width",
            "result_panel_height",
            "hud_portrait_size",
        ):
            if _finite(getattr(self, name), name) < 0:
                raise ValueError(f"{name} must be >= 0")


@dataclass(frozen=True, slots=True)
class BattleUiText:
    text: str
    x: float
    y: float
    role: str = "body"
    align: str = "left"
    member_id: str = ""


@dataclass(frozen=True, slots=True)
class BattleUiPanel:
    panel_id: str
    x: float
    y: float
    width: float
    height: float
    role: str = "panel"
    member_id: str = ""


@dataclass(frozen=True, slots=True)
class BattleUiGaugeBar:
    member_id: str
    resource_id: str
    label: str
    x: float
    y: float
    width: float
    height: float
    normalized: float
    current: float
    maximum: float
    presentation: str = "bar"
    segments: int = 0
    icon_asset_id: str | None = None
    color: str = ""  # "#rrggbb" fill; empty: the theme's


@dataclass(frozen=True, slots=True)
class BattleUiIcon:
    asset_id: str
    x: float
    y: float
    role: str
    member_id: str = ""
    label: str = ""


@dataclass(frozen=True, slots=True)
class BattleUiMarker:
    member_id: str
    x: float
    y: float
    primary: bool = False


@dataclass(frozen=True, slots=True)
class BattleUiPortrait:
    """A party card's portrait: the picture ``asset_id`` fitted inside the box with its
    proportions kept."""

    member_id: str
    asset_id: str
    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True, slots=True)
class BattleUiFrame:
    scene_id: str
    background_asset_id: str
    combatant_draws: tuple
    panels: tuple[BattleUiPanel, ...]
    texts: tuple[BattleUiText, ...]
    gauges: tuple[BattleUiGaugeBar, ...]
    icons: tuple[BattleUiIcon, ...]
    markers: tuple[BattleUiMarker, ...]
    vfx: tuple
    screen_fx: tuple
    portraits: tuple[BattleUiPortrait, ...] = ()  # drawn over the party cards' panels


MARK_ROLE = ":mark"  # a row's cursor or tick, drawn by the backend level with its label


MENU_COST_GAP = 4.0  # layout units kept between a menu row's name and its cost


def _mark_gutter(*prefixes):
    """Room before a row's label for its mark, in layout units: the widest mark and a small gap
    (what its trailing spaces gave before). Every row's label starts at the same place, marked
    or not."""
    widest = max(len(p.strip()) for p in prefixes)
    return widest * 3.8 + 2.0 if widest else 0.0


def _gap(a, b):
    """How far apart two ``(x, y, w, h)`` boxes are (0 when they touch or overlap)."""
    dx = max(b[0] - (a[0] + a[2]), a[0] - (b[0] + b[2]), 0.0)
    dy = max(b[1] - (a[1] + a[3]), a[1] - (b[1] + b[3]), 0.0)
    return max(dx, dy)


def _portrait_side(layout, rows, room):
    """The side of a party card's portrait square: ``hud_portrait_size``, else as tall as the
    card's ``rows`` less their padding; never more than ``room``, and beside the rows never
    taller than they are. 0 when that is less than PORTRAIT_MIN (the card shows none)."""
    side = min(float(layout.hud_portrait_size) or rows - 4.0, room)
    if layout.hud_portraits != "above":
        side = min(side, rows - 4.0)
    return side if side >= PORTRAIT_MIN else 0.0


def bottom_row_height(layout, portraits=False):
    """How tall the bottom-row party HUD (``party_hud="bottom_row"``) stands, layout units: its
    cells, and the portraits over them when they show ``portraits`` (``hud_portraits=
    "above"``; beside the rows a portrait never makes a cell taller). The stage keeps the
    combatants' feet above it."""
    if not portraits or getattr(layout, "hud_portraits", "left") != "above":
        return BOTTOM_ROW_HEIGHT
    side = float(getattr(layout, "hud_portrait_size", 0.0)) or BOTTOM_ROW_HEIGHT - 4.0
    side = min(side, float(getattr(layout, "virtual_height", 180)) / 2 - BOTTOM_ROW_HEIGHT - 2.0)
    return BOTTOM_ROW_HEIGHT + side + 2.0 if side >= PORTRAIT_MIN else BOTTOM_ROW_HEIGHT


def _category_strip(categories, active, room, shown_as=None):
    """``Attack  [Skills]  Combo`` within ``room`` layout units: the active category and as
    many of its neighbours as fit, ``‹`` / ``›`` where more lie past the edge (the whole row ran
    out of the menu, under the panels beside it). ``shown_as`` maps a category (an id) to the
    name drawn for it."""
    at = list(categories).index(active) if active in categories else 0
    names = [(shown_as or {}).get(c, c) for c in categories]

    def text(lo, hi):
        shown = "  ".join(f"[{v}]" if i == at else v for i, v in enumerate(names) if lo <= i < hi)
        return ("< " if lo > 0 else "") + shown + (" >" if hi < len(names) else "")

    lo, hi = at, at + 1
    while True:
        grown = False
        for candidate in ((lo, hi + 1), (lo - 1, hi)):  # the next one first, then the one before
            a, b = candidate
            if 0 <= a and b <= len(names) and cells(text(a, b)) * 3.8 <= room:
                lo, hi, grown = a, b, True
        if not grown:
            return text(lo, hi)


def _marked(prefix, label, left, gutter, y, role):
    """A row's label and, apart from it, its mark (``▶``, ``✓``...): the backend draws the mark
    centred on the label's letters, whatever font each is drawn in (a symbol the pixel font
    lacked came from another font and sat crooked beside the name)."""
    texts = []
    mark = prefix.strip()
    if mark:
        texts.append(BattleUiText(mark, left, y, role + MARK_ROLE, "left"))
    texts.append(BattleUiText(label, left + gutter, y, role, "left"))
    return texts


class BattleUiComposer:
    """Composes existing Battle Presentation view-state into adapter-ready UI.

    This layer owns layout only. It never reads or mutates Battle Core, resolves
    targets, changes resources, advances scheduler time, or applies rewards.
    """

    MIN_MENU_WIDTH = 96.0
    TIMELINE_CHAR_WIDTH = 5.0

    def __init__(
        self, scene: BattlePresentationScene, layout=None, party_layout=None, polish=None
    ):
        if not isinstance(scene, BattlePresentationScene):
            raise TypeError("scene must be BattlePresentationScene")
        self.scene = scene
        self.layout = layout or BattleUiLayoutProfile()
        if not isinstance(self.layout, BattleUiLayoutProfile):
            raise TypeError("layout must be BattleUiLayoutProfile")
        self.party_layout = party_layout or BattlePartyLayoutPolicy()
        if not isinstance(self.party_layout, BattlePartyLayoutPolicy):
            raise TypeError("party_layout must be BattlePartyLayoutPolicy")
        self.polish = polish or BattleUiPolishProfile()
        if not isinstance(self.polish, BattleUiPolishProfile):
            raise TypeError("polish must be BattleUiPolishProfile")
        self._display_names = {}
        self._member_heights = {}
        self._camera = None
        self._focus = None
        self.overhead_labels = {}  # member_id: (x, y, w, h) of its overhead label, last frame
        self._hud_cache = None  # (inputs, commands, overhead_labels) of the last HUD layout
        self._menu_cache = None  # (inputs, commands) of the last command menu layout
        # (text, role) -> layout units as the backend draws it (an adapter sets it), so
        # a menu row's name and cost are fitted by their real widths
        self.text_width = None
        self._category_names = {}  # a menu category (id) -> the name drawn for it
        self._translate = None  # (key, english, **params) -> text: the screen's own words
        self._portraits = {}  # member_id: (portrait, small portrait) its party card may show
        self.portrait_boxes = {}  # member_id: (x, y, w, h) of its card's portrait, this frame

    def _name(self, member_id):
        return self._display_names.get(str(member_id), str(member_id))

    def _card_portrait(self, member_id, rows, room):
        """``(side, picture)`` of the portrait a party card shows: its square's side in layout
        units (``_portrait_side``) and the asset - the large portrait from PORTRAIT_LARGE up,
        else the small one, each standing in for the other - or ``(0.0, "")`` for none."""
        large, small = self._portraits.get(str(member_id), ("", ""))
        if self.layout.hud_portraits == "off" or not (large or small):
            return 0.0, ""
        side = _portrait_side(self.layout, rows, room)
        if not side:
            return 0.0, ""
        return side, (large or small) if side >= PORTRAIT_LARGE else (small or large)

    def _portrait_rows(self, side, x, width, height):
        """How a party card ``width`` x ``height`` at ``x`` makes room for a ``side`` portrait:
        ``(x, width, lift, height)`` of its rows - where they start, how wide they are, how far
        down they move - and the card's new height (beside the rows it is at least as tall as
        the portrait; over them it grows by it). No portrait: the card as it was."""
        place = self.layout.hud_portraits
        if not side:
            return x, width, 0.0, height
        if place == "above":
            return x, width, side + 2.0, height + side + 2.0
        shift = side + 2.0
        return (x + shift if place == "left" else x), width - shift, 0.0, max(height, side + 4.0)

    def _portrait(self, member_id, picture, side, card, inset):
        """The portrait of a party card ``(x, y, width, height)``: at its left or right end,
        centred on its height, or over its rows where the name starts (``inset`` in)."""
        x, y, width, height = card
        if self.layout.hud_portraits == "above":
            return BattleUiPortrait(member_id, picture, x + inset, y + 2.0, side, side)
        px = x + 2.0 if self.layout.hud_portraits == "left" else x + width - 2.0 - side
        return BattleUiPortrait(member_id, picture, px, y + (height - side) / 2, side, side)

    def _tr(self, key, english, **params):
        """One of the screen's own words in the game's language (``rpg.built_in_text``)."""
        if self._translate is not None:
            return self._translate(key, english, **params)
        return english.format(**params) if params else english

    def _drawn_width(self, text, role):
        """How wide ``text`` is drawn in ``role``, in layout units (``text_width`` measures it,
        else about 3.8 a character)."""
        if self.text_width is None:
            return cells(text) * 3.8
        return float(self.text_width(text, role))

    def _row_units(self, entry):
        """A menu row's name as the selected row draws it (a size larger) and its cost, with
        the space kept between them."""
        units = self._drawn_width(entry.label, "action_selected")
        if entry.cost_text:
            units += MENU_COST_GAP + self._drawn_width(entry.cost_text, "action_cost")
        return units

    def _fit_width(self, label, room):
        """``label`` as the selected row draws it, inside ``room`` layout units: shortened with
        ".." where it is wider (a crowded row keeps at least a letter)."""
        if self._drawn_width(label, "action_selected") <= room:
            return label
        for keep in range(cells(label) - 1, 0, -1):
            short = cut(label, keep).rstrip() + ".."
            if self._drawn_width(short, "action_selected") <= room:
                return short
        return cut(label, 1).rstrip() + ".."

    @staticmethod
    def _fit(text, max_chars):
        """Shorten to ``max_chars`` cells (a full-width character takes two), keeping the last
        word (e.g. "Hero 06" -> "H06")."""
        text = str(text)
        if cells(text) <= max_chars:
            return text
        words = text.split()
        if len(words) > 1:
            short = "".join(w[0] for w in words[:-1]) + words[-1]
            if cells(short) <= max_chars:
                return short
        return (cut(text, max(1, max_chars - 1)) or text[:1]) + "."

    def _anchor_screen(self, camera, member_id):
        try:
            visual = self.scene.visual_for(member_id)
        except KeyError:
            return None
        return camera.world_to_screen(visual.anchor.x, visual.anchor.y)

    def _hud_commands(
        self, members, side_by_member, placement_by_member=None, focus_member_id=None
    ):
        """The member HUD (panels, overhead labels): laid out again only when something it
        reads changed since the last frame, else the last frame's commands."""
        L = self.layout
        anchors = None
        if L.overhead_zones and self._camera is not None:  # overhead labels follow the figures
            to_screen = self._camera.world_to_screen
            anchors = tuple(
                (v.member_id, to_screen(v.anchor.x, v.anchor.y)) for v in self.scene.combatants
            )
        key = (
            tuple(members),
            dict(side_by_member or {}),
            dict(placement_by_member or {}),
            focus_member_id,
            self._display_names,
            self._member_heights,
            anchors,
            L,
            self._member_extents,
            self._overhead_hidden,
            None if self._camera is None else self._camera.zoom,
            self.party_layout,
            self.polish,
            self._portraits,
        )
        cached = self._hud_cache
        if cached is not None and cached[0] == key:
            self.overhead_labels = dict(cached[2])
            return tuple(list(x) for x in cached[1])
        out = self._hud_layout(*key[:4])
        self._hud_cache = (key, tuple(tuple(x) for x in out), dict(self.overhead_labels))
        return out

    def _hud_layout(self, members, side_by_member, placement_by_member, focus_member_id):
        panels, texts, gauges, icons, portraits = [], [], [], [], []
        L = self.layout

        # Explicit presentation placement wins. Legacy side metadata remains only
        # for backward compatibility with pre-Batch-105 projects.
        explicit = {str(k): str(v) for k, v in dict(placement_by_member or {}).items()}
        legacy = {str(k): str(v) for k, v in dict(side_by_member or {}).items()}

        # Legacy direct-call compatibility groups members by opaque side ID, but
        # never interprets side names. Distinct groups are assigned visual zones
        # deterministically by first appearance. Projects should prefer explicit
        # placement metadata when more than two presentation zones are desired.
        side_order = []
        for member in members:
            side = legacy.get(member.member_id, "")
            if side and side not in side_order:
                side_order.append(side)
        fallback_zone = {
            side: ("left" if index % 2 == 0 else "right") for index, side in enumerate(side_order)
        }

        zone_by_member = {}
        for member in members:
            member_id = member.member_id
            if member_id in explicit:
                zone_by_member[member_id] = explicit[member_id]
            else:
                side = legacy.get(member_id, "")
                zone_by_member[member_id] = fallback_zone.get(side, self.party_layout.default_zone)

        members = [m for m in members if zone_by_member[m.member_id] not in L.hidden_zones]
        overhead = [m for m in members if zone_by_member[m.member_id] in L.overhead_zones]
        if overhead and self._overhead_hidden:  # the camera is zoomed in: names wait
            self.overhead_labels = {}
            members = [m for m in members if zone_by_member[m.member_id] not in L.overhead_zones]
        elif overhead:
            o_panels, o_texts, o_gauges = self._overhead_commands(overhead)
            panels.extend(o_panels)
            texts.extend(o_texts)
            gauges.extend(o_gauges)
            members = [m for m in members if zone_by_member[m.member_id] not in L.overhead_zones]
        if L.party_hud == "bottom_row":
            b_panels, b_texts, b_gauges, b_portraits = self._bottom_row_commands(
                members, focus_member_id
            )
            panels.extend(b_panels)
            texts.extend(b_texts)
            gauges.extend(b_gauges)
            return panels, texts, gauges, icons, b_portraits
        if L.party_hud == "side_list":
            s_panels, s_texts, s_gauges, s_portraits = self._side_list_commands(
                members, focus_member_id
            )
            panels.extend(s_panels)
            texts.extend(s_texts)
            gauges.extend(s_gauges)
            return panels, texts, gauges, icons, s_portraits

        available_height = max(1.0, L.virtual_height - L.timeline_y - 42.0 - L.margin)
        layout = self.party_layout.resolve(
            [x.member_id for x in members],
            zone_by_member=zone_by_member,
            focus_member_id=focus_member_id,
            available_height=available_height,
        )
        member_by_id = {x.member_id: x for x in members}

        for zone_layout in layout.zones:
            density = zone_layout.density
            row_height = self.party_layout.row_height(density)
            right = zone_layout.zone == "right"
            center = zone_layout.zone == "center"
            stacked = 0.0
            shared = self._column_portrait_side(zone_layout, member_by_id, available_height)
            for member_id in zone_layout.visible_member_ids:
                member = member_by_id[member_id]
                if center:
                    x = (L.virtual_width - L.hud_panel_width) / 2
                elif right:
                    x = L.virtual_width - L.margin - L.hud_panel_width
                else:
                    x = L.margin

                # Stack upward from the lower battle HUD safe area; each row
                # advances by at least its own panel height so panels never overlap.
                base_y = L.virtual_height - L.margin - 8.0
                y = base_y - stacked

                selected = self._column_gauges(member, density)

                status_limit = self.party_layout.status_limit(density)
                selected_statuses = list(member.statuses)
                if status_limit is not None:
                    selected_statuses = selected_statuses[:status_limit]

                height = self._column_height(len(selected), density)
                # the member's portrait, one size down the column: beside the rows (they move
                # aside and narrow, never under BAR_MIN) or over them (the card grows taller)
                room = min(self._column_room(selected, density), shared)
                side, picture = self._card_portrait(member.member_id, height, room)
                cx, cw, lift, height = self._portrait_rows(side, x, L.hud_panel_width, height)

                panel_y = y - height
                stacked += max(row_height, height + 2.0)
                if side:
                    card = (x, panel_y, L.hud_panel_width, height)
                    portraits.append(self._portrait(member.member_id, picture, side, card, 4.0))
                focused = (
                    self.polish.focus_member_emphasis
                    and focus_member_id is not None
                    and member.member_id == str(focus_member_id)
                )
                panel_role = f"hud:{density}:focus" if focused else f"hud:{density}"
                name_role = f"member_name:{density}:focus" if focused else f"member_name:{density}"
                panels.append(
                    BattleUiPanel(
                        f"hud:{member.member_id}",
                        x,
                        panel_y,
                        L.hud_panel_width,
                        height,
                        panel_role,
                        member.member_id,
                    )
                )
                name = self._name(member.member_id)
                if side:  # the rows are narrower: the name keeps within them
                    name = self._fit(name, max(4, int((cw - 8) // 4.4)))
                texts.append(
                    BattleUiText(
                        name,
                        cx + 4,
                        panel_y + lift + 3,
                        name_role,
                        "left",
                        member.member_id,
                    )
                )

                gy = panel_y + lift + (13 if density != "minimal" else 9)
                for gauge in selected:
                    mode = str(gauge.presentation)
                    if density == "minimal":
                        # Minimal density shows only the highest-priority resource
                        # with no redundant label/value unless the project uses a
                        # number-style resource.
                        if mode in {"number", "contextual"}:
                            texts.append(
                                BattleUiText(
                                    f"{gauge.current:g}",
                                    cx + cw - 4,
                                    panel_y + lift + 3,
                                    f"resource_value:{mode}",
                                    "right",
                                    member.member_id,
                                )
                            )
                        else:
                            gauges.append(
                                BattleUiGaugeBar(
                                    member.member_id,
                                    gauge.resource_id,
                                    gauge.label,
                                    cx + 38,
                                    panel_y + lift + 6,
                                    max(8.0, cw - 44),
                                    4.0,
                                    max(0.0, min(1.0, float(gauge.normalized))),
                                    float(gauge.current),
                                    float(gauge.maximum),
                                    mode,
                                    int(gauge.segments),
                                    gauge.icon_asset_id,
                                    getattr(gauge, "color", ""),
                                )
                            )
                        continue

                    if gauge.show_label and density == "expanded":
                        texts.append(
                            BattleUiText(
                                self._fit(gauge.label, 5),
                                cx + 4,
                                gy,
                                "gauge_label",
                                "left",
                                member.member_id,
                            )
                        )

                    if mode in {"number", "contextual"}:
                        if gauge.show_value:
                            texts.append(
                                BattleUiText(
                                    f"{gauge.current:g}",
                                    cx + cw - 4,
                                    gy,
                                    f"resource_value:{mode}",
                                    "right",
                                    member.member_id,
                                )
                            )
                    else:
                        label_space = self._label_space(gauge, density)
                        value_space = self._value_space(gauge, density)
                        bar_x = cx + label_space
                        bar_w = max(8.0, cw - label_space - value_space)
                        gauges.append(
                            BattleUiGaugeBar(
                                member.member_id,
                                gauge.resource_id,
                                gauge.label,
                                bar_x,
                                gy,
                                bar_w,
                                5.0 if density == "expanded" else 4.0,
                                max(0.0, min(1.0, float(gauge.normalized))),
                                float(gauge.current),
                                float(gauge.maximum),
                                mode,
                                int(gauge.segments),
                                gauge.icon_asset_id,
                                getattr(gauge, "color", ""),
                            )
                        )
                        if gauge.show_value and not gauge.compact and density == "expanded":
                            texts.append(
                                BattleUiText(
                                    f"{gauge.current:g}/{gauge.maximum:g}",
                                    cx + cw - 4,
                                    gy,
                                    "gauge_value",
                                    "right",
                                    member.member_id,
                                )
                            )
                    gy += L.hud_row_height if density == "expanded" else 8.0

                if density != "minimal":
                    ix = cx + 4
                    iy = y - 8
                    for status in selected_statuses:
                        if status.icon_asset_id:
                            icons.append(
                                BattleUiIcon(
                                    status.icon_asset_id,
                                    ix,
                                    iy,
                                    "status",
                                    member.member_id,
                                    status.label,
                                )
                            )
                            ix += 10

            if zone_layout.overflow_count:
                if zone_layout.zone == "right":
                    ox = L.virtual_width - L.margin
                    align = "right"
                elif zone_layout.zone == "center":
                    ox = L.virtual_width / 2
                    align = "center"
                else:
                    ox = L.margin
                    align = "left"
                texts.append(
                    BattleUiText(
                        f"+{zone_layout.overflow_count}",
                        ox,
                        L.timeline_y + 31.0,
                        "hud_overflow",
                        align,
                        "",
                    )
                )
        return panels, texts, gauges, icons, portraits

    def _column_height(self, rows, density):
        """A column HUD card's height for ``rows`` resource rows at ``density``."""
        if density == "expanded":
            return max(24.0, 18.0 + rows * self.layout.hud_row_height)
        if density == "compact":
            return max(20.0, 14.0 + rows * 8.0)
        return 16.0

    @staticmethod
    def _label_space(gauge, density):
        """Room a column card keeps before a resource's bar (for its label when it shows one)."""
        return 30 if (gauge.show_label and density == "expanded") else 4

    @staticmethod
    def _value_space(gauge, density):
        """Room a column card keeps after a resource's bar (for its numbers when it shows
        them)."""
        return 26 if (gauge.show_value and not gauge.compact and density == "expanded") else 8

    def _column_gauges(self, member, density):
        """The resources a column card shows at ``density``: those of highest priority, in the
        member's own order."""
        limit = self.party_layout.resource_limit(density)
        ordered = sorted(
            member.gauges,
            key=lambda g: (-int(getattr(g, "priority", 0)), g.order, g.resource_id),
        )
        chosen = {g.resource_id for g in (ordered if limit is None else ordered[:limit])}
        return [g for g in member.gauges if g.resource_id in chosen]

    def _column_room(self, selected, density):
        """The most a portrait may take of a column card's width: beside the rows, what leaves
        their labels, numbers and a BAR_MIN bar; over them, the card's width inside."""
        if self.layout.hud_portraits == "above":
            return self.layout.hud_panel_width - 8.0
        widest = 44.0  # a minimal card: its one bar starts 38 in and ends 6 short
        if selected and density != "minimal":
            widest = max(
                self._label_space(g, density) + self._value_space(g, density) for g in selected
            )
        return self.layout.hud_panel_width - 2.0 - BAR_MIN - widest

    def _column_portrait_side(self, zone_layout, member_by_id, available):
        """The side the portraits of one HUD column share: the smallest any of its cards has
        room for - over the rows, out of the height the column has left in ``available``,
        shared. 0 when none shows one."""
        density = zone_layout.density
        ids = zone_layout.visible_member_ids
        owners = [m for m in ids if self._portraits.get(m)]
        if not owners or self.layout.hud_portraits == "off":
            return 0.0
        share = float("inf")
        if self.layout.hud_portraits == "above":
            row_height = self.party_layout.row_height(density)
            used = 0.0
            for member_id in ids:
                rows = len(self._column_gauges(member_by_id[member_id], density))
                used += max(row_height, self._column_height(rows, density) + 2.0)
            share = (available - used) / len(owners) - 2.0
        sides = []
        for member_id in owners:
            selected = self._column_gauges(member_by_id[member_id], density)
            height = self._column_height(len(selected), density)
            room = min(self._column_room(selected, density), share)
            sides.append(self._card_portrait(member_id, height, room)[0])
        return min((side for side in sides if side), default=0.0)

    @staticmethod
    def _ranked_gauges(member, limit):
        ordered = sorted(
            member.gauges, key=lambda g: (-int(getattr(g, "priority", 0)), g.order, g.resource_id)
        )
        return [
            g for g in ordered if str(g.presentation) not in {"number", "contextual", "hidden"}
        ][:limit]

    def _bar(self, member_id, gauge, x, y, width, height):
        return BattleUiGaugeBar(
            member_id,
            gauge.resource_id,
            gauge.label,
            x,
            y,
            width,
            height,
            max(0.0, min(1.0, float(gauge.normalized))),
            float(gauge.current),
            float(gauge.maximum),
            str(gauge.presentation),
            int(gauge.segments),
            gauge.icon_asset_id,
            getattr(gauge, "color", ""),
        )

    # room an overhead label keeps: a line of state names (drawn by the runtime) over the name
    OVERHEAD_CAPTION = 8.0
    OVERHEAD_CHAR = 4.4  # virtual width of one character of a name

    def _combatant_boxes(self):
        """``member_id: (x, y, w, h)`` of every combatant's figure on screen (virtual pixels),
        with the strip under the feet where shield and weakness tiles stand."""
        boxes = {}
        zoom = 1.0 if self._camera is None else float(self._camera.zoom)
        for visual in self.scene.combatants:
            pos = (
                None
                if self._camera is None
                else self._anchor_screen(self._camera, visual.member_id)
            )
            if pos is None:
                continue
            extent = self._member_extents.get(visual.member_id)
            if extent is not None:  # the figure's visible pixels, every frame of it, as drawn
                left, top, right, bottom = (v * zoom for v in extent)
                bottom = max(bottom, 0.0) + 9.0
                boxes[visual.member_id] = (pos[0] + left, pos[1] + top, right - left, bottom - top)
                continue
            body = float(self._member_heights.get(visual.member_id, 32.0)) * zoom
            half = max(8.0, body * 0.32)
            boxes[visual.member_id] = (pos[0] - half, pos[1] - body, 2 * half, body + 9.0)
        return boxes

    def _overhead_commands(self, members):
        """Name (and, with ``overhead_bars``, the top-priority bar) over each member's sprite.
        A label never covers a combatant (its own too), another label or the turn bar, and it
        stays by its owner: just over the head, a little higher or to the side, else just under
        the feet row, else beside the head. Where none of those is clear the name is not shown -
        never somewhere far from its owner. ``overhead_labels`` keeps where each shown one went."""
        panels, texts, gauges = [], [], []
        L = self.layout
        camera = self._camera
        boxes = self._combatant_boxes()
        placed = []
        self.overhead_labels = {}
        floor, margin = L.timeline_y + 24.0, L.margin  # a label stays under the turn bar

        for member in members:
            anchor = None if camera is None else self._anchor_screen(camera, member.member_id)
            if anchor is None:
                continue
            ax, ay = anchor
            own = boxes.get(member.member_id)
            top = (
                own[1]
                if own is not None
                else ay - float(self._member_heights.get(member.member_id, 32.0))
            )
            name = self._fit(self._name(member.member_id), 14)
            ranked = self._ranked_gauges(member, 1) if L.overhead_bars else ()
            states = cut(" ".join(str(st.label or st.state_id) for st in member.statuses), 30)
            width = max(
                44.0 if ranked else 0.0,
                cells(name) * self.OVERHEAD_CHAR + 4.0,
                cells(states) * 1.9,  # the state names over it (small type)
            )
            height = self.OVERHEAD_CAPTION + 9.0 + (5.0 if ranked else 0.0)
            home_x = ax - width / 2
            # (y, cost): over the head first, a little higher, else under the feet row (close to
            # its owner beats far above someone else's head)
            feet = own[1] + own[3] if own is not None else ay + 9.0
            below = [(feet + 1.0 + i * 3.0, 24.0 + i * 3.0) for i in range(4)]
            if L.overhead_below:
                ys = [(cy, cost - 24.0) for cy, cost in below]
            else:
                base = top - height - 1.0
                ys = [(base - i * 3.0, i * 3.0) for i in range(5)] + below
            shifts = [0.0]
            for step in (0.25, 0.5):  # a little to the side, still over its owner
                shifts += [-step * width, step * width]
            spots = [(cy, home_x + dx, cost + 1.2 * abs(dx)) for cy, cost in ys for dx in shifts]
            if own is not None:  # beside the head, touching the figure's side, last
                bx, by, bw, bh = own
                for i in range(4):
                    cy = by + i * 3.0
                    if cy + height > by + bh / 2:
                        break
                    spots += [(cy, bx - width - 2.0, 40.0 + i), (cy, bx + bw + 2.0, 41.0 + i)]
            tries = sorted(spots, key=lambda t: t[2])
            right = L.virtual_width - L.margin - width
            # the first (cheapest) spot that is on screen, by its owner, and covers no figure
            # (its own too) and no other label
            others = list(boxes.values()) + placed
            spot = None
            for cy, cx, _cost in tries:
                if cy < floor or cy + height > L.virtual_height:
                    continue
                cx = max(margin, min(right, cx))
                if own is not None and _gap((cx, cy, width, height), own) > 12.0:
                    continue  # pushed along by the screen edge, away from its owner
                if all(
                    cx + width <= bx or bx + bw <= cx or cy + height <= by or by + bh <= cy
                    for bx, by, bw, bh in others
                ):
                    spot = (cy, cx)
                    break
            if spot is None:
                continue  # no clear place by its owner: no name rather than one far away
            y, x = spot
            placed.append((x, y, width, height))
            name_y = y + self.OVERHEAD_CAPTION
            self.overhead_labels[member.member_id] = (x, y, width, height)
            cx = x + width / 2
            texts.append(
                BattleUiText(name, cx, name_y, "overhead_name", "center", member.member_id)
            )
            if ranked:
                gauges.append(
                    self._bar(member.member_id, ranked[0], cx - 22.0, name_y + 10.0, 44.0, 3.0)
                )
        return panels, texts, gauges

    @staticmethod
    def _chip(label):
        """A short status label: initials of a multi-word name, else the first three letters
        (the first two characters of a Chinese or Japanese name)."""
        words = str(label).replace(".", " ").replace("_", " ").split()
        if len(words) > 1:
            return cut("".join(w[0] for w in words[:3]).upper(), 4)
        word = words[0] if words else "?"
        return word[:3].upper() if word.isascii() else cut(word, 4)

    def _side_list_commands(self, members, focus_member_id):
        """One panel per member down the party's edge, under the turn bar: name and status chips
        on top, then a ``label  current / maximum`` line with a thin bar per resource (pips
        resources, like boost points, draw as dots). Panels shrink their row count, never
        overlap, and never leave the screen. A member's portrait stands at its panel's left or
        right end (the rows narrow) or over its rows (the panel grows into the room the list has
        left; the row count is what it would be without portraits)."""
        panels, texts, gauges, portraits = [], [], [], []
        L = self.layout
        if not members:
            return panels, texts, gauges, portraits
        width = float(L.hud_panel_width)
        x = L.virtual_width - L.margin - width
        top = L.timeline_y + 24.0
        available = L.virtual_height - L.margin - top
        gap, header, row, pad = 2.0, 9.0, 10.0, 3.0
        ranked = {m.member_id: self._ranked_gauges(m, 4) for m in members}

        def plan(rows, cap=None):
            """``(height, side, picture)`` of each member's panel with ``rows`` resource rows
            and a portrait of at most ``cap``."""
            out = []
            for member in members:
                shown = ranked[member.member_id][:rows]
                base = pad + header + row * len(shown)
                side, picture = 0.0, ""
                if self._portraits.get(member.member_id):  # rows measured only for a portrait
                    if L.hud_portraits == "above":
                        room = width - 6.0
                    else:
                        room = width - 2.0 - self._side_rows_need(shown)
                    side, picture = self._card_portrait(
                        member.member_id, base, room if cap is None else min(room, cap)
                    )
                out.append((self._portrait_rows(side, x, width, base)[3], side, picture))
            return out

        def total(cards):
            return sum(c[0] for c in cards) + gap * (len(members) - 1)

        rows = 4  # as many as fit without portraits: a portrait never takes another's rows
        while rows > 1 and total(plan(rows, 0.0)) > available:
            rows -= 1
        cap = None  # beside the rows a portrait never makes its panel taller
        if L.hud_portraits == "above":  # over them: the room the list has left, shared
            owners = sum(1 for m in members if self._portraits.get(m.member_id))
            cap = (available - total(plan(rows, 0.0))) / max(1, owners) - 2.0
        cards = plan(rows, cap)
        sides = [c[1] for c in cards if c[1]]
        if sides and min(sides) < max(sides):  # one size down the list: the smallest any has
            cards = plan(rows, min(sides))
        y = top
        for member, (height, side, picture) in zip(members, cards):
            shown = ranked[member.member_id][:rows]
            cx, cw, lift, _ = self._portrait_rows(side, x, width, pad + header + row * len(shown))
            focused = focus_member_id is not None and member.member_id == str(focus_member_id)
            panels.append(
                BattleUiPanel(
                    f"hud:{member.member_id}",
                    x,
                    y,
                    width,
                    height,
                    "hud:side:focus" if focused else "hud:side",
                    member.member_id,
                )
            )
            if side:
                card = (x, y, width, height)
                portraits.append(self._portrait(member.member_id, picture, side, card, 3.0))
            chips = " ".join(self._chip(s.label or s.state_id) for s in member.statuses[:4])
            name_room = max(6, int((cw - 8 - 4 * cells(chips)) // 4.4))
            texts.append(
                BattleUiText(
                    self._fit(self._name(member.member_id), name_room),
                    cx + 3,
                    y + lift + 2,
                    "member_name:side:focus" if focused else "member_name:side",
                    "left",
                    member.member_id,
                )
            )
            if chips:
                texts.append(
                    BattleUiText(
                        chips, cx + cw - 3, y + lift + 2, "status_chip", "right", member.member_id
                    )
                )
            gy = y + lift + pad + header
            for gauge in shown:
                label = self._fit(gauge.label, 3)
                texts.append(
                    BattleUiText(label, cx + 3, gy, "gauge_label", "left", member.member_id)
                )
                if str(gauge.presentation) in {"pips", "segmented_bar", "icon_stack"}:
                    gauges.append(
                        self._bar(member.member_id, gauge, cx + 22, gy + 1.5, cw - 28, 4.0)
                    )
                else:
                    value = f"{gauge.current:,.0f} / {gauge.maximum:,.0f}"
                    texts.append(
                        BattleUiText(
                            value, cx + cw - 3, gy, "side_value", "right", member.member_id
                        )
                    )
                    gauges.append(
                        self._bar(member.member_id, gauge, cx + 3, gy + row - 3.0, cw - 6, 1.6)
                    )
                gy += row
            y += height + gap
        return panels, texts, gauges, portraits

    def _side_rows_need(self, shown):
        """How wide a side-list panel's rows must stay beside a portrait: six letters of the
        name, and each resource line's label with its numbers at their maximum (so the portrait
        keeps its size while they change) or with its pips."""
        need = 6 + 6 * 4.4
        for gauge in shown:
            label = self._drawn_width(self._fit(gauge.label, 3), "gauge_label")
            if str(gauge.presentation) in {"pips", "segmented_bar", "icon_stack"}:
                need = max(need, 28 + BAR_MIN)
            else:
                value = f"{gauge.maximum:,.0f} / {gauge.maximum:,.0f}"
                need = max(need, 10 + label + self._drawn_width(value, "side_value"))
        return need

    def _bottom_row_commands(self, members, focus_member_id):
        """Compact party cells in one row along the bottom (name + up to two bars). A member's
        portrait stands at its cell's left or right end, or over its rows (the cell grows up,
        ``bottom_row_height``)."""
        panels, texts, gauges, portraits = [], [], [], []
        L = self.layout
        if not members:
            return panels, texts, gauges, portraits
        gap = 3.0
        count = len(members)
        width = min(120.0, (L.virtual_width - 2 * L.margin - gap * (count - 1)) / count)
        total = count * width + gap * (count - 1)
        x0 = L.virtual_width - L.margin - total  # anchored to the party's side (right)
        if L.hud_portraits == "above":  # as wide as the cell; the row stays in the lower half
            room = min(width - 6.0, L.virtual_height / 2 - BOTTOM_ROW_HEIGHT - 2.0)
        else:
            room = width - 8.0 - BAR_MIN
        for index, member in enumerate(members):
            x = x0 + index * (width + gap)
            side, picture = self._card_portrait(member.member_id, BOTTOM_ROW_HEIGHT, room)
            cx, cw, lift, height = self._portrait_rows(side, x, width, BOTTOM_ROW_HEIGHT)
            y = L.virtual_height - L.margin - height
            focused = focus_member_id is not None and member.member_id == str(focus_member_id)
            panels.append(
                BattleUiPanel(
                    f"hud:{member.member_id}",
                    x,
                    y,
                    width,
                    height,
                    "hud:compact:focus" if focused else "hud:compact",
                    member.member_id,
                )
            )
            if side:
                card = (x, y, width, height)
                portraits.append(self._portrait(member.member_id, picture, side, card, 3.0))
            texts.append(
                BattleUiText(
                    self._fit(self._name(member.member_id), int(cw // 5)),
                    cx + 3,
                    y + lift + 2,
                    "member_name:compact:focus" if focused else "member_name:compact",
                    "left",
                    member.member_id,
                )
            )
            for row, gauge in enumerate(self._ranked_gauges(member, 2)):
                gauges.append(
                    self._bar(
                        member.member_id, gauge, cx + 3, y + lift + 12 + row * 6, cw - 6, 3.0
                    )
                )
        return panels, texts, gauges, portraits

    def _clear_of_portraits(self, x, y, width, height, least):
        """``(x, y, width)`` for a ``width`` x ``height`` panel wanted at ``(x, y)`` (the command
        menu, its help box, the action workflow) that covers no party card's portrait: where it
        was when it covers none, else the nearest clear place - narrower on the portraits' side
        (down to ``least`` wide) rather than moved far. Where no place is clear it stays."""
        boxes = list(self.portrait_boxes.values())

        def clear(cx, cy, w):
            return all(
                cx + w <= bx - 1 or bx + bw + 1 <= cx or cy + height <= by - 1 or by + bh + 1 <= cy
                for bx, by, bw, bh in boxes
            )

        if clear(x, y, width):
            return x, y, width
        L = self.layout
        ys = {y}
        for _bx, by, _bw, bh in boxes:  # just above or just below a portrait
            ys.update((by - 1.0 - height, by + bh + 1.0))
        spots = []  # (cost, x, y, width)
        for cy in ys:
            if cy < L.timeline_y + 24.0 or cy + height > L.virtual_height - 2.0:
                continue
            fits = [(x, width)]
            for bx, _by, bw, _bh in boxes:
                fits += [
                    (x, bx - 1.0 - x),  # ends before the portrait
                    (bx + bw + 1.0, x + width - bx - bw - 1.0),  # starts after it
                    (bx - 1.0 - width, width),  # moved to its left
                    (bx + bw + 1.0, width),  # moved to its right
                ]
            for cx, w in fits:
                if least <= w <= width and cx >= 2.0 and cx + w <= L.virtual_width - 2.0:
                    if clear(cx, cy, w):
                        spots.append((2.0 * abs(cy - y) + abs(cx - x) + width - w, cx, cy, w))
        if not spots:
            return x, y, width
        _, cx, cy, w = min(spots)
        return cx, cy, w

    def _action_menu_commands(self, menu):
        """The command menu: laid out again only when the menu, the stage or a label it keeps
        clear of changed since the last frame, else the last frame's commands."""
        if menu is None:
            return [], [], []
        if not isinstance(menu, BattleActionMenuView):
            raise TypeError("action_menu must be BattleActionMenuView")
        camera = self._camera
        stage = None
        if camera is not None:
            stage = tuple(
                camera.world_to_screen(v.anchor.x, v.anchor.y) for v in self.scene.combatants
            )
        key = (
            tuple(getattr(menu, name) for name in _MENU_LAYOUT_FIELDS),
            self._focus,
            self._member_heights,
            self.overhead_labels,
            self.scene.combatants,
            stage,
            self.layout,
            self.polish,
            self._category_names,
            self._tr("battle.menu.filter", "Filter: {query}"),  # the language of its own words
            self.text_width,
            self.portrait_boxes,  # a new dict each frame: the kept key is never changed in place
        )
        cached = self._menu_cache
        if cached is not None and cached[0] == key:
            return tuple(list(x) for x in cached[1])
        out = self._action_menu_layout(menu)
        key = key[:3] + (dict(self.overhead_labels),) + key[4:]
        self._menu_cache = (key, tuple(tuple(x) for x in out))
        return out

    def _action_menu_layout(self, menu):
        panels, texts, icons = [], [], []
        if menu is None:
            return panels, texts, icons
        if not isinstance(menu, BattleActionMenuView):
            raise TypeError("action_menu must be BattleActionMenuView")
        L, P = self.layout, self.polish
        if not L.command_counts and any(e.action_id.startswith("root:") for e in menu.entries):
            from dataclasses import replace

            menu = replace(  # the top-level commands show their names alone
                menu,
                entries=tuple(
                    replace(e, cost_text="") if e.action_id.startswith("root:") else e
                    for e in menu.entries
                ),
            )
        width = min(P.interaction_width, L.virtual_width - 2 * L.margin)
        # as wide as the longest row (name + cost) needs, so costs never run into names:
        # measured as the backend draws them, else estimated
        gutter = _mark_gutter(P.selected_prefix, P.idle_prefix)
        if self.text_width is not None:
            units = max((self._row_units(e) + 2 + gutter for e in menu.entries), default=0)
        else:
            chars = max(
                (
                    cells(e.label) + 2 + (cells(e.cost_text) + 2 if e.cost_text else 0)
                    for e in menu.entries
                ),
                default=0,
            )
            units = chars * 3.8
        # rows with an icon (a skill's ``icon_id``) start 8 layout units further right
        icon_pad = 8.0 if any(e.icon_asset_id for e in menu.entries) else 0.0
        wanted = min(width, max(88.0, min(150.0, units + 2 * P.interaction_padding + icon_pad)))
        # Keep the menu between left/right HUD columns when there is room for it.
        hud_gap = L.virtual_width - 2 * (L.margin + L.hud_panel_width) - 2 * L.margin
        if hud_gap >= self.MIN_MENU_WIDTH:
            width = min(width, max(hud_gap, wanted))
        x = (L.virtual_width - width) / 2
        if L.party_hud == "side_list":
            # between the far side's combatants and the party's, left of the party's list
            width = min(width, wanted)
            left = L.margin
            right = L.virtual_width - L.margin - L.hud_panel_width - L.margin
            centre = L.virtual_width / 2
            for visual in self.scene.combatants:
                # a combatant also owns its overhead name/bar (>= 44 wide) and shield row
                half = max(float(self._member_heights.get(visual.member_id, 32.0)) / 2, 24.0) + 6.0
                pos = (
                    None
                    if self._camera is None
                    else self._anchor_screen(self._camera, visual.member_id)
                )
                px = visual.anchor.x if pos is None else pos[0]
                if px <= centre:
                    left = max(left, px + half)
                elif px < right:
                    right = min(right, px - half)
            if right - left >= self.MIN_MENU_WIDTH:
                width = min(width, right - left)
                x = (left + right - width) / 2
            else:  # no gap: the lower-left corner, under the far side
                x = L.margin
        header_rows = (1 if menu.categories else 0) + (1 if menu.query else 0)
        body_rows = max(1, len(menu.entries))
        height = (
            2 * P.interaction_padding
            + header_rows * P.interaction_header_height
            + body_rows * P.interaction_row_height
            + P.interaction_footer_height
        )
        y = max(
            L.timeline_y + 28.0,
            L.virtual_height - L.margin - P.interaction_bottom_gap - height,
        )
        if L.party_hud == "side_list" and self._camera is not None:
            # Kept clear: the acting member and every enemy (name and bar above, sprite, shield
            # row under the feet), whatever ``menu_over_stage`` says. Only the other party
            # members may sit behind the (see-through) menu.
            boxes = []
            boxed = []
            for visual in self.scene.combatants:
                pos = self._anchor_screen(self._camera, visual.member_id)
                if pos is None:
                    continue
                if self._stands_right(visual.member_id) and visual.member_id != self._focus:
                    continue
                body = float(self._member_heights.get(visual.member_id, 32.0))
                half = max(body / 2, 24.0)
                boxes.append((pos[0] - half, pos[1] - body - 22.0, 2 * half, body + 22.0 + 30.0))
                boxed.append(visual)
                label = self.overhead_labels.get(visual.member_id)
                if label is not None:  # a name that moved up to stay clear stays uncovered
                    boxes.append(label)
                    boxed.append(visual)

            def clear(cx, cy, w):
                return all(
                    cx + w <= bx - 2 or bx + bw <= cx - 2 or cy + height <= by or by + bh <= cy
                    for bx, by, bw, bh in boxes
                )

            hero_left = L.virtual_width - 2 * L.margin - L.hud_panel_width
            # first choice: beside the acting member, on the side facing the enemies
            lefts = [box[0] for box, v in zip(boxes, boxed) if self._stands_right(v.member_id)]
            actor_at = (
                None if self._focus is None else self._anchor_screen(self._camera, self._focus)
            )
            found = None
            if lefts and actor_at is not None:
                # fixed spot: right beside the acting member, narrower rather than moved
                top_y = L.timeline_y + 28.0
                low_y = L.virtual_height - 3.0 - height
                mid_y = min(low_y, max(top_y, actor_at[1] - height / 2 - 14.0))
                for w in dict.fromkeys((width, 120.0, 104.0, 92.0, 84.0)):
                    w = min(w, width)
                    cx = min(lefts) - 4.0 - w
                    for cy in dict.fromkeys((mid_y, low_y, top_y)):
                        if cx >= L.margin and clear(cx, cy, w):
                            found = (cx, cy, w)
                            break
                    if found:
                        break
            for w in dict.fromkeys((width, min(width, 120.0), min(width, 104.0))):
                if found:
                    break
                xs = []
                ys = [y, L.timeline_y + 28.0]
                if lefts and actor_at is not None:
                    xs.append(min(lefts) - 4.0 - w)
                    ys.insert(0, max(L.timeline_y + 28.0, actor_at[1] - height / 2 - 14.0))
                xs += [x, L.margin]
                xs += [bx + bw + 4.0 for bx, _, bw, _ in boxes]
                ys += [by + bh + 2.0 for _, by, _, bh in boxes]
                for cy in dict.fromkeys(ys):
                    if cy + height > L.virtual_height - 3.0 or cy < L.timeline_y + 24.0:
                        continue
                    for cx in dict.fromkeys(xs):
                        if L.margin <= cx and cx + w <= hero_left and clear(cx, cy, w):
                            found = (cx, cy, w)
                            break
                    if found:
                        break
                if found:
                    break
            if found:
                x, y, width = found
        anchor = None
        if (
            L.action_menu_placement == "actor"
            and L.party_hud != "side_list"
            and self._focus is not None
            and self._camera is not None
        ):
            anchor = self._anchor_screen(self._camera, self._focus)
        if anchor is not None:
            # Beside the acting member's group, on the side facing the stage
            # centre, so the menu never covers other party members; as wide as its longest row
            # (name + cost) needs, within 88..150 virtual pixels.
            width = min(width, wanted)
            ax, ay = anchor
            body = float(self._member_heights.get(self._focus, 32.0))
            right_side = ax > L.virtual_width / 2
            group = []
            for visual in self.scene.combatants:
                if (visual.anchor.x > L.virtual_width / 2) != right_side:
                    continue
                gx, _ = self._camera.world_to_screen(visual.anchor.x, visual.anchor.y)
                half = float(self._member_heights.get(visual.member_id, 32.0)) / 2
                group.append(gx - half if right_side else gx + half)
            edge = (
                (min(group) if right_side else max(group))
                if group
                else (ax - body / 2 if right_side else ax + body / 2)
            )
            # never across the stage centre: the other side's combatants stay visible
            centre = L.virtual_width / 2
            room = (edge - 6 - (centre + 2)) if right_side else ((centre - 2) - (edge + 6))
            if room >= self.MIN_MENU_WIDTH:
                width = min(width, room)
            x = edge - 6 - width if right_side else edge + 6
            x = max(L.margin, min(L.virtual_width - L.margin - width, x))
            limit = (
                L.virtual_height
                - L.margin
                - (28.0 if L.party_hud == "bottom_row" else 0.0)
                - height
            )
            y = max(L.timeline_y + 28.0, min(limit, ay - body / 2 - height / 2))
        if (
            L.action_menu_placement == "actor_bottom_right"
            and self._focus is not None
            and self._camera is not None
        ):
            spot = self._anchor_screen(self._camera, self._focus)
            if spot is not None:
                # always at the acting member's lower right, touching the figure, so it is
                # plain who acts; it may cover others (even a HUD panel when there is no room)
                body = float(self._member_heights.get(self._focus, 32.0))
                width = min(width, wanted)
                half = max(8.0, body * 0.32)
                x = spot[0] + half + 2.0
                room = L.virtual_width - 2.0 - x
                if room >= 80.0:  # narrower rather than over the one who acts
                    width = min(width, room)
                else:  # no room on the right at all: the lower left instead
                    x = spot[0] - half - 2.0 - width
                y = spot[1] - body * 0.5
                x = max(L.margin, min(L.virtual_width - 2.0 - width, x))
                y = max(L.timeline_y + 24.0, min(L.virtual_height - 2.0 - height, y))
        # it may cover a HUD panel, never a portrait on one
        x, y, width = self._clear_of_portraits(x, y, width, height, min(width, 80.0))
        role = "interaction:float" if L.party_hud == "side_list" else "interaction:action_menu"
        panels.append(BattleUiPanel("action_menu", x, y, width, height, role))

        ty = y + P.interaction_padding
        if menu.categories:
            category_text = _category_strip(
                menu.categories,
                menu.active_category,
                width - 2 * P.interaction_padding,
                self._category_names,
            )
            texts.append(
                BattleUiText(
                    category_text, x + P.interaction_padding, ty, "action_categories", "left"
                )
            )
            ty += P.interaction_header_height

        if menu.query:
            texts.append(
                BattleUiText(
                    self._tr("battle.menu.filter", "Filter: {query}", query=menu.query),
                    x + P.interaction_padding,
                    ty,
                    "action_filter",
                    "left",
                )
            )
            ty += P.interaction_header_height

        if not menu.entries:
            texts.append(
                BattleUiText(P.empty_label, x + width / 2, ty + 3, "action_empty", "center")
            )
        else:
            for index, entry in enumerate(menu.entries):
                selected = index == menu.cursor
                if L.row_buttons:
                    button = (
                        "button:selected"
                        if selected
                        else ("button" if entry.enabled else "button:disabled")
                    )
                    panels.append(
                        BattleUiPanel(
                            f"button:{index}",
                            x + P.interaction_padding - 3,
                            ty - 2,
                            width - 2 * (P.interaction_padding - 3),
                            P.interaction_row_height,
                            button,
                        )
                    )
                role = (
                    "action_selected"
                    if selected
                    else ("action_entry" if entry.enabled else "action_disabled")
                )
                prefix = P.selected_prefix if selected else P.idle_prefix
                gutter = _mark_gutter(P.selected_prefix, P.idle_prefix)
                label = entry.label
                if self.text_width is not None:  # measured: never into the cost
                    room = width - 2 * P.interaction_padding - 2 - icon_pad - gutter
                    if entry.cost_text:
                        room -= MENU_COST_GAP + self._drawn_width(entry.cost_text, "action_cost")
                    label = self._fit_width(label, room)
                elif icon_pad:  # the icon took room from the name: never run into the cost
                    cost_room = (cells(entry.cost_text) + 2) * 3.8 if entry.cost_text else 0.0
                    fit = int((width - 2 * P.interaction_padding - icon_pad - cost_room) / 3.8)
                    fit -= round(gutter / 3.8)
                    if cells(label) > fit:  # a crowded row keeps a letter and ".."
                        label = cut(label, max(1, fit - 2)).rstrip() + ".."
                left = x + P.interaction_padding + 2 + icon_pad
                texts.extend(_marked(prefix, label, left, gutter, ty, role))
                if entry.cost_text:
                    texts.append(
                        BattleUiText(
                            entry.cost_text,
                            x + width - P.interaction_padding,
                            ty,
                            "action_cost" if entry.enabled else "action_cost_disabled",
                            "right",
                        )
                    )
                if entry.icon_asset_id:
                    # inside the row's frame, clear of its border and level in the row (on the
                    # border, the selection frame ran through the icon)
                    icons.append(
                        BattleUiIcon(
                            entry.icon_asset_id,
                            x + P.interaction_padding - 1,
                            ty - 2 + (P.interaction_row_height - 8.0) / 2,
                            "action",
                            "",
                            entry.label,
                        )
                    )
                ty += P.interaction_row_height

            selected = menu.selected
            if selected is not None:
                footer = selected.detail
                footer_role = "action_detail"
                if not selected.enabled and selected.disabled_reason:
                    footer = selected.disabled_reason
                    footer_role = "action_disabled_reason"
                room = width - 2 * P.interaction_padding - (14.0 if menu.page_count > 1 else 0)
                fit = max(4, int(room // 4.4))
                skill_text = footer_role == "action_detail" and selected.category != "Command"
                if footer and cells(footer) > fit and skill_text:
                    # a skill's whole description: a help box over the menu, words wrapped
                    help_panels, help_texts = self._help_box(footer, x, y, width, role)
                    panels += help_panels
                    texts += help_texts
                    footer = ""
                if footer:
                    if cells(footer) > fit:  # never wider than the menu
                        footer = cut(footer, fit - 2).rstrip() + ".."
                    texts.append(
                        BattleUiText(
                            footer,
                            x + P.interaction_padding,
                            y + height - P.interaction_footer_height,
                            footer_role,
                            "left",
                        )
                    )

        if menu.page_count > 1:
            texts.append(
                BattleUiText(
                    f"{menu.page + 1}{P.page_separator}{menu.page_count}",
                    x + width - P.interaction_padding,
                    y + height - P.interaction_footer_height,
                    "action_page",
                    "right",
                )
            )
        return panels, texts, icons

    def _help_lines(self, text, width):
        """``text`` wrapped for a help box ``width`` wide (three lines at most), and the box's
        height."""
        P = self.polish
        per_line = max(8, int((width - 2 * P.interaction_padding) // 3.4))
        lines = wrap(text, per_line)  # at spaces, and between Chinese / Japanese characters
        if len(lines) > 3:
            lines = lines[:3]
            lines[2] = cut(lines[2], per_line - 2).rstrip() + ".."
        return lines, 2 * P.interaction_padding + len(lines) * P.interaction_header_height

    def _help_box(self, text, menu_x, menu_y, menu_width, role):
        """A panel over the action menu holding ``text`` word-wrapped (three lines at most),
        its right edge on the menu's."""
        L, P = self.layout, self.polish
        width = min(L.virtual_width - 2 * L.margin, max(menu_width * 1.7, menu_width + 60.0))
        lines, height = self._help_lines(text, width)
        x = max(L.margin, min(menu_x + menu_width - width, L.virtual_width - L.margin - width))
        y = max(L.margin, menu_y - height - 3.0)
        x, y, narrow = self._clear_of_portraits(x, y, width, height, min(width, menu_width))
        if narrow != width:  # narrower beside a portrait: the words wrap again
            width = narrow
            lines, height = self._help_lines(text, width)
            y = max(L.margin, menu_y - height - 3.0)
            x, y, _ = self._clear_of_portraits(x, y, width, height, width)
        panels = [BattleUiPanel("action_help", x, y, width, height, role)]
        texts = [
            BattleUiText(
                value,
                x + P.interaction_padding,
                y + P.interaction_padding + i * P.interaction_header_height,
                "action_detail",
                "left",
            )
            for i, value in enumerate(lines)
        ]
        return panels, texts

    def _workflow_commands(self, workflow):
        panels, texts, icons = [], [], []
        if workflow is None:
            return panels, texts, icons
        if not isinstance(workflow, BattleActionWorkflowView):
            raise TypeError("action_workflow must be BattleActionWorkflowView")
        L, P = self.layout, self.polish
        width = min(P.interaction_width + 10.0, L.virtual_width - 2 * L.margin)
        x = (L.virtual_width - width) / 2
        option_rows = max(1, len(workflow.options))
        height = (
            2 * P.interaction_padding
            + 2 * P.interaction_header_height
            + option_rows * P.interaction_row_height
            + P.interaction_footer_height
        )
        y = max(
            L.timeline_y + 28.0,
            L.virtual_height - L.margin - P.interaction_bottom_gap - height,
        )
        x, y, width = self._clear_of_portraits(x, y, width, height, min(width, 120.0))
        panels.append(
            BattleUiPanel("action_workflow", x, y, width, height, "interaction:workflow")
        )
        texts.append(
            BattleUiText(
                workflow.label,
                x + P.interaction_padding,
                y + P.interaction_padding,
                "workflow_title",
                "left",
            )
        )

        if workflow.complete:
            texts.append(
                BattleUiText(
                    self._tr("battle.workflow.ready", "Ready"),
                    x + width / 2,
                    y + P.interaction_padding + P.interaction_header_height + 4,
                    "workflow_complete",
                    "center",
                )
            )
            return panels, texts, icons

        step = workflow.step
        step_y = y + P.interaction_padding + P.interaction_header_height
        texts.append(
            BattleUiText(
                f"{workflow.step_index + 1}{P.page_separator}{workflow.step_count}  {step.label}",
                x + P.interaction_padding,
                step_y,
                "workflow_step",
                "left",
            )
        )
        selected = set()
        for value in workflow.selections:
            if value.step_id == step.step_id:
                selected.update(value.option_ids)

        oy = step_y + P.interaction_header_height
        gutter = _mark_gutter(P.selected_option_prefix, P.idle_prefix)
        for option in workflow.options:
            is_selected = option.option_id in selected
            mark = P.selected_option_prefix if is_selected else P.idle_prefix
            if is_selected:
                role = "workflow_option_selected"
            else:
                role = "workflow_option" if option.enabled else "workflow_option_disabled"
            left = x + P.interaction_padding + 3
            texts.extend(_marked(mark, option.label, left, gutter, oy, role))
            if option.icon_asset_id:
                icons.append(
                    BattleUiIcon(
                        option.icon_asset_id, x + 1, oy, "workflow_option", "", option.label
                    )
                )
            oy += P.interaction_row_height
        return panels, texts, icons

    def _stands_right(self, member_id):
        """True for a member standing on the right half of the stage (the party's side by the
        usual staging); the turn bar only uses it to tint the tiles."""
        try:
            visual = self.scene.visual_for(member_id)
        except KeyError:
            return True
        return visual.anchor.x > self.layout.virtual_width / 2

    def _timeline_commands(self, timeline):
        panels, texts = [], []
        if timeline is None:
            return panels, texts
        L = self.layout
        slot, padding = 32.0, 9.0
        capacity = max(1, int((L.virtual_width - 2 * L.margin - 2 * padding) // slot))
        turns = tuple(timeline.turns)[:capacity]
        width = 2 * padding + slot * len(turns)
        panels.append(
            BattleUiPanel(
                "timeline", (L.virtual_width - width) / 2, L.timeline_y, width, 24.0, "timeline"
            )
        )
        x = (L.virtual_width - width) / 2 + padding + slot / 2
        max_chars = max(3, int(slot // self.TIMELINE_CHAR_WIDTH))
        for entry in turns:
            # a tile per turn, tinted by the side of the field the member stands on
            ally = self._stands_right(entry.member_id)
            kind = "current" if entry.is_current else ("ally" if ally else "enemy")
            panels.append(
                BattleUiPanel(
                    f"turn:{entry.member_id}",
                    x - slot / 2 + 1.0,
                    L.timeline_y + 1.0,
                    slot - 2.0,
                    22.0,
                    f"timeline_tile:{kind}",
                    entry.member_id,
                )
            )
            role = "timeline_current" if entry.is_current else "timeline_entry"
            texts.append(
                BattleUiText(
                    self._fit(self._name(entry.member_id), max_chars),
                    x,
                    L.timeline_y + 7,
                    role,
                    "center",
                    entry.member_id,
                )
            )
            if timeline.scheduler_mode == "continuous":
                texts.append(
                    BattleUiText(
                        f"{entry.ready_time:.1f}",
                        x,
                        L.timeline_y + 16,
                        "timeline_time",
                        "center",
                        entry.member_id,
                    )
                )
            x += slot
        for i, cast in enumerate(timeline.casts):
            texts.append(
                BattleUiText(
                    f"{cast.actor_id}: {cast.ability_id} {int(round(cast.progress * 100))}%",
                    L.margin,
                    L.timeline_y + 26 + i * 9,
                    "cast",
                    "left",
                    cast.actor_id,
                )
            )
        return panels, texts

    def _feedback_commands(self, camera, feedback):
        texts = []
        if feedback is None:
            return texts
        for value in feedback.values:
            pos = self._anchor_screen(camera, value.target_id)
            if pos is None:
                continue
            x, y = pos
            lift = 10.0 + 12.0 * min(1.0, value.age / max(value.duration, 1e-9))
            sign = "+" if value.kind == BattleValueKind.HEAL and value.value >= 0 else ""
            texts.append(
                BattleUiText(
                    f"{sign}{_value_text(value.value)}",
                    x,
                    y - lift,
                    f"value:{value.kind.value}",
                    "center",
                    value.target_id,
                )
            )
        per_target = {}
        for label in feedback.labels:
            pos = self._anchor_screen(camera, label.target_id)
            if pos is None:
                continue
            offset = per_target.get(label.target_id, 0)
            per_target[label.target_id] = offset + 1
            texts.append(
                BattleUiText(
                    label.label,
                    pos[0],
                    pos[1] - 24.0 - offset * 8.0,
                    "feedback_label",
                    "center",
                    label.target_id,
                )
            )
        return texts

    def _result_commands(self, result):
        panels, texts = [], []
        if result is None or not result.finished:
            return panels, texts
        L = self.layout
        x = (L.virtual_width - L.result_panel_width) / 2
        y = (L.virtual_height - L.result_panel_height) / 2
        panels.append(
            BattleUiPanel(
                "battle_result", x, y, L.result_panel_width, L.result_panel_height, "result"
            )
        )
        texts.append(
            BattleUiText(result.headline, L.virtual_width / 2, y + 12, "result_headline", "center")
        )
        line_y = y + 28
        for reward in result.currencies:
            texts.append(
                BattleUiText(
                    f"{reward.label}  +{reward.amount:g}", x + 12, line_y, "reward", "left"
                )
            )
            line_y += 9
        for reward in result.items:
            texts.append(
                BattleUiText(f"{reward.label}  x{reward.amount}", x + 12, line_y, "reward", "left")
            )
            line_y += 9
        for reward in result.progression:
            rank = "battle.result.rank", "Rank {old} → {new}"
            suffix = (
                "  " + self._tr(*rank, old=reward.old_rank, new=reward.new_rank)
                if reward.new_rank != reward.old_rank
                else ""
            )
            texts.append(
                BattleUiText(
                    f"{reward.label}  +{reward.new_total - reward.old_total:g}{suffix}",
                    x + 12,
                    line_y,
                    "progression",
                    "left",
                )
            )
            line_y += 9
        return panels, texts

    def compose(
        self,
        camera: Camera2D,
        battle_frame: BattlePresentationFrame,
        *,
        hud_members=(),
        timeline: BattleTurnTimelineView | None = None,
        feedback: BattleFeedbackRuntime | None = None,
        camera_feedback: BattleCameraFeedbackFrame | None = None,
        result: BattleResultView | None = None,
        action_menu: BattleActionMenuView | None = None,
        action_workflow: BattleActionWorkflowView | None = None,
        side_by_member=None,
        placement_by_member=None,
        focus_member_id=None,
        display_names=None,
        member_heights=None,
        member_extents=None,
        overhead_hidden=False,
        category_names=None,
        translate=None,
        portraits=None,
    ):
        """``display_names`` maps member ids to the labels shown in HUD and timeline;
        ``member_heights`` (logical sprite heights) positions overhead bars and the
        actor-anchored action menu; ``category_names`` maps menu categories (ids) to the names
        drawn; ``translate(key, english, **params)`` words the screen's own text; ``portraits``
        maps member ids to the ``(portrait, small portrait)`` asset ids their party cards show
        (``hud_portraits``; the menus keep clear of them)."""
        self._portraits = {
            str(k): (str(v[0] or ""), str(v[1] or "")) for k, v in dict(portraits or {}).items()
        }
        self._display_names = {str(k): str(v) for k, v in dict(display_names or {}).items()}
        self._category_names = {str(k): str(v) for k, v in dict(category_names or {}).items()}
        self._translate = translate
        self._member_heights = {str(k): float(v) for k, v in dict(member_heights or {}).items()}
        self._member_extents = {
            str(k): tuple(float(x) for x in v) for k, v in dict(member_extents or {}).items()
        }
        self._overhead_hidden = bool(overhead_hidden)
        self._camera = camera
        self._focus = None if focus_member_id is None else str(focus_member_id)
        if not isinstance(camera, Camera2D):
            raise TypeError("camera must be Camera2D")
        if not isinstance(battle_frame, BattlePresentationFrame):
            raise TypeError("battle_frame must be BattlePresentationFrame")
        if battle_frame.scene_id != self.scene.scene_id:
            raise ValueError("battle frame scene mismatch")
        hud_members = tuple(hud_members)
        if any(not isinstance(x, BattleHudMember) for x in hud_members):
            raise TypeError("hud_members must contain BattleHudMember")
        side_by_member = dict(side_by_member or {})

        panels, texts, gauges, icons, portraits = self._hud_commands(
            hud_members, side_by_member, placement_by_member, focus_member_id
        )
        self.portrait_boxes = {p.member_id: (p.x, p.y, p.width, p.height) for p in portraits}
        pw, tw, iw = self._workflow_commands(action_workflow)
        panels.extend(pw)
        texts.extend(tw)
        icons.extend(iw)
        if action_workflow is None:
            pa, ta, ia = self._action_menu_commands(action_menu)
            panels.extend(pa)
            texts.extend(ta)
            icons.extend(ia)
        p2, t2 = self._timeline_commands(timeline)
        panels.extend(p2)
        texts.extend(t2)
        texts.extend(self._feedback_commands(camera, feedback))
        p3, t3 = self._result_commands(result)
        panels.extend(p3)
        texts.extend(t3)

        markers = ()
        screen_fx = ()
        if camera_feedback is not None:
            markers = tuple(
                BattleUiMarker(x.member_id, x.screen_x, x.screen_y, x.primary)
                for x in camera_feedback.targets
            )
            screen_fx = tuple(camera_feedback.screen_fx)

        if feedback is None:
            vfx = ()
        else:
            vfx = tuple(
                sorted(
                    feedback.vfx,
                    key=lambda item: (
                        int(dict(item.payload.get("staging", {}) or {}).get("layer", 0)),
                        -int(dict(item.payload.get("staging", {}) or {}).get("priority", 0)),
                        item.sequence,
                    ),
                )
            )
        return BattleUiFrame(
            self.scene.scene_id,
            battle_frame.background_asset_id,
            tuple(battle_frame.combatant_draws),
            tuple(panels),
            tuple(texts),
            tuple(gauges),
            tuple(icons),
            markers,
            vfx,
            screen_fx,
            tuple(portraits),
        )
