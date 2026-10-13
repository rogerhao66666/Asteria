"""CMP-01 / CMP-02 / CMP-04: layered characters, sockets and attachments authored on a sheet and
drawn in battle."""

from pathlib import Path

import pytest

from asteria.editor import EditorDocument
from asteria.editor.character_composition_authoring import (
    CharacterCompositionAuthoring,
    CompositionAuthoringError,
)
from asteria.presentation.character_composition import CharacterComposition
from asteria.project import Project

REF = Path(__file__).parents[1] / "reference_projects/complex_reference_rpg/project.asteria.json"
BODY = "battle.combatant.hero_01"
ITEM = "battle.fx.heal"  # any sprite sheet can be worn; 64x64 frames in a 4x4 grid


def _api(project=None):
    document = EditorDocument()
    document.set_project(
        project or Project.load_json(REF, document.component_registry), file_path=REF
    )
    return CharacterCompositionAuthoring(document)


def _author(api, sheet=BODY):
    api.add_socket(sheet, "hand", 10, -30)
    api.set_socket_key(sheet, "hand", 0, 10, -30)
    api.set_socket_key(sheet, "hand", 4, 20, -20, rotation=45)
    api.attach(sheet, "charm", ITEM, "hand", scale=0.25, frame=5)
    api.add_layer(sheet, ITEM, component_id="cape", z=-1, clips=("idle",))


def test_sockets_attachments_and_layers_are_undoable_sheet_metadata():
    api = _api()
    _author(api)
    rig, attachments, layers = api.composition(BODY)
    assert set(rig.sockets) == {"hand"} and [k.frame for k in rig.sockets["hand"].keys] == [0, 4]
    assert [(a.id, a.asset_id, a.socket_id, a.metadata["frame"]) for a in attachments] == [
        ("charm", ITEM, "hand", 5)
    ]
    assert [(x.component_id, x.z, x.clips) for x in layers.layers] == [("cape", -1.0, ("idle",))]
    meta = api.animation.asset(BODY).meta()  # canonical storage: the body sheet's asset metadata
    assert (
        meta["attachments"][0]["socket_id"] == "hand"
        and meta["socket_rig"]["sockets"][0]["id"] == "hand"
    )
    with pytest.raises(CompositionAuthoringError, match="holds attachments"):
        api.remove_socket(BODY, "hand")
    with pytest.raises(CompositionAuthoringError, match="unknown socket"):
        api.attach(BODY, "hat", ITEM, "head")
    with pytest.raises(CompositionAuthoringError, match="unique"):
        api.attach(BODY, "charm", ITEM, "hand")
    with pytest.raises(CompositionAuthoringError):
        api.attach(BODY, "ghost", "no.such.sheet", "hand")
    for _ in range(5):  # one undo step per edit
        api.document.undo()
    rig, attachments, layers = api.composition(BODY)
    assert not rig.sockets and not attachments and not layers.layers


def test_the_attachment_follows_the_socket_keyed_per_frame():
    api = _api()
    _author(api)
    parts = {p.id: p for p in api.parts(BODY, 0, "idle")}
    assert parts["cape"].behind and not parts["charm"].behind
    assert (parts["charm"].x, parts["charm"].y, parts["charm"].rotation_deg) == (10.0, -30.0, 0.0)
    halfway = {p.id: p for p in api.parts(BODY, 2, "attack")}
    assert halfway["charm"].x == pytest.approx(15.0) and halfway[
        "charm"
    ].rotation_deg == pytest.approx(22.5)
    assert "cape" not in halfway  # the layer only shows in the idle clip
    keyed = {p.id: p for p in api.parts(BODY, 4)}
    assert keyed["charm"].rotation_deg == pytest.approx(45.0) and keyed[
        "charm"
    ].scale_x == pytest.approx(0.25)
    api.edit_attachment(BODY, "charm", visible=False)
    assert [p.id for p in api.parts(BODY, 0, "idle")] == ["cape"]


def test_a_sheet_without_composition_costs_nothing():
    assert CharacterComposition.from_meta(_api().animation.asset(BODY).meta()) is None


# --- the real battle screen draws what was authored ----------------------------------------------


@pytest.fixture
def battle(resource_root, monkeypatch):
    pytest.importorskip("pygame")
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    from test_playable_battle_loop import _boss_runtime

    from asteria.runtime.battle_presentation_adapters import CanonicalBattleAdapter

    runtime = _boss_runtime(resource_root)
    yield runtime, CanonicalBattleAdapter
    runtime.close()


