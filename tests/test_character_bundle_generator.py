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
    body = next(item for item in catalog.parts if item.category == "body" and item.gender == "Male"
                and item.source_root.parent.name == "rpg_maker_mv")
    recipe = CharacterRecipe("hero-one", parts={"body": body.id, "accessory": part.id}, body_family="Male")

    bundle = CharacterBundleGenerator(catalog).generate(recipe, tmp_path / "generated")

    assert bundle.output_dir == tmp_path / "generated" / "hero-one"
    assert Image.open(bundle.walking_path).size == (144, 192)
    assert Image.open(bundle.face_path).size == (144, 144)
    assert Image.open(bundle.side_view_path).size == (576, 384)
    assert all(Image.open(path).mode == "RGBA" for path in bundle.visual_paths)
    assert all(Image.open(path).getpixel((0, 0))[3] == 0 for path in bundle.visual_paths)
    assert bundle.anchor == (24, 48)
    assert bundle.source_part_ids == (body.id, part.id)
    assert tuple(asset.kind for asset in bundle.canonical_assets) == (
        "character.walking", "character.face", "character.damaged", "character.side_view"
    )
    metadata = json.loads(bundle.metadata_path.read_text(encoding="utf-8"))
    assert metadata["source_part_ids"] == [body.id, part.id]
    assert metadata["walking"]["frame_size"] == [48, 48]
    assert not any(path.name.startswith(".hero-one-") for path in (tmp_path / "generated").iterdir())


def test_new_bundle_rejects_recipe_without_a_body(tmp_path):
    catalog = _real_catalog()
    accessory = next(part for part in catalog.parts if part.category == "accessory" and part.gender == "Male")
    recipe = CharacterRecipe("no-body", parts={"accessory": accessory.id})

    with pytest.raises(ValueError, match="body part required"):
        CharacterBundleGenerator(catalog).generate(recipe, tmp_path / "generated")
    assert not (tmp_path / "generated" / "no-body").exists()


def test_full_core_body_generates_editable_four_sheet_bundle(tmp_path):
    catalog = _real_catalog()
    root = next(part.source_root for part in catalog.parts
                if part.category == "body" and part.gender == "Kid"
                and part.source_root.parent.name == "rpg_maker_mv")
    body = next(part for part in catalog.parts if part.source_root == root
                and part.gender == "Kid" and part.category == "body")
    hair = next(part for part in catalog.parts if part.source_root == root
                and part.gender == "Kid" and part.category == "hair_front")
    recipe = CharacterRecipe("kid-hero", parts={"body": body.id, "hair_front": hair.id},
                             body_family="Kid")

    bundle = CharacterBundleGenerator(catalog).generate(recipe, tmp_path / "generated")

    assert bundle.damaged_path is not None
    assert Image.open(bundle.damaged_path).size == (144, 48)
    assert len(bundle.all_visual_paths) == 4
    metadata = json.loads(bundle.metadata_path.read_text(encoding="utf-8"))
    assert metadata["recipe"]["body_family"] == "Kid"
    assert metadata["damaged"]["canvas"] == [144, 48]


def test_mixed_family_recipe_is_rejected_before_output(tmp_path):
    catalog = _real_catalog()
    body = next(part for part in catalog.parts if part.category == "body" and part.gender == "Male")
    hair = next(part for part in catalog.parts if part.category == "hair_front" and part.gender == "Female")
    recipe = CharacterRecipe("broken-family", parts={"body": body.id, "hair_front": hair.id}, body_family="Male")

    with pytest.raises(ValueError, match="incompatible body family"):
        CharacterBundleGenerator(catalog).generate(recipe, tmp_path / "generated")
    assert not (tmp_path / "generated" / "broken-family").exists()


def test_mv_face_iris_layer_stays_visible_above_eye_white():
    catalog = _real_catalog()
    core = [part for part in catalog.parts if part.source_root.parent.name == "rpg_maker_mv"
            and part.gender == "Male"]
    body = next(part for part in core if part.category == "body" and part.part_number == 1)
    eyes = next(part for part in core if part.category == "eyes" and part.part_number == 1)
    recipe = CharacterRecipe("eyes", parts={"body": body.id, "eyes": eyes.id}, body_family="Male")

    face = CharacterBundleGenerator(catalog).compose("face", recipe)

    red, green, blue, alpha = face.getpixel((68, 62))
    assert alpha == 255
    assert blue > red + 40


