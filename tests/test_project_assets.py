from asteria.assets import AssetRecord
from asteria.core import ComponentRegistry, Entity, Scene, Transform
from asteria.project import Project


def test_project_v2_contains_assets_and_components():
    p = Project("Reference")
    s = p.add_scene(Scene("Town"))
    e = s.add_entity(Entity("Hero"))
    e.add_component(Transform(1.0, 2.0))
    p.assets.add(AssetRecord.create(kind="texture", source_path="assets/hero.png"))
    d = p.to_data()
    r = ComponentRegistry()
    r.register(Transform)
    p2 = Project.from_data(d, r)
    assert len(p2.assets.records()) == 1
    assert p2.scenes()[0].entities()[0].get(Transform).x == 1.0
