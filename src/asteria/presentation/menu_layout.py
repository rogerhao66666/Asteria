"""Menu screens as data (U2): a layout per screen and one menu theme per project.

Every menu screen the engine draws (the shop, the status pages, the bag, the quest log...) is
made of **named elements**: its frame, its title, its list, its detail box, its key hints. The
screen's code knows what each element shows; a ``MenuLayout`` for that screen says where each
one goes and how it looks:

- ``rect`` moves and sizes it (``None`` keeps the engine's place), measured from ``anchor``:
  ``topleft`` counts from the screen's top-left corner, ``bottomright`` from its bottom-right
  corner (x and y then usually negative), ``center`` from the middle..., so one layout fits
  any window size.
- ``visible`` hides it, ``layer`` orders the author's own elements around the screen's.
- the style - a nine-patch ``skin`` or a picture, ``fill`` / ``border`` colours, ``font``,
  ``size``, ``color``, ``align`` - replaces the engine's look for that element only.

A layout can also hold **elements of the author's own** (ids starting ``extra.``): a picture,
a panel, a fixed text (a translation key or plain words, ``{field}`` filled from the screen's
fields), a gauge bound to a field, a portrait. Each screen lists the fields it offers
(``SCREENS``), so a layout only names what the screen has.

A screen with no layout draws exactly as before: every lookup falls back to the engine's own
place and style. ``MenuTheme`` is project-wide: fonts (one for Latin letters, one for Chinese,
Japanese and Korean, the bundled Noto Sans TC filling missing glyphs), the text colours, the
selection and cursor pictures, rarity colours and the menu sounds.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .ui_skin import NinePatch

ANCHORS = (
    "topleft",
    "top",
    "topright",
    "left",
    "center",
    "right",
    "bottomleft",
    "bottom",
    "bottomright",
)
KINDS = (
    "panel",  # a frame: nine-patch, picture or colours
    "image",  # any picture: stretch, fit, centre or tile
    "text",  # fixed words or a field
    "list",  # rows of a data source (icon, name, columns, selection)
    "grid",  # cells of a data source (bag)
    "doll",  # equipment slots placed on a picture (paper doll)
    "detail",  # the selected thing: icon, name, description, stats, comparison
    "gauge",  # a bar bound to a value and its maximum
    "tabs",  # pages of a screen (buy / sell, refine / socket / cards)
    "portrait",  # a character's or shopkeeper's picture
    "hint",  # the key hints line
)
IMAGE_MODES = ("stretch", "fit", "center", "tile")
FRAME_AXES = ("x", "y")  # an animation strip's frames run left to right, or top to bottom
ALIGNS = ("", "left", "center", "right")
EXTRA = "extra."  # the author's own elements
DESIGN_SIZE = (1280, 720)


def _color(value, name):
    if value is None or value == "" or value == []:
        return None
    if isinstance(value, str):
        text = value.strip().lstrip("#")
        if len(text) not in (6, 8):
            raise ValueError(f"{name} must be #rrggbb or #rrggbbaa")
        value = tuple(int(text[i : i + 2], 16) for i in range(0, len(text), 2))
    value = tuple(int(v) for v in value)
    if len(value) not in (3, 4) or any(v < 0 or v > 255 for v in value):
        raise ValueError(f"{name} must be 3 or 4 numbers 0-255")
    return value


def _rect(value, name="rect"):
    if value is None or value == [] or value == ():
        return None
    value = tuple(int(round(float(v))) for v in value)
    if len(value) != 4:
        raise ValueError(f"{name} must be (x, y, width, height)")
    if value[2] < 0 or value[3] < 0:
        raise ValueError(f"{name} width and height must be >= 0")
    return value


def _patch(value):
    if value is None or value == {} or value == "":
        return None
    return value if isinstance(value, NinePatch) else NinePatch.from_data(value)


def resolve_rect(rect, anchor, size):
    """``rect`` (measured from ``anchor``) in screen pixels for a screen of ``size``."""
    x, y, w, h = rect
    width, height = size
    horizontal = {"left": 0, "center": 0.5, "right": 1}
    vertical = {"top": 0, "center": 0.5, "bottom": 1}
    anchor = str(anchor or "topleft")
    if anchor == "center":
        fx, fy = 0.5, 0.5
    else:
        fy = next((vertical[k] for k in ("top", "bottom") if anchor.startswith(k)), 0.5)
        fx = next((horizontal[k] for k in ("left", "right") if anchor.endswith(k)), 0.5)
    return (int(round(x + width * fx)), int(round(y + height * fy)), w, h)


def anchored_rect(rect, anchor, size):
    """The inverse of ``resolve_rect``: screen pixels -> measured from ``anchor``."""
    zero = resolve_rect((0, 0, 0, 0), anchor, size)
    return (rect[0] - zero[0], rect[1] - zero[1], rect[2], rect[3])


@dataclass(frozen=True, slots=True)
class MenuSlotPlace:
    """Where a doll element puts one equipment slot, and the picture of the empty place.

    How the worn piece's icon fills the place (D88): ``icon_scale`` of the place (1 = as big as
    fits inside it), ``icon_rotate`` degrees counter-clockwise first (-45 lays a diagonal sword
    flat in a long place), ``icon_trim`` cuts the icon's empty edges so its picture, not its
    margin, fills the place, ``icon_fit`` "fit" keeps its shape, "stretch" fills the place."""

    slot_id: str
    rect: tuple
    placeholder: str = ""
    icon_scale: float = 1.0
    icon_rotate: int = 0
    icon_trim: bool = False
    icon_fit: str = "fit"

    FITS = ("fit", "stretch")

    def __post_init__(self):
        if not str(self.slot_id).strip():
            raise ValueError("a doll slot needs a slot_id")
        object.__setattr__(self, "slot_id", str(self.slot_id).strip())
        object.__setattr__(self, "rect", _rect(self.rect, "slot rect"))
        object.__setattr__(self, "placeholder", str(self.placeholder or "").strip())
        scale = float(self.icon_scale)
        if not 0.1 <= scale <= 4.0:
            raise ValueError("a slot's icon_scale must be between 0.1 and 4")
        object.__setattr__(self, "icon_scale", scale)
        object.__setattr__(self, "icon_rotate", int(self.icon_rotate) % 360)
        object.__setattr__(self, "icon_trim", bool(self.icon_trim))
        fit = str(self.icon_fit or "fit").strip()
        if fit not in self.FITS:
            raise ValueError(f"a slot's icon_fit must be one of {self.FITS}")
        object.__setattr__(self, "icon_fit", fit)

    def to_data(self):
        data = {"slot_id": self.slot_id, "rect": list(self.rect)}
        if self.placeholder:
            data["placeholder"] = self.placeholder
        if self.icon_scale != 1.0:
            data["icon_scale"] = self.icon_scale
        if self.icon_rotate:
            data["icon_rotate"] = self.icon_rotate
        if self.icon_trim:
            data["icon_trim"] = True
        if self.icon_fit != "fit":
            data["icon_fit"] = self.icon_fit
        return data

    @classmethod
    def from_data(cls, data):
        return cls(
            data["slot_id"],
            data["rect"],
            data.get("placeholder", ""),
            data.get("icon_scale", 1.0),
            data.get("icon_rotate", 0),
            data.get("icon_trim", False),
            data.get("icon_fit", "fit"),
        )


@dataclass(frozen=True, slots=True)
class MenuElement:
    """One element of a screen: one of the screen's own (by its name) or the author's own
    (``extra.<name>``). Every style field left empty keeps the engine's look."""

    element_id: str
    kind: str = "panel"
    rect: tuple | None = None
    anchor: str = "topleft"
    layer: int = 0  # the author's elements: below 0 under the screen, 0 and up over it
    visible: bool = True
    skin: NinePatch | None = None
    image: str = ""
    image_mode: str = "stretch"
    fill: tuple | None = None
    border: tuple | None = None
    font: str = ""
    size: int = 0
    color: tuple | None = None
    align: str = ""
    text: str = ""  # fixed words, a translation key (``key:...``), ``{field}`` filled in
    binding: str = ""  # the screen field a text, gauge or portrait shows
    row_height: int = 0
    icon_size: int = 0
    selection_skin: NinePatch | None = None
    selection_fill: tuple | None = None
    columns: int = 0
    cell: int = 0
    gap: int = -1
    slots: tuple = ()  # MenuSlotPlace for a doll
    frames: int = 0  # the picture is a strip of this many frames (0 / 1: a still picture)
    frame_axis: str = "x"  # the strip runs left to right ("x") or top to bottom ("y")
    fps: float = 0.0  # frames a second (0: the screen picks the frame, e.g. a cooldown)
    bitmap_font: str = ""  # a bitmap font (``MenuBitmapFont``) for the element's words

    def __post_init__(self):
        element_id = str(self.element_id).strip()
        if not element_id:
            raise ValueError("a menu element needs an element_id")
        object.__setattr__(self, "element_id", element_id)
        if self.kind not in KINDS:
            raise ValueError(f"kind must be one of {KINDS}")
        object.__setattr__(self, "rect", _rect(self.rect))
        if self.anchor not in ANCHORS:
            raise ValueError(f"anchor must be one of {ANCHORS}")
        if self.image_mode not in IMAGE_MODES:
            raise ValueError(f"image_mode must be one of {IMAGE_MODES}")
        if self.align not in ALIGNS:
            raise ValueError(f"align must be one of {ALIGNS[1:]}")
        object.__setattr__(self, "layer", int(self.layer))
        object.__setattr__(self, "visible", bool(self.visible))
        object.__setattr__(self, "skin", _patch(self.skin))
        object.__setattr__(self, "selection_skin", _patch(self.selection_skin))
        for name in ("fill", "border", "color", "selection_fill"):
            object.__setattr__(self, name, _color(getattr(self, name), name))
        for name in ("image", "font", "text", "binding"):
            object.__setattr__(self, name, str(getattr(self, name) or ""))
        for name in ("size", "row_height", "icon_size", "columns", "cell"):
            value = int(getattr(self, name) or 0)
            if value < 0:
                raise ValueError(f"{name} must be >= 0")
            object.__setattr__(self, name, value)
        object.__setattr__(self, "gap", int(self.gap))
        slots = tuple(
            s if isinstance(s, MenuSlotPlace) else MenuSlotPlace.from_data(s) for s in self.slots
        )
        object.__setattr__(self, "slots", slots)
        if self.frame_axis not in FRAME_AXES:
            raise ValueError(f"frame_axis must be one of {FRAME_AXES}")
        if int(self.frames or 0) < 0 or float(self.fps or 0) < 0:
            raise ValueError("frames and fps must be >= 0")
        object.__setattr__(self, "frames", int(self.frames or 0))
        object.__setattr__(self, "fps", float(self.fps or 0))
        object.__setattr__(self, "bitmap_font", str(self.bitmap_font or "").strip())

    @property
    def extra(self):
        return self.element_id.startswith(EXTRA)

    def to_data(self):
        """Only what differs from an empty element (a short, readable project file)."""
        data = {"element_id": self.element_id, "kind": self.kind}
        defaults = _DEFAULTS
        for name in _FIELDS:
            value = getattr(self, name)
            if value == getattr(defaults, name):
                continue
            if isinstance(value, NinePatch):
                value = value.to_data()
            elif name == "slots":
                value = [s.to_data() for s in value]
            elif isinstance(value, tuple):
                value = list(value)
            data[name] = value
        return data

    @classmethod
    def from_data(cls, data):
        unknown = set(data) - set(_FIELDS) - {"element_id", "kind"}
        if unknown:
            raise ValueError("unknown menu element fields: " + ", ".join(sorted(unknown)))
        return cls(**dict(data))


