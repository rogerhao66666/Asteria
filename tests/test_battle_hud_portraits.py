"""Party portraits in the battle HUD (D53): each member's card shows the portrait set on its
Combatant Sprites record - beside its name and bars or over them, small on a small card - and
neither the card's own rows nor the command menu ever cover it. Cards without one are laid out
exactly as before, and the two layout options are written only when set."""

import itertools
import json
from dataclasses import replace
from pathlib import Path

import pytest

from asteria.presentation import (
    BattleActionEntry,
    BattleCombatantVisual,
    BattleHudGauge,
    BattleHudMember,
    BattlePresentationFrame,
    BattlePresentationScene,
    BattleUiComposer,
    BattleUiLayoutProfile,
    BattleUiPortrait,
    BattleVisualAnchor,
)
from asteria.presentation.battle_action_menu import BattleActionMenuView
from asteria.presentation.battle_hud import BattleHudStatusIcon
from asteria.presentation.battle_ui import PORTRAIT_LARGE, bottom_row_height
from asteria.presentation.library import BattlePresentationLibrary
from asteria.presentation.text_cells import cells
from asteria.runtime import Camera2D

REPO = Path(__file__).resolve().parents[1]
PARTY_RPG = REPO / "reference_projects" / "party_rpg_demo"
HEROES = ("hero", "ally", "mage")
PLACEMENT = {"hero": "right", "ally": "right", "mage": "right", "boss": "left", "imp": "left"}
PORTRAITS = {m: (f"faces/{m}.png", f"faces/{m}_small.png") for m in HEROES}
MODES = ("column", "bottom_row", "side_list")
PLACES = ("left", "right", "above")


# --- a battle to lay out ----------------------------------------------------------------------


def _gauge(resource_id, label, current, maximum, order, presentation="bar"):
    return BattleHudGauge(
        resource_id, label, current, 0, maximum, 0, current / maximum, False, None, order,
        presentation,
    )  # fmt: skip


def _members():
    poison = BattleHudStatusIcon("poison", "Poison", "icons/poison.png", 1, 3.0, None, 0)
    out = []
    for member_id in (*HEROES, "boss", "imp"):
        gauges = (_gauge("hp", "HP", 950, 1200, 0), _gauge("mp", "MP", 40, 60, 1))
        if member_id in HEROES:
            gauges += (_gauge("bp", "BP", 2, 5, 2, "pips"),)
        out.append(BattleHudMember(member_id, gauges, (poison,) if member_id == "hero" else ()))
    return tuple(out)


def _scene(width=320, height=180):
    def visual(member_id, x, y):
        return BattleCombatantVisual(
            member_id, f"{member_id}.sheet", f"{member_id}.clips", BattleVisualAnchor(x, y)
        )

    w, h = width / 320, height / 180
    return BattlePresentationScene(
        "battle.portraits",
        "bg",
        (
            visual("hero", 200 * w, 120 * h),
            visual("ally", 214 * w, 140 * h),
            visual("mage", 228 * w, 100 * h),
            visual("boss", 90 * w, 110 * h),
            visual("imp", 60 * w, 140 * h),
        ),
    )


def _menu(detail=""):
    entries = tuple(
        BattleActionEntry(f"root:{name}", name.title(), detail=detail)
        for name in ("attack", "skills", "items", "guard", "escape")
    )
    return BattleActionMenuView((), "", "", entries, 0, 1, len(entries), 1, 1)


def _compose(layout, composer=None, **kw):
    composer = composer or BattleUiComposer(
        _scene(layout.virtual_width, layout.virtual_height), layout
    )
    args = dict(
        hud_members=_members(),
        placement_by_member=PLACEMENT,
        focus_member_id="hero",
        member_heights={m: 32.0 for m in PLACEMENT},
    )
    args.update(kw)
    camera = Camera2D(width=layout.virtual_width, height=layout.virtual_height)
    frame = BattlePresentationFrame(composer.scene.scene_id, "bg", ())
    return composer, composer.compose(camera, frame, **args)