def _start(runtime, adapter_type):
    runtime._battle_presentation = adapter = adapter_type(runtime)
    runtime.game.start_encounter("boss_room")
    adapter.begin()
    runtime._advance_to_hero_turn()
    runtime._present_battle(0.016)
    return adapter


def _draws(adapter):
    from asteria.runtime.camera import Camera2D

    layout = adapter.screen.composer.layout
    return adapter.screen.animation.build_frame(
        Camera2D(width=layout.virtual_width, height=layout.virtual_height)
    )


def test_battle_draws_layers_behind_and_attachments_in_front_of_the_body(battle):
    runtime, adapter_type = battle
    api = _api(runtime.game.project)
    heroes = [s for s in api.sheets() if s.startswith("battle.combatant.hero")]
    for sheet in heroes:
        _author(api, sheet)
    adapter = _start(runtime, adapter_type)
    assert not adapter.composition_errors
    frame = _draws(adapter)
    order = list(frame.combatant_draws)
    staged = [v for v in adapter.screen.scene.combatants if v.sprite_sheet_asset_id in heroes]
    assert staged and all(v.member_id in adapter.screen.animation.compositions for v in staged)
    for hero in staged:
        body = next(
            d
            for d in order
            if d.texture_asset_id == hero.sprite_sheet_asset_id and d.depth == hero.anchor.depth
        )
        mine = [
            d
            for d in order
            if d.texture_asset_id == ITEM and abs(d.depth - hero.anchor.depth) < 1e-3
        ]
        behind = [d for d in mine if d.depth < body.depth]
        front = [d for d in mine if d.depth > body.depth]
        assert (
            len(behind) == 1 and len(front) == 1
        )  # cape layer (idle pose) behind, charm in front
        assert order.index(behind[0]) < order.index(body) < order.index(front[0])
        charm = front[0]
        assert charm.width == pytest.approx(64 * 0.25 / hero.source_pixels_per_logical_pixel)
        assert charm.flip_x == (hero.anchor.facing.lower() == "left")  # mirrors with the body
    enemies = [v for v in adapter.screen.scene.combatants if v not in staged]
    assert enemies and all(
        v.member_id not in adapter.screen.animation.compositions for v in enemies
    )
    adapter.draw()  # renders through the pygame texture drawer
    assert adapter.textures.draw_count >= len(staged) * 3


# --- rotated parts render the same on both backends ----------------------------------------------


def test_rotated_quads_turn_about_their_centre_on_the_gpu_backend():
    from asteria.platform.moderngl_backend import ModernglRuntimeBackend

    backend = ModernglRuntimeBackend.__new__(ModernglRuntimeBackend)
    texture = object()
    backend._batch_texture, backend._batch_vertices, backend._batch_indices = texture, [], []
    backend._enqueue_quad(
        texture, 10, 10, (0, 0, 10, 10), 0, 0, 10, 20, 1.0, False, rotation_deg=90
    )
    corners = [
        tuple(round(v, 6) for v in backend._batch_vertices[i : i + 2]) for i in range(0, 32, 8)
    ]
    # a 10x20 quad centred on (5, 10) turned a quarter clockwise (y down): top-left goes to the
    # top-right
    assert corners == [(15.0, 5.0), (15.0, 15.0), (-5.0, 15.0), (-5.0, 5.0)]


def test_rotated_parts_keep_their_centre_on_the_pygame_backend(resource_root, monkeypatch):
    pygame = pytest.importorskip("pygame")
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    from asteria.runtime.battle_presentation_adapters import PygameTextureDrawer

    pygame.init()
    screen = pygame.Surface((100, 100), pygame.SRCALPHA)
    image = pygame.Surface((10, 20), pygame.SRCALPHA)
    image.fill((255, 0, 0, 255))

    class Host:
        pg = pygame

        def __init__(self):
            self.screen = screen

        def load_image(self, _uri):
            return image

    class Resolver:
        def source_uri(self, asset_id):
            return asset_id

    PygameTextureDrawer(Host(), Resolver(), 1.0).blit_region(
        "x", (0, 0, 10, 20), 40, 40, 10, 20, rotation_deg=90
    )
    painted = pygame.mask.from_surface(screen).get_bounding_rects()[0]
    assert painted.center == (45, 50) and painted.size == (20, 10)


