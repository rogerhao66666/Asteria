from asteria.core import Scene

from .commands import AddSceneCommand, RemoveSceneCommand, ReorderSceneCommand


class SceneEditError(ValueError):
    pass


def build_add_scene_command(project, name="Scene"):
    if project is None:
        raise SceneEditError("Project required")
    name = str(name).strip() or "Scene"
    taken = {scene.name for scene in project.scenes()}
    if name in taken:  # "Scene", "Scene 2", "Scene 3"...: every scene keeps a readable name
        number = 2
        while f"{name} {number}" in taken:
            number += 1
        name = f"{name} {number}"
    return AddSceneCommand(project, Scene(name))


def build_remove_scene_command(project, scene):
    if project is None or scene is None:
        raise SceneEditError("Project and scene required")
    if len(project.scenes()) <= 1:
        raise SceneEditError("Project must keep at least one scene")
    return RemoveSceneCommand(project, scene)


def build_reorder_scene_command(project, scene, new_index):
    if project is None or scene is None:
        raise SceneEditError("Project and scene required")
    old = project.scene_index(scene)
    new = max(0, min(int(new_index), len(project.scenes()) - 1))
    return ReorderSceneCommand(project, scene, new, old)