_FIELDS = tuple(
    name for name in MenuElement.__dataclass_fields__ if name not in ("element_id", "kind")
)
_DEFAULTS = MenuElement("_")


@dataclass(frozen=True, slots=True)
class MenuLayout:
    """The look of one screen (``screen_id`` from ``SCREENS``): its background and elements."""

    screen_id: str
    elements: tuple = ()
    background_color: tuple | None = None
    background_image: str = ""
    background_mode: str = "stretch"
    dim: int = -1  # how dark the map behind is drawn (0-255); -1 keeps the engine's
    music: str = ""  # a track played while the screen is open ("" keeps what plays)

    def __post_init__(self):
        if not str(self.screen_id).strip():
            raise ValueError("a menu layout needs a screen_id")
        object.__setattr__(self, "screen_id", str(self.screen_id).strip())
        elements = tuple(
            e if isinstance(e, MenuElement) else MenuElement.from_data(e) for e in self.elements
        )
        ids = [e.element_id for e in elements]
        if len(ids) != len(set(ids)):
            raise ValueError(f"duplicate menu elements in {self.screen_id}")
        object.__setattr__(self, "elements", elements)
        object.__setattr__(self, "background_color", _color(self.background_color, "background"))
        object.__setattr__(self, "background_image", str(self.background_image or ""))
        if self.background_mode not in IMAGE_MODES:
            raise ValueError(f"background_mode must be one of {IMAGE_MODES}")
        dim = int(self.dim)
        if dim < -1 or dim > 255:
            raise ValueError("dim must be -1 (engine's) or 0-255")
        object.__setattr__(self, "dim", dim)
        object.__setattr__(self, "music", str(self.music or ""))

    def element(self, element_id):
        return next((e for e in self.elements if e.element_id == element_id), None)

    def with_element(self, element):
        """A copy with ``element`` added or replacing the one of the same id."""
        kept = [e for e in self.elements if e.element_id != element.element_id]
        kept.append(element)
        return MenuLayout(
            self.screen_id,
            tuple(kept),
            self.background_color,
            self.background_image,
            self.background_mode,
            self.dim,
            self.music,
        )

    def without_element(self, element_id):
        kept = tuple(e for e in self.elements if e.element_id != element_id)
        return MenuLayout(
            self.screen_id,
            kept,
            self.background_color,
            self.background_image,
            self.background_mode,
            self.dim,
            self.music,
        )

    def to_data(self):
        data = {"screen_id": self.screen_id, "elements": [e.to_data() for e in self.elements]}
        if self.background_color is not None:
            data["background_color"] = list(self.background_color)
        if self.background_image:
            data["background_image"] = self.background_image
        if self.background_mode != "stretch":
            data["background_mode"] = self.background_mode
        if self.dim != -1:
            data["dim"] = self.dim
        if self.music:
            data["music"] = self.music
        return data

    @classmethod
    def from_data(cls, data):
        return cls(
            data["screen_id"],
            tuple(MenuElement.from_data(e) for e in data.get("elements", ())),
            data.get("background_color"),
            data.get("background_image", ""),
            data.get("background_mode", "stretch"),
            data.get("dim", -1),
            data.get("music", ""),
        )


