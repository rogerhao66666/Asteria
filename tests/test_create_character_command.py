from pathlib import Path
from dataclasses import replace

import pytest
from PIL import Image

from asteria.assets.canonical import AssetSource, CanonicalAsset
from asteria.assets.character_bundle import GeneratedCharacterBundle
from asteria.core import Entity, Scene, Transform
from asteria.editor.create_character_command import CreateCharacterCommand
from asteria.editor.character_generator_workspace import CharacterGeneratorWorkspace
from asteria.project import Project
from asteria.rpg import ActorDefinition
from asteria.runtime import AnimationClipSet, Animator2DComponent, SpriteRenderer2D
from asteria.assets.rpg_maker_mv_generator import RPGMakerMVGeneratorCatalog


def _bundle(tmp_path):
    output = tmp_path / "generated" / "hero-one"
    output.mkdir(parents=True)
    paths = {}
    for name, size in (("walking", (144, 192)), ("face", (144, 144)), ("side_view", (576, 384))):
        path = output / f"{name}.png"
        Image.new("RGBA", size, (10, 20, 30, 0)).save(path)
        paths[name] = path
    metadata = output / "character.bundle.json"
    metadata.write_text('{"schema":"asteria.character.bundle.v1"}', encoding="utf-8")
    assets = tuple(
        CanonicalAsset(f"generated/hero-one/{name}", f"character.{name}", AssetSource(str(paths[name]), "generated"))
        for name in ("walking", "face", "side_view")
    )
    return GeneratedCharacterBundle(
        "hero-one",
        output,
        paths["walking"],
        paths["face"],
        paths["side_view"],
        metadata,
        (24, 48),
        ("mvgen.source",),
        assets,
    )


def _world(tmp_path):
    project = Project("Test")
    scene = project.add_scene(Scene("Map"))
    bundle = _bundle(tmp_path)
    return project, scene, bundle


def test_execute_creates_actor_assets_clips_and_cell_aligned_entity(tmp_path):
    project, scene, bundle = _world(tmp_path)
    command = CreateCharacterCommand(bundle, project, scene, (2, 3), display_name="Hero One")

    created = command.execute()

    assert isinstance(created.actor, ActorDefinition)
    assert project.rpg_database.actors[created.actor_id] is created.actor
    assert len(project.assets.snapshot()) == 3
    assert tuple(asset.asset_id for asset in created.assets) == tuple(
        asset.asset_id for asset in bundle.canonical_assets
    )
    assert isinstance(created.clip_set, AnimationClipSet)
    assert tuple(created.clip_set.clips) == (
        "idle_down",
        "walk_down",
        "idle_left",
        "walk_left",
        "idle_right",
        "walk_right",
        "idle_up",
        "walk_up",
    )
    for row, direction in enumerate(("down", "left", "right", "up")):
        assert [frame.frame_index for frame in created.clip_set.get(f"walk_{direction}").keyframes] == [
            row * 3 + pattern for pattern in (1, 2, 1, 0)
        ]
    assert scene.get_entity(created.entity_id) is created.entity
    transform = created.entity.get(Transform)
    assert (transform.x, transform.y) == (120.0, 192.0)
    assert created.entity.get(SpriteRenderer2D).sprite_sheet_asset_id == "generated/hero-one/walking"
    animator = created.entity.get(Animator2DComponent)
    assert animator.clip_set_id == created.clip_set_id
    assert animator.default_clip == "idle_down"


def test_undo_and_redo_restore_identical_ids_and_only_owned_files(tmp_path):
    project, scene, bundle = _world(tmp_path)
    sentinel = bundle.output_dir / "keep.txt"
    sentinel.write_text("pre-existing", encoding="utf-8")
    command = CreateCharacterCommand(bundle, project, scene, (0, 0))
    first = command.execute()
    ids = (first.actor_id, first.entity_id, first.clip_set_id)

    command.undo()

    assert first.actor_id not in project.rpg_database.actors
    assert scene.get_entity(first.entity_id) is None
    assert not any(path.exists() for path in bundle.visual_paths + (bundle.metadata_path,))
    assert sentinel.read_text(encoding="utf-8") == "pre-existing"
    assert project.assets.snapshot() == ()

    second = command.redo()
    assert (second.actor_id, second.entity_id, second.clip_set_id) == ids
    assert all(path.exists() for path in bundle.visual_paths + (bundle.metadata_path,))
    assert sentinel.exists()


def test_undo_removes_owned_damaged_sheet_and_redo_restores_it(tmp_path):
    project, scene, bundle = _world(tmp_path)
    damaged = bundle.output_dir / "damaged.png"
    Image.new("RGBA", (144, 48), (0, 0, 0, 0)).save(damaged)
    asset = CanonicalAsset("generated/hero-one/damaged", "character.damaged", AssetSource(str(damaged), "generated"))
    bundle = replace(bundle, damaged_path=damaged, canonical_assets=bundle.canonical_assets + (asset,))
    command = CreateCharacterCommand(bundle, project, scene, (0, 0))

    command.execute()
    command.undo()
    assert not damaged.exists()
    command.redo()
    assert damaged.is_file()


def test_workspace_builds_scene_creation_command_from_generated_bundle(tmp_path):
    project, scene, bundle = _world(tmp_path)
    workspace = CharacterGeneratorWorkspace.create_mv(RPGMakerMVGeneratorCatalog((), (), (), 0), "hero-one")

    command = workspace.create_character_command(bundle, project, scene, (4, 5), display_name="Hero")

    assert isinstance(command, CreateCharacterCommand)
    created = command.execute()
    assert (created.entity.get(Transform).x, created.entity.get(Transform).y) == (216.0, 288.0)


@pytest.mark.parametrize("boundary", ["files", "assets", "actor", "entity"])
def test_failure_at_each_boundary_rolls_back_without_touching_preexisting_state(tmp_path, boundary):
    project, scene, bundle = _world(tmp_path)
    existing_asset = CanonicalAsset("existing/asset", "icon", AssetSource("existing.png"))
    project.assets.register(existing_asset)
    existing_actor = project.rpg_database.add_actor(ActorDefinition("existing.actor", "Existing"))
    existing_entity = scene.add_entity(Entity("Existing"))
    sentinel = bundle.output_dir / "keep.txt"
    sentinel.write_text("keep", encoding="utf-8")

    def fail(stage):
        if stage == boundary:
            raise RuntimeError(f"injected at {stage}")

    command = CreateCharacterCommand(bundle, project, scene, (1, 1), failure_injector=fail)
    with pytest.raises(RuntimeError, match=f"injected at {boundary}"):
        command.execute()

    assert project.assets.snapshot() == (existing_asset,)
    assert project.rpg_database.actors == {existing_actor.actor_id: existing_actor}
    assert scene.entities() == (existing_entity,)
    assert sentinel.read_text(encoding="utf-8") == "keep"
    assert not any(path.exists() for path in bundle.visual_paths + (bundle.metadata_path,))
