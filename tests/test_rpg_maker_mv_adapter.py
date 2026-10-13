from pathlib import Path

import pytest

from asteria.assets import AssetRegistry
from asteria.assets.local_reference import resolve_rpg_maker_mv_root
from asteria.assets.rpg_maker_mv import RPGMakerMVImporter

STEAM_MV_ROOT = Path(
    "/Users/roger/Library/Application Support/Steam/steamapps/common/RPG Maker MV"
)
REPO_ROOT = Path(__file__).resolve().parents[1]


def real_mv_file(category: str, pattern: str = "*.png") -> Path:
    root = resolve_rpg_maker_mv_root(REPO_ROOT, STEAM_MV_ROOT)
    if root is None:
        pytest.skip(f"real RPG Maker MV {category} fixture unavailable")
    matches = sorted(root.glob(f"**/img/{category}/{pattern}"))
    if not matches:
        pytest.skip(f"real RPG Maker MV {category} fixture unavailable")
    return matches[0]


def test_real_mv_character_sheet_preserves_direction_and_frame_contract():
    # Break caught: treating MV's source layout as a generic engine limitation or
    # using the wrong row order for Down/Left/Right/Up.
    source = real_mv_file("characters", "Actor*.png")
    imported = RPGMakerMVImporter().inspect(source)

    assert imported.category == "characters"
    assert imported.source_size == (576, 384)
    assert imported.alpha is True
    assert imported.frame_size == (48, 48)
    assert imported.character_count == 8
    assert imported.frames_per_direction == 3
    assert imported.directions == ("down", "left", "right", "up")
    assert imported.idle_frame == 1


def test_real_mv_single_and_object_character_filename_semantics():
    # Break caught: ignoring the `$` single-character and `!` object-alignment
    # semantics encoded in real MV filenames.
    single = RPGMakerMVImporter().inspect(real_mv_file("characters", "$*.png"))
    object_sheet = RPGMakerMVImporter().inspect(real_mv_file("characters", "!*.png"))

    assert single.character_count == 1
    assert single.frame_size == (single.source_size[0] // 3, single.source_size[1] // 4)
    assert object_sheet.object_character is True
    assert object_sheet.anchor == (0.5, 1.0)


@pytest.mark.parametrize(
    ("category", "expected_layout"),
    [
        ("faces", "faces_4x2"),
        ("sv_actors", "sv_actor_9x6"),
        ("enemies", "single_image"),
        ("sv_enemies", "single_image"),
        ("tilesets", "tileset_source"),
        ("animations", "animation_sheet_5x5"),
        ("pictures", "single_image"),
        ("parallaxes", "single_image"),
    ],
)
def test_real_mv_categories_are_detected_without_copying(category, expected_layout):
    # Break caught: category detection based on guessed names instead of the
    # actual MV img/<category> boundary.
    source = real_mv_file(category)
    imported = RPGMakerMVImporter().inspect(source)

    assert imported.category == category
    assert imported.layout == expected_layout
    assert imported.source_path == source.resolve()
    assert imported.source_size[0] > 0 and imported.source_size[1] > 0


def test_real_mv_import_converts_to_canonical_and_registers_without_copying():
    # Break caught: an adapter that parses an image but cannot cross the
    # canonical AssetRegistry boundary or serialise its metadata.
    source = real_mv_file("sv_actors")
    importer = RPGMakerMVImporter()
    imported = importer.inspect(source)
    canonical = importer.to_canonical(imported, asset_id="fixture.mv.actor2_1")
    registry = AssetRegistry()

    registry.register(canonical)
    encoded = importer.to_dict(imported)
    decoded = importer.from_dict(encoded)

    assert registry.resolve("fixture.mv.actor2_1") == canonical
    assert canonical.kind == "sprite_sheet"
    assert canonical.source.uri == str(source.resolve())
    assert decoded == imported


def test_real_mv_walking_clip_boxes_use_down_left_right_up_rows():
    # Break caught: a walking vertical slice using the wrong row or mixing one
    # character's 3x4 block with the neighbouring character.
    imported = RPGMakerMVImporter().inspect(real_mv_file("characters", "Actor1.png"))
    importer = RPGMakerMVImporter()

    assert importer.walk_clip_boxes(imported, character_index=0, direction="down") == (
        (0, 0, 48, 48),
        (48, 0, 96, 48),
        (96, 0, 144, 48),
    )
    assert importer.walk_clip_boxes(imported, character_index=0, direction="up") == (
        (0, 144, 48, 192),
        (48, 144, 96, 192),
        (96, 144, 144, 192),
    )
    assert importer.walk_clip_boxes(imported, character_index=1, direction="down")[0] == (
        144,
        0,
        192,
        48,
    )


def test_real_mv_side_view_actor_motion_extraction_stays_in_adapter():
    # Break caught: hard-coding MV's 9x6 motion topology into generic animation
    # core instead of translating it to arbitrary clip frame boxes here.
    imported = RPGMakerMVImporter().inspect(real_mv_file("sv_actors", "Actor1_1.png"))
    importer = RPGMakerMVImporter()

    assert imported.frame_size == (64, 64)
    assert importer.side_view_motion_boxes(imported, motion_index=0) == (
        (0, 0, 64, 64),
        (64, 0, 128, 64),
        (128, 0, 192, 64),
    )
    assert importer.side_view_motion_boxes(imported, motion_index=6) == (
        (192, 0, 256, 64),
        (256, 0, 320, 64),
        (320, 0, 384, 64),
    )
    assert importer.side_view_motion_boxes(imported, motion_index=9) == (
        (192, 192, 256, 256),
        (256, 192, 320, 256),
        (320, 192, 384, 256),
    )
    assert importer.side_view_motion_boxes(imported, motion_index=17) == (
        (384, 320, 448, 384),
        (448, 320, 512, 384),
        (512, 320, 576, 384),
    )


def test_mv_clip_extraction_rejects_out_of_range_requests():
    imported = RPGMakerMVImporter().inspect(real_mv_file("characters", "Actor1.png"))
    importer = RPGMakerMVImporter()

    with pytest.raises(ValueError, match="character_index"):
        importer.walk_clip_boxes(imported, character_index=8, direction="down")
    with pytest.raises(ValueError, match="direction"):
        importer.walk_clip_boxes(imported, character_index=0, direction="northwest")


def test_invalid_or_unsupported_mv_asset_fails_clearly(tmp_path):
    # Break caught: unsupported or malformed sources silently entering the
    # canonical pipeline.
    malformed = tmp_path / "img" / "characters" / "Broken.png"
    malformed.parent.mkdir(parents=True)
    malformed.write_bytes(b"not a png")

    with pytest.raises(ValueError, match="invalid RPG Maker MV image"):
        RPGMakerMVImporter().inspect(malformed)

    outside = tmp_path / "unknown" / "Thing.png"
    outside.parent.mkdir()
    outside.write_bytes(real_mv_file("characters").read_bytes())
    with pytest.raises(ValueError, match="unsupported RPG Maker MV category"):
        RPGMakerMVImporter().inspect(outside)
