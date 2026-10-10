import pytest
from asteria.editor.attachment_authoring import AttachmentAuthoringModel
from asteria.editor.attachment_preview import AttachmentPreviewController
from asteria.presentation.animation_attachment import AnimationClock
from asteria.presentation.attachments import Socket, Attachment, Transform2D


def setup(loop=True):
    m = AttachmentAuthoringModel()
    m.add_socket(Socket("hand"))
    m.attach(Attachment("held", "asset", "hand"))
    return m, AttachmentPreviewController(m, AnimationClock.uniform(3, 10, loop=loop))


def test_seek_time_updates_preview_frame():
    m, p = setup()
    f = p.seek_time(150)
    assert f.sample.frame == 1 and f.sample.subframe == pytest.approx(0.5)


def test_seek_frame_supports_timeline_scrub():
    m, p = setup()
    f = p.seek_frame(2, 0.25)
    assert f.sample.frame == 2 and f.sample.subframe == pytest.approx(0.25)


def test_play_tick_advances():
    m, p = setup()
    p.play()
    assert p.tick(100).sample.frame == 1


def test_pause_freezes():
    m, p = setup()
    p.play()
    p.tick(50)
    p.pause()
    a = p.tick(100)
    b = p.tick(100)
    assert a.sample == b.sample


def test_playback_rate():
    m, p = setup()
    p.set_playback_rate(2)
    p.play()
    assert p.tick(50).sample.frame == 1


def test_nonloop_stops_at_end():
    m, p = setup(False)
    p.play()
    f = p.tick(999)
    assert f.sample.finished and not p.playing


def test_edit_at_playhead_updates_same_preview():
    m, p = setup()
    p.seek_frame(1)
    f = p.edit_socket_key_at_playhead("hand", Transform2D(x=12, y=4))
    assert f.attachments[0].transform.x == 12 and f.attachments[0].transform.y == 4


def test_undo_redo_live_preview():
    m, p = setup()
    p.seek_frame(1)
    p.edit_socket_key_at_playhead("hand", Transform2D(x=9))
    changed, f = p.undo()
    assert changed and f.attachments[0].transform.x == 0
    changed, f = p.redo()
    assert changed and f.attachments[0].transform.x == 9


def test_invalid_seek_and_rate():
    m, p = setup()
    with pytest.raises(ValueError):
        p.seek_time(-1)
    with pytest.raises(IndexError):
        p.seek_frame(99)
    with pytest.raises(ValueError):
        p.seek_frame(0, 2)
    with pytest.raises(ValueError):
        p.set_playback_rate(0)
    with pytest.raises(ValueError):
        p.tick(-1)


def test_editor_preview_uses_runtime_attachment_model():
    m, p = setup()
    assert p.seek_time(0).attachments[0].asset_id == "asset"
