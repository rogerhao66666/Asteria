import json
from pathlib import Path

import pytest
from PIL import Image

from asteria.assets.character_generator import CharacterRecipe
from asteria.assets.character_bundle import CharacterBundleGenerator
from asteria.assets.local_reference import resolve_rpg_maker_mv_root
from asteria.assets.rpg_maker_mv_generator import (
    MVGeneratorPart,
    MVGeneratorRepresentation,
    RPGMakerMVGeneratorCatalog,
)


def _real_catalog():
    repo = Path(__file__).resolve().parents[1]
    return RPGMakerMVGeneratorCatalog.discover(resolve_rpg_maker_mv_root(repo))


def test_real_mv_part_generates_coordinated_atomic_bundle(tmp_path):
    catalog = _real_catalog()
    part = next(
        item for item in catalog.parts
        if item.source_category == "AccA" and item.part_number == 14
        and item.gender == "Male" and "Modern_Generator/parts" in item.source_root.as_posix()
    )
    recipe = CharacterRecipe("hero-one", parts={"accessory": part.id})

    bundle = CharacterBundleGenerator(catalog).generate(recipe, tmp_path / "generated")

    assert bundle.output_dir == tmp_path / "generated" / "hero-one"
    assert Image.open(bundle.walking_path).size == (144, 192)
    assert Image.open(bundle.face_path).size == (144, 144)
    assert Image.open(bundle.side_view_path).size == (576, 384)
    assert all(Image.open(path).mode == "RGBA" for path in bundle.visual_paths)
    assert all(Image.open(path).getpixel((0, 0))[3] == 0 for path in bundle.visual_paths)
    assert bundle.anchor == (24, 48)
    assert bundle.source_part_ids == (part.id,)
    assert tuple(asset.kind for asset in bundle.canonical_assets) == (
        "character.walking", "character.face", "character.side_view"
    )
    metadata = json.loads(bundle.metadata_path.read_text(encoding="utf-8"))
    assert metadata["source_part_ids"] == [part.id]
    assert metadata["walking"]["frame_size"] == [48, 48]
    assert not any(path.name.startswith(".hero-one-") for path in (tmp_path / "generated").iterdir())


def _png(path, size=(144, 192), rgba=(255, 0, 0, 255)):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", size, rgba).save(path)
    return path


def _catalog(tmp_path, *, face=True, bad_side=False, masks=True):
    root = tmp_path / "Generator"
    walk = _png(root / "TV.png")
    side = _png(root / "SV.png", (100, 100) if bad_side else (576, 384))
    portrait = _png(root / "FG.png", (144, 144))
    walk_mask = _png(root / "TV_c.png", rgba=(0, 0, 0, 0))
    side_mask = _png(root / "SV_c.png", (576, 384), (0, 0, 0, 0))
    part = MVGeneratorPart(
        "mvgen.test.body", root, "Male", "Body", "body", 1,
        walking=MVGeneratorRepresentation("walking", (walk,), (walk_mask,) if masks else ()),
        face=MVGeneratorRepresentation("face", (portrait,)) if face else None,
        side_view=MVGeneratorRepresentation("side_view", (side,), (side_mask,) if masks else ()),
    )
    return RPGMakerMVGeneratorCatalog((root,), (part,), (), 5), part


@pytest.mark.parametrize("mode", ["missing", "canvas", "mask"])
def test_validation_fails_before_publishing_partial_bundle(tmp_path, mode):
    catalog, part = _catalog(
        tmp_path / "source", face=mode != "missing", bad_side=mode == "canvas", masks=mode != "mask"
    )
    palette = {"body": "#805030"} if mode == "mask" else {}
    recipe = CharacterRecipe("broken", parts={"body": part.id}, palette=palette)
    output = tmp_path / "generated"

    with pytest.raises(ValueError, match={
        "missing": "face unavailable", "canvas": "side_view canvas", "mask": "walking mask"
    }[mode]):
        CharacterBundleGenerator(catalog).generate(recipe, output)

    assert not (output / "broken").exists()
    assert not output.exists() or not tuple(output.iterdir())
