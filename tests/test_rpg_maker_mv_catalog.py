from pathlib import Path

import pytest

from asteria.assets.local_reference import discover_mv_projects, resolve_rpg_maker_mv_root
from asteria.assets.rpg_maker_mv_catalog import RPGMakerMVCatalog
from asteria.assets.rpg_maker_mv_database import RPGMakerMVDatabase

pytestmark = pytest.mark.mv_reference


def _catalog():
    repo = Path(__file__).resolve().parents[1]
    root = resolve_rpg_maker_mv_root(repo)
    layout = discover_mv_projects(root)[0]
    return RPGMakerMVCatalog.build(layout, RPGMakerMVDatabase.load(layout))


def test_real_catalog_indexes_all_visual_categories():
    catalog = _catalog()

    for category in (
        "characters",
        "faces",
        "sv_actors",
        "enemies",
        "sv_enemies",
        "tilesets",
        "battlebacks1",
        "battlebacks2",
        "animations",
        "parallaxes",
        "system",
        "titles1",
        "titles2",
    ):
        assert catalog.images_for(category), category
    assert catalog.category_root("pictures").name == "pictures"
    assert catalog.resolve_image("system", "IconSet").is_file()
    assert len(catalog.assets) == 498


def test_iconset_indices_resolve_to_32_pixel_boxes():
    catalog = _catalog()

    first = catalog.icon(1)

    assert first.index == 1
    assert first.source.name == "IconSet.png"
    assert first.box == (32, 0, 64, 32)


def test_audio_references_resolve_both_available_encodings():
    catalog = _catalog()

    title = catalog.audio("bgm", "Theme6")
    cursor = catalog.audio("se", "Cursor2")

    assert {path.suffix for path in title.candidates} == {".ogg", ".m4a"}
    assert {path.suffix for path in cursor.candidates} == {".ogg", ".m4a"}


def test_missing_empty_and_out_of_range_references_are_nonfatal():
    catalog = _catalog()

    assert catalog.resolve_image("characters", "") is None
    assert catalog.resolve_image("characters", "DoesNotExist") is None
    assert catalog.icon(999999) is None
    assert catalog.audio("bgm", "DoesNotExist").candidates == ()
    codes = {issue.code for issue in catalog.issues}
    assert {"image.empty", "image.missing", "icon.out_of_range", "audio.missing"} <= codes
