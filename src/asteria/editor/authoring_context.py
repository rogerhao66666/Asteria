from asteria.runtime import Animator2DComponent

from .scene_render import render_source_for_scene
from .viewport import selected_scene


def scene_authoring_source(document):
    return render_source_for_scene(document, selected_scene(document))


def animation_context(document):
    """Return (clip_set, default_clip) for the selected animated entity/component."""
    sel = document.selection
    entity = None
    if sel.kind == "entity" and not sel.multiple:
        entity = sel.value
    elif sel.kind == "component" and not sel.multiple and sel.value is not None:
        entity = getattr(sel.value, "entity", None)
        if entity is None:
            scene = selected_scene(document)
            if scene is not None:
                for candidate in scene.entities():
                    if sel.value in candidate.components():
                        entity = candidate
                        break

    animator = entity.try_get(Animator2DComponent) if entity is not None else None
    if animator is None or not animator.clip_set_id:
        return None, None

    clip_set = document.asset_views.clip_set(animator.clip_set_id)
    if clip_set is None:
        return None, animator.default_clip

    names = tuple(clip_set.clips)
    current = (
        animator.default_clip
        if animator.default_clip in names
        else (names[0] if names else None)
    )
    return clip_set, current
