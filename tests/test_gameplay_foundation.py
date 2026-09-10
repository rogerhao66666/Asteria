from asteria.authoring import AuthoringSession
from asteria.core import (
    ComponentRegistry,
    Entity,
    Scene,
    deserialize_scene,
    serialize_scene,
)
from asteria.gameplay import (
    GameplayAttributesComponent,
    ResourcePool,
    ResourceValue,
    StatBlock,
    TagSet,
)
from asteria.project import Project


def test_stat_block_is_generic_and_serializable():
    stats = StatBlock({"power": 10, "speed": 2.5})
    assert stats.get("power") == 10
    assert stats.add("power", 3) == 13
    data = stats.to_data()
    restored = StatBlock.from_data(data)
    assert restored.require("power") == 13
    assert restored.require("speed") == 2.5


def test_resource_pool_clamps_and_spends_atomically():
    pool = ResourcePool()
    pool.define("energy", 100, current=40)
    assert pool.restore("energy", 80) == 100
    assert pool.spend("energy", 30)
    assert pool.current("energy") == 70
    assert not pool.spend("energy", 80)
    assert pool.current("energy") == 70


def test_resource_maximum_can_preserve_ratio():
    value = ResourceValue(50, 100)
    value.set_maximum(200, preserve_ratio=True)
    assert value.current == 100
    assert value.normalized == 0.5


def test_tag_set_normalizes_and_queries():
    tags = TagSet(["Enemy.Boss", "Element.Fire"])
    assert tags.contains("enemy.boss")
    assert tags.contains_all(["enemy.boss", "element.fire"])
    assert tags.contains_any(["missing", "element.fire"])
    assert tags.values() == ("element.fire", "enemy.boss")


def test_gameplay_component_roundtrips_through_scene_serialization():
    registry = ComponentRegistry()
    registry.register(GameplayAttributesComponent)

    scene = Scene("Arena")
    entity = scene.add_entity(Entity("Unit"))
    component = entity.add_component(GameplayAttributesComponent())

    stats = StatBlock({"power": 12})
    resources = ResourcePool()
    resources.define("hp", 100, current=75)
    tags = TagSet(["actor.player"])

    component.set_stat_block(stats)
    component.set_resource_pool(resources)
    component.set_tag_set(tags)

    restored = deserialize_scene(serialize_scene(scene), registry)
    restored_component = restored.entities()[0].get(GameplayAttributesComponent)

    assert restored_component.stat_block().require("power") == 12
    assert restored_component.resource_pool().current("hp") == 75
    assert restored_component.tag_set().contains("actor.player")


def test_python_authoring_can_create_and_edit_gameplay_attributes():
    project = Project("Demo")
    scene = project.add_scene(Scene("Town"))
    hero = scene.add_entity(Entity("Hero"))

    api = AuthoringSession(project)
    gameplay = api.scene("Town").entity("Hero").gameplay

    gameplay.set_stat("power", 15)
    gameplay.add_stat("power", 5)
    gameplay.define_resource("hp", 100, current=60)
    assert gameplay.spend_resource("hp", 20)
    gameplay.add_tag("actor.player")

    component = hero.get(GameplayAttributesComponent)
    assert component.stats["power"] == 20
    assert component.resources["hp"]["current"] == 40
    assert component.tags == ["actor.player"]


def test_gameplay_is_not_rpg_name_hardcoded():
    stats = StatBlock({"temperature": 300, "combo_meter": 7})
    pool = ResourcePool()
    pool.define("guard", 50)
    tags = TagSet(["machine", "state.overheated"])
    assert stats.require("temperature") == 300
    assert pool.maximum("guard") == 50
    assert tags.contains("machine")