def _layout(mode, place="left", **kw):
    return BattleUiLayoutProfile(party_hud=mode, hud_portraits=place, **kw)


# --- boxes -------------------------------------------------------------------------------------


def _hit(a, b):
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def _inside(a, b):
    return (
        b[0] <= a[0] and b[1] <= a[1] and a[0] + a[2] <= b[0] + b[2] and a[1] + a[3] <= b[1] + b[3]
    )


def _text_box(text):
    """A line as the composer counts it (3.8 layout units a cell), 8 tall."""
    width = cells(text.text) * 3.8
    shift = {"right": width, "center": width / 2}.get(text.align, 0.0)
    return (text.x - shift, text.y, width, 8.0)


def _boxes(frame, member_id):
    """Every text, bar and status icon of ``member_id``'s card."""
    out = [_text_box(t) for t in frame.texts if t.member_id == member_id]
    out += [(g.x, g.y, g.width, g.height) for g in frame.gauges if g.member_id == member_id]
    out += [(i.x, i.y, 8.0, 8.0) for i in frame.icons if i.member_id == member_id]
    return out


def _panel(frame, member_id):
    p = next(p for p in frame.panels if p.panel_id == f"hud:{member_id}")
    return (p.x, p.y, p.width, p.height)


def _without(frame, member_ids):
    """The frame's commands that belong to no member of ``member_ids``."""

    def keep(items):
        return tuple(x for x in items if getattr(x, "member_id", "") not in member_ids)

    return keep(frame.panels), keep(frame.texts), keep(frame.gauges), keep(frame.icons)


def _card(frame, member_id):
    """``member_id``'s card as it looks wherever it stands: its panel's size, and its texts,
    bars and icons from the panel's corner."""
    x, y, width, height = _panel(frame, member_id)

    def mine(items):
        return [i for i in items if i.member_id == member_id]

    texts = [(t.text, t.x - x, t.y - y, t.role, t.align) for t in mine(frame.texts)]
    bars = [(g.resource_id, g.x - x, g.y - y, g.width, g.height) for g in mine(frame.gauges)]
    icons = [(i.asset_id, i.x - x, i.y - y) for i in mine(frame.icons)]
    return (width, height), texts, bars, icons


# --- data and editor ---------------------------------------------------------------------------


def test_the_layout_writes_the_portrait_options_only_when_set():
    library = BattlePresentationLibrary()
    plain = BattleUiLayoutProfile()
    assert (plain.hud_portraits, plain.hud_portrait_size) == ("left", 0.0)
    data = library._encode("ui_layout", plain)
    assert "hud_portraits" not in data and "hud_portrait_size" not in data
    old = BattleUiLayoutProfile(**data)  # data from before D53 reads the same
    assert old == plain
    library.add(
        "ui_layout", "set", BattleUiLayoutProfile(hud_portraits="above", hud_portrait_size=40)
    )
    raw = library.to_data()["categories"]["ui_layout"]["set"]
    assert (raw["hud_portraits"], raw["hud_portrait_size"]) == ("above", 40)
    back = BattlePresentationLibrary.from_data(library.to_data()).require("ui_layout", "set")
    assert (back.hud_portraits, back.hud_portrait_size) == ("above", 40)
    with pytest.raises(ValueError):
        BattleUiLayoutProfile(hud_portraits="below")
    with pytest.raises(ValueError):
        BattleUiLayoutProfile(hud_portrait_size=-1)


