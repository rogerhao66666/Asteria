from asteria.presentation.render_backend import *
from asteria.presentation.render_integration import *
from asteria.presentation.text_render_integration import TextRenderPacket


class B:
    def __init__(self):
        self.events = []

    def begin_frame(self, i):
        self.events.append(("begin", i))

    def resolve_visual(self, a):
        self.events.append(("rv", a))
        return "V:" + a

    def draw_visual(self, r, p):
        self.events.append(("dv", r, p.transform.flip_x, p.transform.rotation_deg))

    def resolve_font(self, a):
        self.events.append(("rf", a))
        return "F:" + str(a)

    def draw_text(self, r, p):
        self.events.append(("dt", r, p.text))

    def end_frame(self):
        self.events.append(("end",))


def T(i="t", z=0, font="font"):
    return TextRenderPacket(i, "hello", "screen", 0, 0, 1, 0, 1, z, font, None, None, None, {})


def test_backend_executes_canonical_transform_without_losing_flip_rotation():
    b = B()
    e = PresentationBackendExecutor(b)
    p = DrawPacket("hero", RenderTransform(rotation_deg=37, flip_x=True), 0)
    e.execute(1, [p])
    assert ("dv", "V:hero", True, 37) in b.events


def test_stable_asset_resolution_cached_across_frames():
    b = B()
    e = PresentationBackendExecutor(b)
    p = DrawPacket("hero", RenderTransform())
    a = e.execute(1, [p])
    c = e.execute(2, [p])
    assert a.visual_resolves == 1 and c.visual_resolves == 0
    assert b.events.count(("rv", "hero")) == 1


def test_invalidation_for_hot_reload_re_resolves():
    b = B()
    e = PresentationBackendExecutor(b)
    p = DrawPacket("hero", RenderTransform())
    e.execute(1, [p])
    e.invalidate("hero")
    e.execute(2, [p])
    assert b.events.count(("rv", "hero")) == 2


def test_text_font_resolution_and_draw():
    b = B()
    e = PresentationBackendExecutor(b)
    s = e.execute(1, texts=[T()])
    assert s.font_resolves == 1 and ("dt", "F:font", "hello") in b.events


def test_deterministic_visual_order():
    b = B()
    e = PresentationBackendExecutor(b)
    e.execute(1, [DrawPacket("b", RenderTransform(), 2), DrawPacket("a", RenderTransform(), 1)])
    assert [x[1] for x in b.events if x[0] == "rv"] == ["a", "b"]


def test_hidden_and_zero_opacity_not_drawn():
    b = B()
    e = PresentationBackendExecutor(b)
    e.execute(1, [DrawPacket("a", RenderTransform(visible=False)), DrawPacket("b", RenderTransform(opacity=0))])
    assert not any(x[0] == "dv" for x in b.events)


def test_end_frame_even_when_backend_raises():
    class Bad(B):
        def draw_visual(self, r, p):
            raise RuntimeError("gpu")

    b = Bad()
    e = PresentationBackendExecutor(b)
    try:
        e.execute(1, [DrawPacket("a", RenderTransform())])
    except RuntimeError:
        pass
    assert b.events[-1] == ("end",)


def test_clear_resources_for_project_close():
    b = B()
    e = PresentationBackendExecutor(b)
    p = DrawPacket("a", RenderTransform())
    e.execute(1, [p])
    e.clear_resources()
    e.execute(2, [p])
    assert b.events.count(("rv", "a")) == 2