def test_mv_face_stays_in_front_of_high_collar_and_scarf_layers():
    catalog = _real_catalog()
    generator_root = (resolve_rpg_maker_mv_root(Path(__file__).resolve().parents[1]) / "Generator").resolve()
    core = [part for part in catalog.parts if part.source_root == generator_root and part.gender == "Male"]
    numbers = {"body": 1, "face_shape": 3, "eyes": 25, "eyebrows": 2, "nose": 1,
               "mouth": 1, "hair_back": 5, "hair_front": 5, "outfit": 3, "cloak": 4}
    parts = {category: next(part for part in core
                            if part.category == category and part.part_number == number)
             for category, number in numbers.items()}
    recipe = CharacterRecipe("face-protection", parts={key: part.id for key, part in parts.items()},
                             body_family="Male")

    face = CharacterBundleGenerator(catalog).compose("face", recipe)

    # At (45, 92), the original clothing/cape pixels overlap the face silhouette.
    # The face skin must remain visible there instead of being painted over by the collar.
    red, green, blue, alpha = face.getpixel((45, 92))
    assert alpha == 255
    assert red > 180 and green > 150 and blue > 130


def test_palette_recolor_preserves_part_shading_and_transparency(tmp_path):
    source = Image.new("RGBA", (3, 1), (0, 0, 0, 0))
    source.putpixel((0, 0), (40, 30, 20, 255))
    source.putpixel((1, 0), (220, 200, 160, 255))
    mask = Image.new("RGBA", (3, 1), (255, 200, 0, 0))
    mask.putpixel((0, 0), (255, 200, 0, 255))
    mask.putpixel((1, 0), (255, 200, 0, 255))
    mask_path = tmp_path / "hair_c.png"
    mask.save(mask_path)

    CharacterBundleGenerator._colorize_mask(source, mask_path, "#3050c0")

    dark, light, clear = (source.getpixel((x, 0)) for x in range(3))
    assert dark != light
    assert dark[2] > dark[0]
    assert light[2] > light[0]
    assert sum(light[:3]) > sum(dark[:3])
    assert clear[3] == 0


def test_hair_palette_updates_face_without_tinting_skin():
    catalog = _real_catalog()
    core = [part for part in catalog.parts if part.source_root.parent.name == "rpg_maker_mv"
            and part.gender == "Male"]
    body = next(part for part in core if part.category == "body" and part.part_number == 1)
    hair = next(part for part in core if part.category == "hair_front" and part.part_number == 1)
    generator = CharacterBundleGenerator(catalog)
    base = CharacterRecipe("base", parts={"body": body.id, "hair_front": hair.id}, body_family="Male")
    blue = CharacterRecipe("blue", parts=base.parts.copy(), palette={"hair_front": "#3050c0"}, body_family="Male")

    before = generator.compose("face", base)
    after = generator.compose("face", blue)

    assert before.getpixel((70, 30)) != after.getpixel((70, 30))
    assert before.getpixel((100, 95)) == after.getpixel((100, 95))


def _png(path, size=(144, 192), rgba=(255, 0, 0, 255)):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", size, rgba).save(path)
    return path


def _catalog(tmp_path, *, face=True, bad_side=False, masks=True):
    root = tmp_path / "Generator"
    walk = _png(root / "TV.png")
    side = _png(root / "SV.png", (100, 100) if bad_side else (576, 384))
    portrait = _png(root / "FG.png", (144, 144))
    damaged = _png(root / "TVD.png", (144, 48))
    walk_mask = _png(root / "TV_c.png", rgba=(0, 0, 0, 0))
    side_mask = _png(root / "SV_c.png", (576, 384), (0, 0, 0, 0))
    part = MVGeneratorPart(
        "mvgen.test.body", root, "Male", "Body", "body", 1,
        walking=MVGeneratorRepresentation("walking", (walk,), (walk_mask,) if masks else ()),
        face=MVGeneratorRepresentation("face", (portrait,)) if face else None,
        damaged=MVGeneratorRepresentation("damaged", (damaged,)),
        side_view=MVGeneratorRepresentation("side_view", (side,), (side_mask,) if masks else ()),
    )
    return RPGMakerMVGeneratorCatalog((root,), (part,), (), 6), part


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


def test_representation_specific_face_feature_does_not_invalidate_walking_or_side_view(tmp_path):
    catalog, body = _catalog(tmp_path / "source")
    face_path = _png(tmp_path / "source" / "Generator" / "eyes.png", (144, 144), (0, 0, 255, 255))
    eyes = MVGeneratorPart(
        "mvgen.test.eyes", body.source_root, "Male", "Eyes", "eyes", 1,
        face=MVGeneratorRepresentation("face", (face_path,)),
    )
    catalog = RPGMakerMVGeneratorCatalog(catalog.roots, (body, eyes), (), catalog.source_file_count + 1)
    recipe = CharacterRecipe("complete", parts={"body": body.id, "eyes": eyes.id})

    bundle = CharacterBundleGenerator(catalog).generate(recipe, tmp_path / "generated")

    assert bundle.walking_path.is_file() and bundle.face_path.is_file() and bundle.side_view_path.is_file()
    assert Image.open(bundle.face_path).getpixel((10, 10))[:3] == (0, 0, 255)