def test_the_editor_offers_the_portrait_options_in_both_languages():
    from asteria.editor.record_vocabulary import HELP, engine_enums, words

    assert engine_enums()["hud_portraits"] == ("above", "left", "off", "right")
    shown = BattlePresentationLibrary().encode_for_editor("ui_layout", BattleUiLayoutProfile())
    assert (shown["hud_portraits"], shown["hud_portrait_size"]) == ("left", 0.0)
    table = json.loads(
        (REPO / "src/asteria/editor/translations/zh_TW.json").read_text(encoding="utf-8")
    )["exact"]
    labels = [words("hud_portraits"), words("hud_portrait_size")]
    labels += [words(v) for v in engine_enums()["hud_portraits"]]
    for text in (*labels, HELP["hud_portraits"], HELP["hud_portrait_size"]):
        assert table.get(text), text


def test_the_combatant_sprites_form_picks_portraits_from_the_portrait_pictures(tmp_path):
    pytest.importorskip("PySide6")
    from PIL import Image
    from PySide6.QtWidgets import QApplication

    from asteria.editor import EditorDocument
    from asteria.editor.image_tools import IconLibrary
    from asteria.editor.record_form import RecordForm
    from asteria.project import Project

    QApplication.instance() or QApplication([])
    document = EditorDocument()
    document.project = Project.load_json(
        PARTY_RPG / "project.asteria.json", document.component_registry
    )
    document.file_path = tmp_path / "project.asteria.json"
    (tmp_path / "faces").mkdir()
    Image.new("RGBA", (38, 38), (255, 0, 255, 255)).save(tmp_path / "faces" / "hero.png")
    library = document.project.battle_presentation_library
    data = library.encode_for_editor(
        "combatant_visuals", library.require("combatant_visuals", "hero_01")
    )
    form = RecordForm(document=document)
    form.icon_library = IconLibrary(document)
    form.category = "combatant_visuals"
    assets = data["assets"]
    for key in ("portrait_asset_id", "small_portrait_asset_id"):
        picker = form.widget_for(assets, key, assets[key])
        assert type(picker).__name__ == "_PortraitPicker"
        picker.combo.showPopup()  # the whole list is filled when it is opened
        picker.combo.hidePopup()
        ids = [picker.combo.itemData(i) for i in range(picker.combo.count())]
        assert "faces/hero.png" in ids
        picker.setText("faces/hero.png")  # as choosing it in the list does
        assert assets[key] == "faces/hero.png"
        assert not picker.preview.pixmap().isNull()  # its picture shows beside the list
        picker.setText("")
        assert assets[key] is None  # none chosen: no portrait (null), not an empty id


# --- cards ------------------------------------------------------------------------------------


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("place", (*PLACES, "off"))
def test_cards_without_a_portrait_are_laid_out_as_before(mode, place):
    layout = _layout(mode, place, virtual_height=360 if place == "above" else 180)
    _, before = _compose(layout)
    _, empty = _compose(layout, portraits={})
    assert empty == before and before.portraits == ()
    # one member with a portrait: every other card looks the same...
    _, one = _compose(layout, portraits={"ally": PORTRAITS["ally"]})
    for member_id in PLACEMENT:
        if member_id != "ally":
            assert _card(one, member_id) == _card(before, member_id)
    # ... and stands where it stood, unless the portrait's card grew taller in a stack
    if place != "above" or mode == "bottom_row":
        assert _without(one, {"ally"}) == _without(before, {"ally"})
    _, off = _compose(_layout(mode, "off"), portraits=PORTRAITS)
    assert off.portraits == ()
    assert off == _compose(_layout(mode, "off"))[1]


