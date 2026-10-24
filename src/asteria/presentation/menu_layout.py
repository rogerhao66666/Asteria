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
    """Where a doll element puts one equipment slot, and the picture of the empty place."""

    slot_id: str
    rect: tuple
    placeholder: str = ""

    def __post_init__(self):
        if not str(self.slot_id).strip():
            raise ValueError("a doll slot needs a slot_id")
        object.__setattr__(self, "slot_id", str(self.slot_id).strip())
        object.__setattr__(self, "rect", _rect(self.rect, "slot rect"))
        object.__setattr__(self, "placeholder", str(self.placeholder or "").strip())

    def to_data(self):
        data = {"slot_id": self.slot_id, "rect": list(self.rect)}
        if self.placeholder:
            data["placeholder"] = self.placeholder
        return data

    @classmethod
    def from_data(cls, data):
        return cls(data["slot_id"], data["rect"], data.get("placeholder", ""))


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

    def __post_init__(self):
        for name in ("font_latin", "font_cjk", "cursor_image"):
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

    def to_data(self):
        data = {}
        empty = MenuTheme()
        for name in MenuTheme.__dataclass_fields__:
            value = getattr(self, name)
            if value == getattr(empty, name):
                continue
            if isinstance(value, NinePatch):
                value = value.to_data()
            elif name in ("rarity_colors", "sounds"):
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


def _spec(screen_id, title, elements, fields=(), sample=""):
    return ScreenSpec(screen_id, title, tuple(elements), tuple(fields), sample or screen_id)


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
SCREEN_IDS = tuple(s.screen_id for s in SCREENS)


def base_screen(screen_id):
    """The screen a layout id draws: ``crafting.forge`` (one workstation's own layout, U4)
    draws the ``crafting`` screen."""
    return str(screen_id).split(".", 1)[0]


def screen_spec(screen_id):
    base = base_screen(screen_id)
    return next((s for s in SCREENS if s.screen_id == base), None)