SOUND_ROLES = ("move", "confirm", "cancel", "buy", "fail", "open")


@dataclass(frozen=True, slots=True)
class MenuTheme:
    """Project-wide look of every menu screen; every field left empty keeps the engine's."""

    font_latin: str = ""  # a .ttf / .otf asset for Latin letters and digits
    font_cjk: str = ""  # one for Chinese, Japanese and Korean ("" = the bundled Noto Sans TC)
    font_scale: float = 1.0  # pixel fonts are often drawn smaller or larger than the size
    text_color: tuple | None = None
    muted_color: tuple | None = None
    title_color: tuple | None = None
    selected_color: tuple | None = None
    panel_skin: NinePatch | None = None  # every menu frame (else the battle theme's)
    selection_skin: NinePatch | None = None  # the selected row's frame
    selection_fill: tuple | None = None
    cursor_image: str = ""
    rarity_colors: tuple = ()  # ((rarity_id, colour), ...) over the rarities' own colours
    sounds: tuple = ()  # ((role, sound asset), ...) roles in SOUND_ROLES
    bitmap_font: str = ""  # a bitmap font for every menu's words (what it lacks: the fonts)
    resource_colors: tuple = ()  # ((resource, colour), ...): orbs and bars of that resource

    def __post_init__(self):
        for name in ("font_latin", "font_cjk", "cursor_image", "bitmap_font"):
            object.__setattr__(self, name, str(getattr(self, name) or "").strip())
        if not float(self.font_scale) > 0:
            raise ValueError("font_scale must be > 0")
        object.__setattr__(self, "font_scale", float(self.font_scale))
        for name in ("text_color", "muted_color", "title_color", "selected_color"):
            object.__setattr__(self, name, _color(getattr(self, name), name))
        object.__setattr__(self, "selection_fill", _color(self.selection_fill, "selection"))
        object.__setattr__(self, "panel_skin", _patch(self.panel_skin))
        object.__setattr__(self, "selection_skin", _patch(self.selection_skin))
        rarity = self.rarity_colors
        rarity = rarity.items() if isinstance(rarity, dict) else rarity
        object.__setattr__(
            self,
            "rarity_colors",
            tuple((str(k), _color(v, "rarity colour")) for k, v in rarity),
        )
        colours = self.resource_colors
        colours = colours.items() if isinstance(colours, dict) else colours
        object.__setattr__(
            self,
            "resource_colors",
            tuple((str(k), _color(v, "resource colour")) for k, v in colours),
        )
        sounds = self.sounds.items() if isinstance(self.sounds, dict) else self.sounds
        sounds = tuple((str(k), str(v)) for k, v in sounds if str(v).strip())
        for role, _asset in sounds:
            if role not in SOUND_ROLES:
                raise ValueError(f"sound role must be one of {SOUND_ROLES}")
        object.__setattr__(self, "sounds", sounds)

    def sound(self, role):
        return dict(self.sounds).get(role, "")

    def rarity_color(self, rarity_id):
        return dict(self.rarity_colors).get(str(rarity_id))

    def resource_color(self, resource):
        return dict(self.resource_colors).get(str(resource))

    def to_data(self):
        data = {}
        empty = MenuTheme()
        for name in MenuTheme.__dataclass_fields__:
            value = getattr(self, name)
            if value == getattr(empty, name):
                continue
            if isinstance(value, NinePatch):
                value = value.to_data()
            elif name in ("rarity_colors", "sounds", "resource_colors"):
                value = {k: (list(v) if isinstance(v, tuple) else v) for k, v in value}
            elif isinstance(value, tuple):
                value = list(value)
            data[name] = value
        return data

    @classmethod
    def from_data(cls, data):
        unknown = set(data) - set(cls.__dataclass_fields__)
        if unknown:
            raise ValueError("unknown menu theme fields: " + ", ".join(sorted(unknown)))
        return cls(**dict(data))


