"""Project templates: starting points a new project is copied from (File > New from Template).

A template is a finished project folder (data, art, manifest). It is copied as it is, so every
setting in it - the battle rules, the combat numbers, the HUD and menus, the maps - is there to
edit instead of being built from nothing. The two templates are the reference projects that
test the engine; nothing in the engine knows them.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SKIP = {"__pycache__", ".DS_Store", "build_project.py", "art.py", "maps.py"}


@dataclass(frozen=True, slots=True)
class ProjectTemplate:
    template_id: str
    title: str
    description: str
    folder: str  # under reference_projects/

    @property
    def source(self):
        return REPO / "reference_projects" / self.folder

    def available(self):
        return (self.source / "project.asteria.json").is_file()


TEMPLATES = (
    ProjectTemplate(
        "party_rpg",
        "Party RPG (Octopath-style)",
        "Turn-based battles with weaknesses and shields, boost points, jobs, a pet, concoction, "
        "statuses and four enemy types; a field map with encounters.",
        "octopath_demo",
    ),
    ProjectTemplate(
        "action_rpg",
        "Action RPG (Diablo-style)",
        "Real-time combat with classes and skill trees, loot with rarities and affixes, a set, "
        "potions, a grid bag, an action bar with cooldowns; a town, a field and a side-view mine.",
        "arpg_demo",
    ),
)


def available_templates():
    return tuple(t for t in TEMPLATES if t.available())


def create_from_template(template_id, name, folder):
    """Copy a template into ``folder`` (created if missing, must be empty) as project ``name``;
    returns the path of the new ``project.asteria.json``."""
    template = next((t for t in TEMPLATES if t.template_id == template_id), None)
    if template is None or not template.available():
        raise ValueError(f"unknown or missing template: {template_id}")
    name = str(name).strip()
    if not name:
        raise ValueError("a project name is required")
    target = Path(folder).expanduser().resolve()
    if target.exists() and any(target.iterdir()):
        raise ValueError(f"{target} is not empty")
    shutil.copytree(
        template.source,
        target,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(*SKIP),
    )
    project_file = target / "project.asteria.json"
    import json

    data = json.loads(project_file.read_text())
    data["name"] = name
    project_file.write_text(json.dumps(data, indent=2))
    return project_file