@pytest.mark.parametrize("mode,place", list(itertools.product(MODES, PLACES)))
def test_a_portrait_sits_in_its_card_clear_of_the_name_and_bars(mode, place):
    # over the rows a portrait takes the room a full list or column has left: a taller screen
    layout = _layout(mode, place, virtual_height=360 if place == "above" else 180)
    _, plain = _compose(layout)
    _, frame = _compose(layout, portraits=PORTRAITS)
    assert {p.member_id for p in frame.portraits} == set(HEROES)
    for portrait in frame.portraits:
        box = (portrait.x, portrait.y, portrait.width, portrait.height)
        assert portrait.width == portrait.height >= 10
        card = _panel(frame, portrait.member_id)
        assert _inside(box, card)
        for other in _boxes(frame, portrait.member_id):
            assert not _hit(other, box), (other, box)
        before = _panel(plain, portrait.member_id)
        if place == "above":  # the card grew taller by the portrait
            assert card[2] == before[2] and card[3] == pytest.approx(
                before[3] + portrait.height + 2
            )
        else:  # beside the rows: the card keeps its size
            assert card == before
    panels = [(p.x, p.y, p.width, p.height) for p in frame.panels if p.panel_id.startswith("hud:")]
    for a, b in itertools.combinations(panels, 2):
        assert not _hit(a, b)
    for x, y, w, h in panels:
        assert (
            0 <= x and x + w <= layout.virtual_width and 0 <= y and y + h <= layout.virtual_height
        )


@pytest.mark.parametrize("mode", ("side_list", "column"))
def test_one_list_or_column_shows_its_portraits_at_one_size(mode):
    members = list(_members())
    # the hero's numbers are far wider and the ally's card has one row less
    hero = members[0]
    members[0] = replace(hero, gauges=(_gauge("hp", "HP", 99999, 99999, 0), *hero.gauges[1:]))
    members[1] = replace(members[1], gauges=members[1].gauges[:1])
    layout = _layout(mode, virtual_height=270)
    _, frame = _compose(layout, hud_members=tuple(members), portraits=PORTRAITS)
    assert len(frame.portraits) == 3
    assert len({p.width for p in frame.portraits}) == 1
    for portrait in frame.portraits:  # and every one still clear of its rows
        box = (portrait.x, portrait.y, portrait.width, portrait.height)
        assert not any(_hit(other, box) for other in _boxes(frame, portrait.member_id))


def test_left_or_right_puts_the_portrait_at_that_end_and_the_rows_beside_it():
    for place in ("left", "right"):
        _, frame = _compose(_layout("side_list", place), portraits=PORTRAITS)
        portrait = next(p for p in frame.portraits if p.member_id == "hero")
        card = _panel(frame, "hero")
        name = next(
            t for t in frame.texts if t.member_id == "hero" and t.role.startswith("member")
        )
        if place == "left":
            assert portrait.x == card[0] + 2 and name.x >= portrait.x + portrait.width + 3
        else:
            assert portrait.x + portrait.width == card[0] + card[2] - 2
            assert name.x == card[0] + 3


def test_small_cards_show_the_small_portrait_and_roomy_ones_the_large():
    _, frame = _compose(_layout("bottom_row"), portraits=PORTRAITS)  # 20 units: small
    assert {p.asset_id for p in frame.portraits} == {f"faces/{m}_small.png" for m in HEROES}
    roomy = _layout("side_list", "above", hud_portrait_size=40, virtual_height=400)
    _, frame = _compose(roomy, portraits=PORTRAITS)
    assert all(p.width >= PORTRAIT_LARGE for p in frame.portraits)
    assert {p.asset_id for p in frame.portraits} == {f"faces/{m}.png" for m in HEROES}
    # either stands in for the other
    _, frame = _compose(_layout("bottom_row"), portraits={"hero": ("faces/hero.png", "")})
    assert [p.asset_id for p in frame.portraits] == ["faces/hero.png"]
    _, frame = _compose(roomy, portraits={"hero": ("", "faces/hero_small.png")})
    assert [p.asset_id for p in frame.portraits] == ["faces/hero_small.png"]