FONT_COLOURS = ("tint", "keep", "two_tone")
EMPTY_CELL = "⬚"  # in a bitmap font's rows: a cell with no character


@dataclass(frozen=True, slots=True)
class MenuBitmapFont:
    """A font drawn by hand: one picture cut into cells of ``cell_width`` x ``cell_height``,
    ``rows`` saying which character each cell holds (one string per row of cells, left to
    right; ``EMPTY_CELL`` skips a cell). How far the pen moves after a glyph is measured from
    its drawn pixels (plus ``spacing``) unless ``fixed_width``; ``widths`` overrides single
    characters. ``colours``: ``tint`` draws every visible pixel in the text colour (white
    glyphs), ``keep`` draws the picture's own colours, ``two_tone`` makes white the text colour
    and mid grey the shadow colour (the creature screens' fonts). Characters the font lacks are
    drawn in the menu fonts, so Chinese still shows."""

    font_id: str
    image: str = ""
    cell_width: int = 8
    cell_height: int = 8
    rows: tuple = ()
    spacing: int = 1
    space_width: int = 0  # 0: half a cell
    line: int = 0  # the line's height (0: a cell's height)
    fixed_width: bool = False
    widths: tuple = ()  # ((character, width), ...)
    colours: str = "tint"
    scale: int = 0  # whole-pixel scale (0: as near the asked text size as a whole number)

    def __post_init__(self):
        font_id = str(self.font_id).strip()
        if not font_id:
            raise ValueError("a bitmap font needs a font_id")
        object.__setattr__(self, "font_id", font_id)
        object.__setattr__(self, "image", str(self.image or "").strip())
        for name in ("cell_width", "cell_height"):
            value = int(getattr(self, name))
            if value < 1:
                raise ValueError(f"{name} must be >= 1")
            object.__setattr__(self, name, value)
        for name in ("space_width", "line", "scale"):
            value = int(getattr(self, name) or 0)
            if value < 0:
                raise ValueError(f"{name} must be >= 0")
            object.__setattr__(self, name, value)
        object.__setattr__(self, "spacing", int(self.spacing))
        rows = (self.rows,) if isinstance(self.rows, str) else self.rows
        object.__setattr__(self, "rows", tuple(str(r) for r in rows))
        object.__setattr__(self, "fixed_width", bool(self.fixed_width))
        widths = self.widths.items() if isinstance(self.widths, dict) else self.widths
        object.__setattr__(self, "widths", tuple((str(k), int(v)) for k, v in widths if str(k)))
        if self.colours not in FONT_COLOURS:
            raise ValueError(f"colours must be one of {FONT_COLOURS}")

    def cells(self):
        """``{character: (column, row)}``: where each character's cell is."""
        out = {}
        for row, chars in enumerate(self.rows):
            for column, char in enumerate(chars):
                if char != EMPTY_CELL and char not in out:
                    out[char] = (column, row)
        return out

    def to_data(self):
        data = {"font_id": self.font_id}
        empty = MenuBitmapFont("_")
        for name in MenuBitmapFont.__dataclass_fields__:
            value = getattr(self, name)
            if name == "font_id" or value == getattr(empty, name):
                continue
            if name == "widths":
                value = {k: v for k, v in value}
            elif isinstance(value, tuple):
                value = list(value)
            data[name] = value
        return data

    @classmethod
    def from_data(cls, data):
        unknown = set(data) - set(cls.__dataclass_fields__)
        if unknown:
            raise ValueError("unknown bitmap font fields: " + ", ".join(sorted(unknown)))
        return cls(**dict(data))


