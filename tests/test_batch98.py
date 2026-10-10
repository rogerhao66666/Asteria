from asteria.presentation.render_batching import ResourceLifetimeCache, compatible_batches
from asteria.presentation.render_integration import DrawPacket, RenderTransform


def p(asset, z=0, owner="", component=""):
    return DrawPacket(asset, RenderTransform(), z, owner, component)


def test_adjacent_compatible_packets_batch():
    b = compatible_batches([p("a", 0, "x", "1"), p("a", 0, "x", "2"), p("b", 1)])
    assert [len(x.packets) for x in b] == [2, 1]


def test_batching_never_crosses_incompatible_layer():
    b = compatible_batches([p("a", 0, "x", "1"), p("b", 0, "x", "2"), p("a", 0, "x", "3")])
    assert [x.key[0] for x in b] == ["a", "b", "a"]


def test_material_participates_in_compatibility_key():
    ps = [p("a", 0, "x", "1"), p("a", 0, "x", "2")]
    mats = {"1": "m1", "2": "m2"}
    assert len(compatible_batches(ps, lambda x: mats[x.component_id])) == 2


def test_hidden_and_transparent_packets_do_not_submit():
    hidden = DrawPacket("a", RenderTransform(visible=False))
    clear = DrawPacket("b", RenderTransform(opacity=0))
    assert compatible_batches([hidden, clear]) == ()


def test_resource_cache_resolves_once_and_releases_on_invalidate():
    resolved = []
    released = []
    c = ResourceLifetimeCache(lambda x: resolved.append(x) or "R" + x, released.append)
    assert c.get("a") == c.get("a") == "Ra" and resolved == ["a"]
    c.invalidate("a")
    assert released == ["Ra"] and len(c) == 0


def test_resource_clear_is_deterministic_and_complete():
    released = []
    c = ResourceLifetimeCache(lambda x: "R" + x, released.append)
    c.get("b")
    c.get("a")
    c.clear()
    assert released == ["Ra", "Rb"] and len(c) == 0


def test_reconcile_after_invalidation_resolves_fresh_handle():
    n = [0]
    released = []

    def resolve(x):
        n[0] += 1
        return (x, n[0])

    c = ResourceLifetimeCache(resolve, released.append)
    old = c.get("asset")
    c.invalidate("asset")
    new = c.get("asset")
    assert old != new and released == [old]
