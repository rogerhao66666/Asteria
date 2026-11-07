"""ui"""

from __future__ import annotations

from dataclasses import dataclass

from asteria.core.values import finite
from asteria.presentation.battle.action_menu import BattleActionMenuView
from asteria.presentation.battle.action_workflow import BattleActionWorkflowView
from asteria.presentation.battle.camera_feedback import BattleCameraFeedbackFrame
from asteria.presentation.battle.feedback import BattleFeedbackRuntime
from asteria.presentation.battle.hud import BattleHudMember
from asteria.presentation.battle.party_layout import BattlePartyLayoutPolicy
from asteria.presentation.battle.result import BattleResultView
from asteria.presentation.battle.runtime import BattlePresentationFrame
from asteria.presentation.battle.scene import BattlePresentationScene
from asteria.presentation.battle.turn_timeline import BattleTurnTimelineView
from asteria.presentation.battle.ui_feedback import FeedbackCompositionMixin
from asteria.presentation.battle.ui_hud import HudCompositionMixin
from asteria.presentation.battle.ui_menu import ActionMenuCompositionMixin
from asteria.presentation.battle.ui_parts import (
    BOTTOM_ROW_HEIGHT,
    MENU_COST_GAP,
    BattleUiGaugeBar,
    BattleUiIcon,
    BattleUiPanel,
    BattleUiText,
)
from asteria.presentation.battle.ui_polish import BattleUiPolishProfile
from asteria.presentation.text.cells import cells, cut
from asteria.runtime import Camera2D

# where a party card shows its member's portrait (``BattleUiLayoutProfile.hud_portraits``)
HUD_PORTRAITS = ("left", "right", "above", "off")


PORTRAIT_MIN = 10.0  # layout units: a card with less room than this for a portrait shows none


PORTRAIT_LARGE = 32.0  # a portrait this large or larger shows the large picture, else the small


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
    # "label  current / maximum" line with a bar per resource - the classic party-RPG look);
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
            if finite(self.column_spacing_right, "column_spacing_right") < 0:
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
            if finite(getattr(self, name), name) < 0:
                raise ValueError(f"{name} must be >= 0")


@dataclass(frozen=True, slots=True)
class BattleUiMarker:
    member_id: str
    x: float
    y: float
    primary: bool = False
    color: tuple | None = None  # a battle layout's (V4) colour; None: the backend's


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


class BattleUiComposer(HudCompositionMixin, ActionMenuCompositionMixin, FeedbackCompositionMixin):
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
        self.screen_layout = None  # the author's ``battle`` MenuLayout (V4); None: as composed
        self.layout_boxes = {}  # group -> (x, y, w, h) after that layout, last frame
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

    # room an overhead label keeps: a line of state names (drawn by the runtime) over the name
    OVERHEAD_CAPTION = 8.0
    OVERHEAD_CHAR = 4.4  # virtual width of one character of a name

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
        marks = [(len(panels), len(texts), len(icons))]  # where each group's commands end
        pw, tw, iw = self._workflow_commands(action_workflow)
        panels.extend(pw)
        texts.extend(tw)
        icons.extend(iw)
        marks.append((len(panels), len(texts), len(icons)))
        if action_workflow is None:
            pa, ta, ia = self._action_menu_commands(action_menu)
            panels.extend(pa)
            texts.extend(ta)
            icons.extend(ia)
        marks.append((len(panels), len(texts), len(icons)))
        p2, t2 = self._timeline_commands(timeline)
        panels.extend(p2)
        texts.extend(t2)
        marks.append((len(panels), len(texts), len(icons)))
        texts.extend(self._feedback_commands(camera, feedback))
        marks.append((len(panels), len(texts), len(icons)))
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
        self.layout_boxes = {}
        if self.screen_layout is not None:  # the author's battle layout (V4): groups moved
            panels, texts, gauges, icons, portraits, markers = self._laid_out(
                marks, panels, texts, gauges, icons, portraits, markers
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

    def _laid_out(self, marks, panels, texts, gauges, icons, portraits, markers):
        """The frame's commands after the ``battle`` layout (``battle_layout``): each tagged
        with its group by where compose() put it, then moved, restyled or hidden."""
        from asteria.presentation.battle.layout import BattleScreenLayout

        names = ("party_hud", "workflow", "menu", "timeline", "numbers", "result")

        def tag(count, slot):
            groups = []
            for end, group in zip([m[slot] for m in marks] + [count], names, strict=True):
                groups += [group] * (end - len(groups))
            return groups

        overhead = set(self.overhead_labels)
        text_tags = tag(len(texts), 1)
        boxed_help = any(p.panel_id == "action_help" for p in panels)  # else: the menu's footer
        for i, text in enumerate(texts):
            if text_tags[i] == "party_hud" and text.role == "overhead_name":
                text_tags[i] = "overhead"
            elif boxed_help and text_tags[i] == "menu" and text.role == "action_detail":
                text_tags[i] = "help"
        panel_tags = tag(len(panels), 0)
        for i, panel in enumerate(panels):
            if panel.panel_id == "action_help":
                panel_tags[i] = "help"
        gauge_tags = []
        for gauge in gauges:  # the overhead bars come first, the party's after
            lead = not gauge_tags or gauge_tags[-1] == "overhead"
            gauge_tags.append("overhead" if lead and gauge.member_id in overhead else "party_hud")
        lists = {
            "panel": list(panels),
            "text": list(texts),
            "gauge": list(gauges),
            "icon": list(icons),
            "portrait": list(portraits),
            "marker": list(markers),
        }
        tags = {
            "panel": panel_tags,
            "text": text_tags,
            "gauge": gauge_tags,
            "icon": tag(len(icons), 2),
            "portrait": ["party_hud"] * len(portraits),
            "marker": ["target"] * len(markers),
        }
        size = (self.layout.virtual_width, self.layout.virtual_height)
        screen = BattleScreenLayout(self.screen_layout, size, self._tr)
        applied = screen.apply(lists, tags)
        self.layout_boxes = screen.boxes
        return (
            applied["panel"],
            applied["text"],
            applied["gauge"],
            applied["icon"],
            applied["portrait"],
            tuple(applied["marker"]),
        )
