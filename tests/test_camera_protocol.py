from asteria.editor.viewport import ViewportCamera


def test_viewport_camera_supports_shared_render_transform_protocol():
    c = ViewportCamera(10, 20, 2)
    assert c.world_to_screen(5, 7) == (20, 34)
    assert c.world_to_screen(5, 7, 0.5, 0.25, 3) == (15, 13)
