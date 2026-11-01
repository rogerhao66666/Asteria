from .scene_render import render_source_for_scene
from .viewport import selected_scene


def scene_authoring_source(document):
    return render_source_for_scene(document, selected_scene(document))
