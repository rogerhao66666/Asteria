from pathlib import Path

from asteria.editor import EditorDocument
from asteria.project import Project

here = Path(__file__).resolve().parent
document = EditorDocument()
project = Project.load_json(here / "project.asteria.json", document.component_registry)
project.validate()
db = project.rpg_database
print(
    {
        "project": project.name,
        "actors": len(db.actors),
        "jobs": len(db.classes),
        "abilities": len(project.gameplay_library.abilities.ids()),
        "equipment": len(db.equipment),
        "boss_encounter": "boss_room" in db.encounters,
        "startup_scene": project.scene(project.startup_scene_id).name,
    }
)
