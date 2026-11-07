from asteria.assets import AssetRecord
from asteria.core import Scene
from asteria.editor.project.model import EditorDocument
from asteria.editor.scene.render import resolve_texture_source
from asteria.project import Project


def test_editor_resolves_texture_relative_to_project_file(tmp_path):
    p = Project("P")
    p.add_scene(Scene("S"))
    rec = AssetRecord.create(kind="texture", source_path="assets/town.png")
    p.assets.add(rec)
    doc = EditorDocument(p, file_path=tmp_path / "game.asteria.json")
    assert resolve_texture_source(doc, rec.id) == tmp_path / "assets/town.png"
