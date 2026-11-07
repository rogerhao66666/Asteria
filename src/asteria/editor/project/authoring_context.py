from asteria.editor.scene.render import render_source_for_scene
from asteria.editor.scene.viewport import selected_scene


def scene_authoring_source(document):
    return render_source_for_scene(document, selected_scene(document))