@dataclass(frozen=True, slots=True)
class ScreenSpec:
    """What one screen offers a layout: its own elements ``(id, kind, description)`` and the
    fields the author's texts, gauges and portraits can show."""

    screen_id: str
    title: str
    elements: tuple = ()
    fields: tuple = ()
    sample: str = ""  # how the editor opens it with sample data (``menu_preview``)
    notes: tuple = field(default=())
    size: tuple | None = None  # its own resolution (a 240x160 screen); None: the window's
    group: str = "menu"  # "menu" or "game" (drawn during play: HUD, dialogue, battle)


def _spec(screen_id, title, elements, fields=(), sample="", size=None, group="menu"):
    return ScreenSpec(
        screen_id, title, tuple(elements), tuple(fields), sample or screen_id, (), size, group
    )


_HINT = ("hint", "hint", "Key hints")
_FRAME = ("frame", "panel", "The screen's frame")
_TITLE = ("title", "text", "The screen's title")
_MESSAGE = ("message", "text", "The last message (bought, used, failed...)")
_EMPTY = ("empty", "text", "The words shown when the list is empty")
SCREENS = (
    _spec(
        "title",
        "Title",
        [
            ("name", "text", "The game's name"),
            ("subtitle", "text", "The line under the name"),
            ("options", "list", "New game / load / guest options"),
            ("status", "text", "Saves found"),
        ],
        ("game.title",),
    ),
    _spec(
        "pause",
        "Pause menu",
        [_FRAME, _TITLE, ("options", "list", "The menu's entries")],
        ("party.leader", "wallet.gold", "map.name"),
    ),
    _spec(
        "settings",
        "Settings",
        [_FRAME, _TITLE, ("options", "list", "The settings and their values"), _HINT],
    ),
    _spec(
        "controls", "Controls", [_FRAME, _TITLE, ("options", "list", "Actions and keys"), _HINT]
    ),
    _spec(
        "save_slots",
        "Save / load",
        [_FRAME, _TITLE, ("slots", "list", "The save slots"), _HINT],
    ),
    _spec(
        "game_over",
        "Game over",
        [_TITLE, ("options", "list", "Load / back to title")],
    ),
    _spec(
        "status",
        "Status pages",
        [
            _FRAME,
            ("tabs", "tabs", "Status / items / equipment / skills"),
            ("member", "text", "The member shown (Q / E)"),
            ("rows", "list", "The page's rows"),
            _EMPTY,
            _HINT,
            _MESSAGE,
        ],
        ("member.name", "member.level", "member.class", "wallet.gold"),
    ),
    _spec(
        "bag",
        "Equipment bag",
        [
            _TITLE,
            ("help", "text", "The keys line under the title"),
            ("worn_label", "text", "The worn strip's label"),
            ("worn", "grid", "The worn pieces"),
            ("bag_label", "text", "The bag's label and count"),
            ("grid", "grid", "The bag's cells"),
            ("detail", "detail", "The selected piece: name, rarity, stats, comparison"),
            _MESSAGE,
        ],
        ("member.name", "bag.count"),
    ),
    _spec(
        "equipment",
        "Equipment (paper doll)",
        [
            _FRAME,
            _TITLE,
            ("member", "text", "The member shown"),
            ("doll", "doll", "The slots on the doll picture"),
            ("candidates", "list", "What can go in the chosen slot"),
            ("detail", "detail", "The chosen piece and the change if worn"),
            ("stats", "list", "The member's stats"),
            _HINT,
            _MESSAGE,
        ],
        ("member.name", "member.level", "member.class", "wallet.gold"),
    ),
    _spec(
        "enhance",
        "Enhance (refine, sockets, cards, growth)",
        [
            _FRAME,
            _TITLE,
            ("member", "text", "The member shown (Q / E)"),
            ("tabs", "tabs", "Refine / sockets / cards / growth"),
            ("gear", "list", "The member's equipment"),
            (
                "sockets",
                "list",
                "The chosen piece's sockets (refine: its levels; growth: its stages)",
            ),
            ("choices", "list", "Gems, orbs or cards that fit"),
            ("detail", "detail", "Cost, chance, materials and the change"),
            _HINT,
            _MESSAGE,
        ],
        ("member.name", "member.level", "member.class", "wallet.gold", "page"),
    ),
    _spec(
        "skill_tree",
        "Skill tree",
        [
            _TITLE,
            ("header", "text", "Tree, classes and level"),
            ("points", "text", "Points to spend"),
            ("trees", "text", "Which tree of how many"),
            ("detail", "detail", "The chosen node"),
            _HINT,
            ("node_locked", "image", "A node that cannot be learned yet (its frame)"),
            ("node_available", "image", "A node that can be learned now"),
            ("node_learned", "image", "A node learned (not at its last rank)"),
            ("node_maxed", "image", "A node at its last rank"),
            ("node_selected", "image", "The frame over the chosen node"),
            ("link_met", "panel", "A line to a met prerequisite (colour; size: width)"),
            ("link_unmet", "panel", "A line to a prerequisite not met yet"),
            ("points_icon", "image", "A picture before the points to spend"),
        ],
        ("member.name",),
    ),
    _spec(
        "shop",
        "Shop",
        [
            _FRAME,
            _TITLE,
            ("tabs", "tabs", "Buy / sell"),
            ("wallet", "text", "The money held"),
            ("columns", "text", "The column titles"),
            ("rows", "list", "The goods"),
            ("count", "text", "Row n of all"),
            _HINT,
            _MESSAGE,
        ],
        ("shop.name", "wallet.gold"),
    ),
    _spec(
        "crafting",
        "Crafting (a workstation)",
        [
            _FRAME,
            _TITLE,
            ("wallet", "text", "The money held"),
            ("tabs", "tabs", "The station's categories (and disassembly)"),
            ("rows", "list", "The recipes, each with its product's icon"),
            ("detail", "detail", "Product, materials held / needed, chance, quality, how many"),
            ("quantity", "text", "How many to make"),
            ("undiscovered", "text", "How many recipes are not discovered yet"),
            ("flash", "image", "The station's picture shown after a success"),
            _EMPTY,
            _HINT,
            _MESSAGE,
        ],
        ("station.name", "page", "quantity", "wallet.gold"),
    ),
    _spec(
        "quest_board",
        "Quest board",
        [
            _FRAME,
            _TITLE,
            ("count", "text", "How many of the board's quests are taken"),
            ("description", "text", "The board's description"),
            ("cards", "grid", "The quest cards (columns, cell, row height, gap)"),
            ("detail", "detail", "The chosen card turned over: objectives, reward, time"),
            _EMPTY,
            _HINT,
            _MESSAGE,
        ],
        ("board.name", "board.active", "board.limit", "wallet.gold"),
    ),
    _spec(
        "recruit",
        "Recruiting office",
        [
            _FRAME,
            _TITLE,
            ("wallet", "text", "The money held"),
            ("party", "text", "The party's size"),
            ("rows", "list", "The candidates: portrait, class, level, price"),
            ("detail", "detail", "The chosen candidate: portrait, price, stats, note"),
            ("ask", "text", "Hire for the price? (Enter once more)"),
            _EMPTY,
            _HINT,
            _MESSAGE,
        ],
        ("office.name", "party.count", "party.limit", "wallet.gold"),
    ),
    _spec(
        "gacha",
        "Gacha banner",
        [
            _FRAME,
            _TITLE,
            ("wallet", "text", "The banner's currency held"),
            ("banner", "panel", "The banner's picture, description and rate-up prizes"),
            ("pity", "text", "Pulls left to the guaranteed rarity"),
            ("rates", "list", "The rates of every rarity (always shown)"),
            ("buttons", "list", "Pull x1 / pull many / all rates / history"),
            ("table", "panel", "The full rates table and the history"),
            ("chest", "image", "The chest that appears, shakes and opens"),
            ("results", "grid", "The prizes of the pull"),
            _HINT,
            _MESSAGE,
        ],
        ("banner.name", "pity.count", "pity.limit", "wallet", "page"),
    ),
    _spec(
        "quests",
        "Quest log",
        [_FRAME, _TITLE, ("rows", "list", "Quests and objectives"), _EMPTY, _HINT],
    ),
    _spec(
        "pets",
        "Pets",
        [_TITLE, ("help", "text", "The keys line"), ("rows", "list", "The pets")],
    ),
    _spec(
        "achievements",
        "Achievements",
        [_FRAME, _TITLE, ("rows", "list", "The achievements"), _HINT],
    ),
    _spec("bestiary", "Bestiary", [_FRAME, _TITLE, ("rows", "list", "The foes"), _HINT]),
    _spec("backlog", "Message log", [_TITLE, ("help", "text", "Keys"), ("rows", "list", "Lines")]),
    _spec("music", "Music room", [_TITLE, ("help", "text", "Keys"), ("rows", "list", "Tracks")]),
    _spec(
        "credits",
        "Credits",
        [_TITLE, ("lines", "list", "The page's lines"), _HINT],
    ),
    _spec(
        "ability_slots",
        "Skill slots",
        [_TITLE, ("help", "text", "Keys"), ("member", "text", "Member"), ("rows", "list", "")],
    ),
    _spec(
        "equip_offer",
        "Wear new gear?",
        [
            ("frame", "panel", "The question's box"),
            _TITLE,
            ("question", "text", "Wear it?"),
            ("keys", "text", "The answer keys"),
        ],
    ),
    _spec(
        "field_hint",
        "Map hints line",
        [("title", "text", "The map's title"), ("controls", "text", "The controls line")],
        ("map.name",),
        sample="field",
    ),
)
# drawn during play (V2-V5): the same layouts, listed under "During play" in the editor
SCREENS += (
    _spec(
        "dialogue",
        "Dialogue window",
        [
            ("window", "panel", "The message window"),
            ("speaker", "text", "Who speaks"),
            ("name_box", "panel", "A box behind the speaker's name (drawn when it has a look)"),
            ("portrait", "portrait", "Where the face or bust goes"),
            ("text", "text", "The line: text area, size, colour, line height, letters a second"),
            ("continue", "hint", "The continue words"),
            ("arrow", "image", "A 'next' arrow once the line is written out (a strip)"),
        ],
        ("speaker", "text"),
        group="game",
    ),
    _spec(
        "dialogue_choice",
        "Dialogue choice",
        [
            ("box", "panel", "The window behind the prompt and options"),
            ("prompt", "text", "The question"),
            ("choices", "list", "The options: columns, cell width, row height, chosen frame"),
        ],
        ("prompt",),
        group="game",
    ),
    _spec(
        "hud_action",
        "Action RPG HUD",
        [
            ("orb_life", "gauge", "The life orb: its frame picture; fill / text colour: liquid"),
            ("orb_life_fill", "image", "The life orb's liquid picture (shown up to its level)"),
            ("orb_life_empty", "image", "The empty life orb's picture"),
            ("orb_life_title", "text", "The life orb's name"),
            ("orb_life_value", "text", "The life orb's numbers"),
            ("orb_second", "gauge", "The second resource's orb"),
            ("orb_second_fill", "image", "Its liquid picture"),
            ("orb_second_empty", "image", "Its empty picture"),
            ("orb_second_title", "text", "Its name"),
            ("orb_second_value", "text", "Its numbers"),
            ("life_bar", "gauge", "Life as a bar instead (place it; hide the orb)"),
            ("second_bar", "gauge", "The second resource as a bar"),
            ("plate", "panel", "The action bar's plate (the slots go with it)"),
            ("slot_main", "image", "A large slot (attack, dodge): frame picture, cell size"),
            ("slot", "image", "A skill slot: frame picture, cell size, gap"),
            ("keycap", "image", "The key on a slot: picture or colours, text colour"),
            ("cooldown", "image", "The cooldown: a strip whose frame follows the time"),
            ("badge", "panel", "A count badge (items left, stacks)"),
            ("cost", "panel", "A skill's cost"),
            ("exp", "gauge", "The experience strip"),
            ("level", "text", "The level on it"),
            ("statuses", "grid", "The player's statuses: place, cell size, gap"),
            ("status_buff", "image", "A boon's frame"),
            ("status_debuff", "image", "A harm's frame"),
            ("resource_bars", "list", "The other resources' bars: first bar, row height"),
            ("hint", "hint", "The controls line at the top"),
            ("target", "panel", "The locked-on enemy's frame"),
            ("banner", "text", "The big words in the middle (level up...)"),
            ("fell", "panel", "The screen's tint when the player falls"),
            ("fell_text", "text", "The fell words"),
        ],
        group="game",
    ),
    _spec(
        "battle",
        "Battle screen",
        [
            ("party_hud", "panel", "The party's cards: move / size (0: as laid out), skin"),
            ("overhead", "text", "The names and bars over the fighters (moved as one)"),
            ("menu", "list", "The command menu and its skill / item pages; selection skin"),
            ("help", "panel", "The help box over the menu"),
            ("workflow", "panel", "The target and step lists of a chosen command"),
            ("timeline", "panel", "The turn order bar"),
            ("numbers", "text", "Damage and healing numbers: colour, size, or hidden"),
            ("result", "panel", "The victory / defeat panel"),
            ("target", "image", "The target cursor: colour, or hidden"),
            # one card on its own, after its group (party order; over-the-head bars likewise)
            *(
                (f"party_hud.{n}", "panel", f"Party card {n} on its own: move, size, skin")
                for n in range(1, 7)
            ),
            *(
                (f"overhead.{n}", "text", f"Name and bars over fighter {n} on their own")
                for n in range(1, 7)
            ),
        ],
        group="game",
    ),
)
SCREEN_IDS = tuple(s.screen_id for s in SCREENS)


def base_screen(screen_id):
    """The screen a layout id draws: ``crafting.forge`` (one workstation's own layout, U4)
    draws the ``crafting`` screen."""
    return str(screen_id).split(".", 1)[0]


def screen_spec(screen_id):
    base = base_screen(screen_id)
    return next((s for s in SCREENS if s.screen_id == base), None)


def screen_size(screen_id, window):
    """The size a screen's layout is measured in: its own resolution, else ``window``."""
    spec = screen_spec(screen_id)
    return tuple(spec.size) if spec is not None and spec.size else tuple(window)