def test_the_size_option_and_where_it_stops():
    _, frame = _compose(_layout("side_list", hud_portrait_size=14), portraits=PORTRAITS)
    assert {p.width for p in frame.portraits} == {14}
    # beside the rows a portrait is never taller than they are
    _, frame = _compose(_layout("bottom_row", hud_portrait_size=60), portraits=PORTRAITS)
    assert {p.width for p in frame.portraits} == {20}
    # over the rows it is as large as asked, the card grows and the stage keeps clear of it
    layout = _layout("bottom_row", "above", hud_portrait_size=30)
    _, frame = _compose(layout, portraits=PORTRAITS)
    assert {p.width for p in frame.portraits} == {30}
    assert max(_panel(frame, m)[3] for m in HEROES) == bottom_row_height(layout, True) == 56
    assert bottom_row_height(layout) == bottom_row_height(_layout("bottom_row"), True) == 24
    # over the rows of a stack: only the room the stack has left (rows are never given up)
    crowded = _layout("side_list", "above", virtual_height=200)
    _, plain = _compose(crowded)
    _, frame = _compose(crowded, portraits=PORTRAITS)
    assert [p.width for p in frame.portraits] == pytest.approx([(161 - 118) / 3 - 2] * 3)
    bottom = max(_panel(frame, m)[1] + _panel(frame, m)[3] for m in PLACEMENT)
    assert bottom <= crowded.virtual_height - crowded.margin + 1e-9  # filled to the margin
    assert [len(_card(frame, m)[2]) for m in PLACEMENT] == [
        len(_card(plain, m)[2]) for m in PLACEMENT
    ]
    _, frame = _compose(_layout("side_list", "above", virtual_height=170), portraits=PORTRAITS)
    assert frame.portraits == ()  # 13 units left for three: too small to show
    _, frame = _compose(_layout("column", "above", virtual_height=110), portraits=PORTRAITS)
    assert frame.portraits == ()
    # a card too narrow for one and its rows shows none
    _, frame = _compose(_layout("side_list", hud_panel_width=70), portraits=PORTRAITS)
    assert frame.portraits == ()


# --- the menus keep clear ----------------------------------------------------------------------


def _menu_boxes(frame):
    return [
        (p.x, p.y, p.width, p.height)
        for p in frame.panels
        if p.panel_id in ("action_menu", "action_help", "action_workflow")
    ]


@pytest.mark.parametrize(
    "layout",
    [
        # the Party RPG demo's: the menu at the acting member's lower right, over the stage
        BattleUiLayoutProfile(
            virtual_width=480,
            virtual_height=270,
            hud_panel_width=108.0,
            party_hud="side_list",
            action_menu_placement="actor_bottom_right",
            menu_over_stage=True,
            overhead_zones=("left",),
        ),
        BattleUiLayoutProfile(),  # the engine default: column HUDs, the menu centred below
        BattleUiLayoutProfile(party_hud="bottom_row", action_menu_placement="actor"),
        BattleUiLayoutProfile(party_hud="column", hud_portraits="right"),
    ],
    ids=["side_list_actor", "column_bottom", "bottom_row_actor", "column_right"],
)
@pytest.mark.parametrize("focus", HEROES)
def test_the_command_menu_and_its_boxes_never_cover_a_portrait(layout, focus):
    long = "Strikes every foe in a row for heavy fire damage and burns them for three turns."
    _, plain = _compose(layout, action_menu=_menu(long), focus_member_id=focus)
    _, frame = _compose(
        layout, action_menu=_menu(long), focus_member_id=focus, portraits=PORTRAITS
    )
    assert frame.portraits
    shown = {p.panel_id for p in frame.panels}
    assert {"action_menu", "action_help"} <= shown
    for box in _menu_boxes(frame):
        for p in frame.portraits:
            assert not _hit(box, (p.x, p.y, p.width, p.height)), (box, p)
    if not any(
        _hit(b, (p.x, p.y, p.width, p.height)) for b in _menu_boxes(plain) for p in frame.portraits
    ):
        assert _menu_boxes(frame) == _menu_boxes(plain)  # nothing in the way: nothing moved
    workflow = _workflow()
    _, frame = _compose(
        layout, action_workflow=workflow, focus_member_id=focus, portraits=PORTRAITS
    )
    for box in _menu_boxes(frame):
        for p in frame.portraits:
            assert not _hit(box, (p.x, p.y, p.width, p.height))