# --- the Character Composition tab ---------------------------------------------------------------


def test_composition_tab_authors_through_its_forms_and_previews_the_parts():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication, QGraphicsPixmapItem

    from asteria.editor.character_composition_widget import CharacterCompositionWidget

    QApplication.instance() or QApplication([])
    widget = CharacterCompositionWidget(_api().document)
    widget.refresh(select=BODY)
    widget.socket_id.setText("hand")
    widget.socket_x.setValue(10)
    widget.socket_y.setValue(-30)
    assert widget.add_socket_from_form() and widget.sockets.count() == 1
    widget.frame.setValue(4)
    widget.socket_rotation.setValue(45)
    assert widget.key_socket_from_form() and "keys 4" in widget.sockets.item(0).text()
    widget.attachment_id.setText("charm")
    widget.item_sheet.setCurrentText(ITEM)
    widget.attach_socket.setCurrentText("hand")
    widget.attach_scale.setValue(0.25)
    assert widget.attach_from_form() and "charm" in widget.attachments.item(0).text()
    widget.layer_sheet.setCurrentText(ITEM)
    widget.layer_component.setText("cape")
    widget.layer_z.setValue(-1)
    assert widget.add_layer_from_form() and widget.layers.count() == 1
    pixmaps = [i for i in widget.preview.scene().items() if isinstance(i, QGraphicsPixmapItem)]
    assert len(pixmaps) == 3  # cape behind, body, charm in front
    widget.attachment_id.setText("charm")
    assert (
        widget.attach_from_form() is None and "unique" in widget.last_error
    )  # errors surface, nothing changes
    widget.sockets.setCurrentRow(0)
    widget.attachments.setCurrentRow(0)
    rig, attachments, _ = widget.api.composition(BODY)
    assert [a.id for a in attachments] == ["charm"] and rig.sockets["hand"].keys[
        -1
    ].transform.rotation_deg == 45
    widget.api.document.undo()  # the layer
    widget.refresh()
    assert widget.layers.count() == 0


def test_game_text_falls_back_to_ascii_for_glyphs_the_font_lacks():
    pygame = pytest.importorskip("pygame")
    from asteria.platform.pygame_battle_ui import renderable_text

    pygame.font.init()
    font = pygame.font.Font(None, 20)  # the default font has no arrow glyph
    assert renderable_text(pygame, font, "move_right → D", {}) == "move_right -> D"
    assert renderable_text(pygame, font, "Lv 1→2 ok", {}) == "Lv 1->2 ok"


def test_the_playable_field_draws_the_players_layers_and_attachments(resource_root, monkeypatch):
    """CMP-01 in the field: a composition authored on the player's canonical sheet is drawn with
    the player."""
    pytest.importorskip("pygame")
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    from test_playable_battle_loop import _boss_runtime

    from asteria.assets.canonical import AssetSource, CanonicalAsset

    runtime = _boss_runtime(resource_root)
    try:
        project = runtime.game.project
        sheet = runtime.manifest["field"]["player_sheet"]
        fw, fh = runtime.manifest["field"]["player_frame_size"]
        project.assets.register(
            CanonicalAsset(
                "field.player",
                "sprite_sheet",
                AssetSource(sheet),
                metadata=(("frame_size", [fw, fh]), ("clips", {})),
            )
        )
        api = _api(project)
        api.add_socket("field.player", "hand", 12, -20)
        api.attach("field.player", "charm", ITEM, "hand", scale=0.5, frame=5)
        api.add_layer("field.player", ITEM, component_id="halo", z=-1)
        runtime._ui_mode = "field"
        runtime._frame([], 0.016)
        plain_counts = (len(runtime.__dict__.get("_field_compositions", {})),)
        behind, front = runtime._composition_parts(
            sheet, 1, "idle_down", (fw, fh), (64, 64), (100, 100)
        )
        assert len(behind) == 1 and len(front) == 1 and plain_counts == (1,)
        charm_image, (cx, cy) = front[0]
        assert charm_image.get_width() == round(
            64 * 0.5
        )  # ITEM frames are 64 px, scaled with the body
        assert (cx, cy) == (100 + 32 + 12, 100 + 64 - 20)  # pivot (feet) + socket offset
    finally:
        runtime.close()
