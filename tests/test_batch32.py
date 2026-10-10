from asteria.presentation import FrameTiming, HighFidelityClip, HighFidelityEditorModel, SyncCue, VisualLayer


def M():
    c = HighFidelityClip(
        "hero", (512, 768), ("a", "b", "c"), (FrameTiming(10),), pivot=(256, 700), layers=(VisualLayer("weapon", 2),)
    )
    return HighFidelityEditorModel(c, (SyncCue(10, "audio", "play", {"id": "s"}),))


def test_sections():
    m = M()
    [m.set_section(x) for x in m.SECTIONS]
    assert m.view.section == "performance"


def test_bad_section():
    import pytest

    m = M()
    pytest.raises(ValueError, m.set_section, "everything")


def test_expand_uniform_timing():
    m = M()
    m.set_frame_duration(1, 77)
    assert [x.duration_ms for x in m.clip.timings] == [10, 77, 10]


def test_layer_add():
    m = M()
    m.add_layer(VisualLayer("glow", 5, "add", 0.5, "emissive"))
    assert len(m.clip.layers) == 2


def test_layer_update():
    m = M()
    m.update_layer(0, blend_mode="add", material="metal")
    assert m.clip.layers[0].material == "metal"


def test_layer_remove():
    m = M()
    m.remove_layer(0)
    assert not m.clip.layers


def test_cues():
    m = M()
    m.add_cue(SyncCue(5, "camera", "shake", {}))
    assert [x.time_ms for x in m.cues] == [5, 10]


def test_filter():
    m = M()
    m.add_layer(VisualLayer("magic_glow", 9, "add", 1, "emissive"))
    m.view.search = "glow"
    assert len(m.filtered_layers()) == 1


def test_inspector_progressive():
    m = M()
    m.set_section("animation")
    assert "frame_size" in m.inspector()
    m.set_section("events")
    assert "cues" in m.inspector()


def test_perf():
    m = M()
    m.set_section("performance")
    assert m.inspector().layer_count == 2


def test_undo_redo():
    m = M()
    m.add_layer(VisualLayer("x"))
    assert m.undo() and len(m.clip.layers) == 1
    assert m.redo() and len(m.clip.layers) == 2


def test_view_state_noncanonical():
    m = M()
    before = m.clip
    m.view.show_advanced = True
    m.view.search = "weapon"
    assert m.clip is before


def test_arbitrary_resolution_preserved():
    m = M()
    m.add_layer(VisualLayer("x"))
    assert m.clip.frame_size == (512, 768)


def test_arbitrary_channel():
    m = M()
    m.add_cue(SyncCue(3, "project.weather", "refract", {}))
    assert m.cues[0].channel == "project.weather"


def test_many_layers_search():
    m = M()
    [m.add_layer(VisualLayer(f"fx{i}", i)) for i in range(500)]
    m.view.search = "fx499"
    assert len(m.filtered_layers()) == 1