def _workflow():
    from asteria.presentation.battle_action_workflow import (
        BattleActionWorkflowDefinition,
        BattleActionWorkflowRuntime,
        BattleWorkflowOption,
        BattleWorkflowStep,
    )

    definition = BattleActionWorkflowDefinition(
        "cast", "Cast", (BattleWorkflowStep("target", "Choose a target"),)
    )
    options = (BattleWorkflowOption("boss", "Boss"), BattleWorkflowOption("imp", "Imp"))
    return BattleActionWorkflowRuntime().begin(definition, options)


def test_the_kept_layout_is_laid_out_again_when_the_portraits_change(monkeypatch):
    calls = []
    hud = BattleUiComposer._hud_layout

    def counted(self, *args):
        calls.append(1)
        return hud(self, *args)

    monkeypatch.setattr(BattleUiComposer, "_hud_layout", counted)
    layout = _layout("side_list")
    composer, first = _compose(layout, portraits=PORTRAITS)
    _, again = _compose(layout, composer, portraits=dict(PORTRAITS))
    assert again == first and len(calls) == 1
    _, changed = _compose(layout, composer, portraits={"hero": PORTRAITS["hero"]})
    assert len(calls) == 2 and [p.member_id for p in changed.portraits] == ["hero"]
    assert composer.portrait_boxes == {
        p.member_id: (p.x, p.y, p.width, p.height) for p in changed.portraits
    }


# --- drawing -----------------------------------------------------------------------------------


def test_the_renderer_draws_each_portrait_over_its_card_before_the_rows():
    from asteria.presentation.battle_ui_renderer import BattleUiRenderer, HeadlessBattleUiBackend

    _, frame = _compose(_layout("side_list"), portraits=PORTRAITS)
    backend = HeadlessBattleUiBackend()
    BattleUiRenderer(backend).render(frame)
    kinds = [op[0] for op in backend.ops]
    drawn = [op for op in backend.ops if op[0] == "portrait"]
    assert drawn == [("portrait", p.asset_id, p.member_id) for p in frame.portraits]
    first, last = kinds.index("portrait"), len(kinds) - 1 - kinds[::-1].index("portrait")
    hud_panels = [
        i for i, op in enumerate(backend.ops) if op[0] == "panel" and op[1].startswith("hud:")
    ]
    assert max(hud_panels) < first and last < kinds.index("gauge") and last < kinds.index("text")

    class Older(HeadlessBattleUiBackend):  # a backend from before D53 has no draw_portrait
        draw_portrait = None

    BattleUiRenderer(Older()).render(frame)  # draws the cards, no portraits, no error


