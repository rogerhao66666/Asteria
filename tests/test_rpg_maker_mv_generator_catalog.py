from pathlib import Path

from asteria.assets.local_reference import resolve_rpg_maker_mv_root
from asteria.assets.rpg_maker_mv_generator import RPGMakerMVGeneratorCatalog


def _real():
    repo = Path(__file__).resolve().parents[1]
    return RPGMakerMVGeneratorCatalog.discover(resolve_rpg_maker_mv_root(repo))


def test_real_catalog_discovers_every_generator_source_file_deterministically():
    first = _real()
    second = _real()

    assert len(first.roots) == 5
    assert first.source_file_count >= 3422
    assert first.parts == second.parts
    assert tuple(part.id for part in first.parts) == tuple(sorted(part.id for part in first.parts))


def test_representative_part_links_walking_face_side_view_thumbnail_and_masks():
    catalog = _real()
    part = next(
        item for item in catalog.parts
        if item.source_category == "AccA" and item.part_number == 14
        and item.gender == "Male" and "Modern_Generator/parts" in item.source_root.as_posix()
    )

    assert part.category == "accessory"
    assert part.walking is not None and part.walking.images
    assert part.face is not None and len(part.face.images) == 3
    assert part.side_view is not None and part.side_view.images
    assert part.thumbnail is not None and part.thumbnail.images[0].name == "icon_AccA_p14.png"
    assert part.walking.masks and part.side_view.masks
    assert part.layer_order["walking"] < part.layer_order["face"]


def test_body_gender_variation_and_generic_translation_are_retained():
    catalog = _real()
    body = next(item for item in catalog.parts if item.source_category == "Body" and item.gender == "Female")

    assert body.category == "body"
    assert body.part_number == 1
    assert "gender:female" in body.tags
    generic = {part.id: part for part in catalog.to_character_parts()}
    assert body.id in generic
    assert generic[body.id].category == "body"


def test_malformed_part_does_not_hide_valid_sibling(tmp_path):
    generator = tmp_path / "Pack" / "Generator" / "TV" / "Male"
    generator.mkdir(parents=True)
    (generator / "TV_Body_p01.png").write_bytes(b"png")
    (generator / "not-a-generator-name.png").write_bytes(b"bad")

    catalog = RPGMakerMVGeneratorCatalog.discover(tmp_path)

    assert len(catalog.parts) == 1
    assert catalog.parts[0].source_category == "Body"
    assert any(issue.code == "generator.unrecognized_name" for issue in catalog.issues)


def test_missing_representations_are_explicit_not_substituted():
    catalog = _real()
    body = next(
        item for item in catalog.parts
        if item.source_category == "Body" and "modern_body" in item.source_root.as_posix()
    )

    assert body.walking is not None
    assert body.face is None
    assert body.side_view is None
    assert any(issue.code == "generator.representation_missing" and issue.part_id == body.id
               for issue in catalog.issues)


def test_core_generator_merges_case_and_numbered_filename_layers_into_logical_parts():
    catalog = _real()
    core = next(
        item for item in catalog.parts
        if item.source_root.parent.name == "rpg_maker_mv"
        and item.source_category == "Body" and item.part_number == 1 and item.gender == "Male"
    )
    clothing = next(
        item for item in catalog.parts
        if item.source_root.parent.name == "rpg_maker_mv"
        and item.source_category == "Clothing" and item.part_number == 1 and item.gender == "Male"
    )

    assert core.walking is not None and core.face is not None and core.side_view is not None
    assert clothing.walking is not None and len(clothing.walking.images) >= 2
    assert clothing.face is not None and clothing.side_view is not None


def test_core_face_features_translate_to_independent_generic_categories():
    catalog = _real()
    core_parts = [part for part in catalog.parts if part.source_root.parent.name == "rpg_maker_mv" and part.gender == "Male"]

    assert next(part for part in core_parts if part.source_category == "Face").category == "face_shape"
    assert next(part for part in core_parts if part.source_category == "Eyebrows").category == "eyebrows"
    assert next(part for part in core_parts if part.source_category == "Nose").category == "nose"
    assert next(part for part in core_parts if part.source_category == "Mouth").category == "mouth"
    assert next(part for part in core_parts if part.source_category == "FacialMark").category == "facial_mark"


def test_mv_generator_keeps_interchangeable_face_and_clothing_slots_distinct():
    catalog = _real()
    core = [part for part in catalog.parts if part.source_root.parent.name == "rpg_maker_mv" and part.gender == "Male"]
    categories = {part.source_category: part.category for part in core}

    assert categories["Eyes"] == "eyes"
    assert categories["Eyebrows"] == "eyebrows"
    assert categories["Cloak"] == "cloak"
    assert categories["Clothing"] == "outfit"
    assert categories["AccA"] == "accessory"
    assert categories["AccB"] == "accessory_b"
    assert categories["Glasses"] == "glasses"
    assert categories["Beard"] == "beard"
    assert categories["Ears"] == "ears"
    assert categories["BeastEars"] == "beast_ears"
    assert {part.gender for part in catalog.parts if part.source_category == "Body"} >= {"Male", "Female", "Kid"}
