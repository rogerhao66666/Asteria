from dataclasses import dataclass
from pathlib import Path

from asteria.project import Project
from asteria.runtime.game_save import GameRuntimeSave


class PlayModeError(RuntimeError):
    pass


@dataclass(slots=True)
class PlaySession:
    source_project_id: str
    source_scene_id: str
    runtime_project: Project
    resource_root: Path | None = None
    active: bool = True
    runtime_save: GameRuntimeSave | None = None
    playtest_profile_id: str | None = None

    @property
    def runtime_scene(self):
        return self.runtime_project.scene(self.source_scene_id)

    def stop(self):
        self.active = False


def resolve_play_scene(document):
    if document.project is None:
        raise PlayModeError("No project is open")
    sel = document.selection
    if sel.kind == "scene" and not sel.multiple and sel.value is not None:
        return sel.value
    if sel.kind == "entity" and sel.value is not None and getattr(sel.value, "scene", None) is not None:
        return sel.value.scene
    if sel.kind == "component" and sel.value is not None:
        entity = getattr(sel.value, "entity", None)
        if entity is not None and getattr(entity, "scene", None) is not None:
            return entity.scene
    scene = document.project.scene(document.project.startup_scene_id)
    if scene is None:
        raise PlayModeError("Project has no valid startup scene")
    return scene


def create_play_session(document, *, runtime_save=None, playtest_profile_id=None, from_start=False):
    """Clone project data into a runtime snapshot.

    Runtime mutations during play cannot mutate the editor's canonical project.
    This is deliberately backend-neutral; launching a pygame/native runtime is
    a later adapter concern.
    """
    scene = (
        document.project.scene(document.project.startup_scene_id)
        if from_start and document.project is not None
        else resolve_play_scene(document)
    )
    snapshot = Project.from_data(document.project.to_data(), document.component_registry)
    if snapshot.scene(scene.id) is None:
        raise PlayModeError("Selected scene was not present in runtime snapshot")
    if runtime_save is None and from_start:
        runtime_save = snapshot.game_start.instantiate(snapshot)
    if runtime_save is not None:
        if isinstance(runtime_save, dict):
            runtime_save = GameRuntimeSave.from_data(runtime_save, snapshot)
        runtime_save.validate(snapshot)
        source_scene_id = runtime_save.scene_id
    else:
        source_scene_id = scene.id
    return PlaySession(
        source_project_id=document.project.id,
        source_scene_id=source_scene_id,
        runtime_project=snapshot,
        resource_root=(document.file_path.resolve().parent if document.file_path is not None else None),
        runtime_save=runtime_save,
        playtest_profile_id=None if playtest_profile_id is None else str(playtest_profile_id),
    )