def test_the_pygame_backend_fits_the_picture_in_its_box_and_centres_it(monkeypatch):
    pygame = pytest.importorskip("pygame")
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    from asteria.platform.pygame_battle_ui import PygameBattleUiBackend

    pygame.init()
    screen = pygame.Surface((320, 200))
    asked = []

    def resolve(asset_id, width, height):
        asked.append((asset_id, width, height))
        picture = pygame.Surface((height // 2, height))  # a tall bust: narrower than the box
        picture.fill((255, 0, 255))
        return picture

    backend = PygameBattleUiBackend(screen, scale=2.0, resolve_portrait=resolve)
    backend.draw_portrait(BattleUiPortrait("hero", "faces/hero.png", 10, 20, 30, 30))
    assert asked == [("faces/hero.png", 60, 60)]  # fitted in screen pixels
    assert screen.get_at((50, 70))[:3] == (255, 0, 255)  # the box's centre
    assert screen.get_at((22, 70))[:3] == (0, 0, 0)  # beside the narrower picture: untouched
    PygameBattleUiBackend(screen).draw_portrait(  # no loader: nothing drawn, no error
        BattleUiPortrait("hero", "faces/hero.png", 100, 20, 30, 30)
    )
    assert screen.get_at((115, 35))[:3] == (0, 0, 0)


# --- a real battle -----------------------------------------------------------------------------


@pytest.fixture
def battle(monkeypatch, tmp_path):
    pygame = pytest.importorskip("pygame")
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    from PIL import Image

    from asteria.editor import EditorDocument
    from asteria.project import Project
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    def start(portraits=True, **layout):
        project = Project.load_json(
            PARTY_RPG / "project.asteria.json", EditorDocument().component_registry
        )
        library = project.battle_presentation_library
        if portraits:
            for index, key in enumerate(f"hero_{n:02d}" for n in range(1, 5)):
                face = tmp_path / f"face_{index}.png"
                Image.new("RGBA", (38, 38), (255, 0, 255 - index, 255)).save(face)
                profile = library.require("combatant_visuals", key)
                assets = replace(profile.assets, portrait_asset_id=str(face))
                library.set("combatant_visuals", key, replace(profile, assets=assets))
            library.set(
                "combatant_visuals",
                "hero_05",
                replace(
                    library.require("combatant_visuals", "hero_05"),
                    assets=replace(
                        library.require("combatant_visuals", "hero_05").assets,
                        portrait_asset_id=str(tmp_path / "missing.png"),
                    ),
                ),
            )
        for key in library.ids("ui_layout"):
            library.set("ui_layout", key, replace(library.require("ui_layout", key), **layout))
        runtime = PlayableTestRuntime(
            project, project.game_start.instantiate(project), PARTY_RPG, width=960, height=540
        )
        runtime.open()
        runtime._ui_mode = "field"
        runtime.game.start_encounter("boss_room")
        runtime._battle_presentation.begin()
        runtime._advance_to_hero_turn()
        runtimes.append(runtime)
        for _ in range(30):  # the HUD syncs with the battle and the command menu opens
            runtime._frame([], 1 / 60)
        return runtime

    runtimes = []
    yield start
    for runtime in runtimes:
        runtime.close()
    pygame.quit()


def test_a_real_battle_draws_the_party_portraits_where_nothing_covers_them(battle):
    runtime = battle()
    adapter = runtime._battle_presentation
    party = {m.member_id for m in runtime.game.battle.members.values() if m.side == "heroes"}
    shown = adapter.screen.member_portraits
    assert shown and set(shown) <= party
    assert all(ids[0] and not ids[1] for ids in shown.values())
    assert not any(m.startswith("hero_05") for m in shown)  # its picture is missing: no portrait
    result = adapter.draw()
    frame = result.frame
    assert {p.member_id for p in frame.portraits} == set(shown)
    scale = runtime.width / adapter.screen.composer.layout.virtual_width
    for portrait in frame.portraits:
        cx = round((portrait.x + portrait.width / 2) * scale)
        cy = round((portrait.y + portrait.height / 2) * scale)
        colour = runtime.screen.get_at((cx, cy))[:3]
        assert colour[:2] == (255, 0), (portrait.member_id, colour)  # the stand-in face
        box = (portrait.x, portrait.y, portrait.width, portrait.height)
        for item in (*frame.texts, *frame.gauges):
            if getattr(item, "member_id", "") == portrait.member_id and hasattr(item, "width"):
                assert not _hit((item.x, item.y, item.width, item.height), box)
        for menu in _menu_boxes(frame):
            assert not _hit(menu, box)


def test_a_real_battle_without_portraits_or_with_them_off_draws_none(battle):
    plain = battle(portraits=False)
    assert plain._battle_presentation.screen.member_portraits == {}
    assert plain._battle_presentation.draw().frame.portraits == ()
    off = battle(hud_portraits="off")
    assert off._battle_presentation.screen.member_portraits  # set, but the layout hides them
    assert off._battle_presentation.draw().frame.portraits == ()
