import json
from pathlib import Path

from asteria.assets import (
    AssetCodecRegistry,
    AssetRegistry,
    AssetSource,
    AssetStore,
    CanonicalAsset,
    IconAsset,
    ValidationIssue,
    ValidationReport,
    install_common_passthrough_codecs,
    install_complex_typed_codecs,
    install_simple_typed_codecs,
    passthrough_codec,
)


def C():
    r = install_common_passthrough_codecs(AssetCodecRegistry())
    return install_complex_typed_codecs(install_simple_typed_codecs(r))


def W(root, name, kind="audio", deps=(), payload=None, aid=None):
    p = Path(root) / f"{name}.asset.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    d = {
        "schema_version": 1,
        "asset_id": aid or name,
        "kind": kind,
        "source": f"{name}.dat",
        "dependencies": list(deps),
        "payload": payload or {"uri": f"{name}.ogg"},
    }
    p.write_text(json.dumps(d))
    return p


def test_load(tmp_path):
    W(tmp_path, "a")
    s = AssetStore(C())
    r = s.load(tmp_path)
    assert r.ok and s.registry.resolve("a")


def test_order(tmp_path):
    W(tmp_path, "b", deps=("a",))
    W(tmp_path, "a")
    r = AssetStore(C()).load(tmp_path)
    assert [x.manifest.asset_id for x in r.loaded] == ["a", "b"]


def test_missing_atomic(tmp_path):
    W(tmp_path, "a", deps=("x",))
    W(tmp_path, "b")
    s = AssetStore(C())
    assert not s.load(tmp_path).ok and not s.registry.snapshot()


def test_cycle(tmp_path):
    W(tmp_path, "a", deps=("b",))
    W(tmp_path, "b", deps=("a",))
    r = AssetStore(C()).load(tmp_path)
    assert any(x.code == "asset.dependency.cycle" for x in r.issues)


def test_bad_json(tmp_path):
    (tmp_path / "x.asset.json").write_text("{bad")
    assert AssetStore(C()).load(tmp_path).issues[0].code == "asset.document.invalid_json"


def test_not_object(tmp_path):
    (tmp_path / "x.asset.json").write_text("[]")
    assert AssetStore(C()).load(tmp_path).issues[0].code == "asset.document.not_object"


def test_bad_manifest(tmp_path):
    (tmp_path / "x.asset.json").write_text('{"kind":"audio"}')
    assert AssetStore(C()).load(tmp_path).issues[0].code == "asset.manifest.invalid"


def test_duplicate(tmp_path):
    W(tmp_path / "x", "a", aid="same")
    W(tmp_path / "y", "b", aid="same")
    s = AssetStore(C())
    assert not s.load(tmp_path).ok and not s.registry.snapshot()


def test_unknown_kind(tmp_path):
    W(tmp_path, "a", kind="project.nope", payload={"x": 1})
    assert any(x.code == "asset.decode.failed" for x in AssetStore(C()).load(tmp_path).issues)


def test_custom_kind(tmp_path):
    c = C()
    c.register(passthrough_codec("project.custom"))
    W(tmp_path, "a", kind="project.custom", payload={"x": 1})
    assert AssetStore(c).load(tmp_path).ok


def test_existing_dep(tmp_path):
    reg = AssetRegistry()
    reg.register(CanonicalAsset("ext", "audio", AssetSource("x")))
    W(tmp_path, "a", deps=("ext",))
    assert AssetStore(C(), reg).load(tmp_path).ok


def test_conflict_atomic(tmp_path):
    reg = AssetRegistry()
    reg.register(CanonicalAsset("a", "audio", AssetSource("x")))
    W(tmp_path, "a")
    W(tmp_path, "b")
    r = AssetStore(C(), reg).load(tmp_path)
    assert not r.ok and len(reg.snapshot()) == 1


def test_warning(tmp_path):
    W(tmp_path, "a")

    def v(a):
        return ValidationReport(a.canonical.asset_id, (ValidationIssue("w", "review", "warning"),))

    r = AssetStore(C(), validators={"audio": v}).load(tmp_path)
    assert r.ok and r.issues[0].severity == "warning"


def test_error_atomic(tmp_path):
    W(tmp_path, "a")

    def v(a):
        return ValidationReport(a.canonical.asset_id, (ValidationIssue("e", "bad"),))

    s = AssetStore(C(), validators={"audio": v})
    assert not s.load(tmp_path).ok and not s.registry.snapshot()


def test_typed_icon(tmp_path):
    W(
        tmp_path,
        "i",
        kind="icon",
        payload={
            "variants": [{"name": "default", "image_uri": "i.png", "size": [32, 32]}],
            "default_variant": "default",
        },
    )
    assert isinstance(AssetStore(C()).load(tmp_path).loaded[0].asset, IconAsset)


def test_stress_5000(tmp_path):
    for i in range(5000):
        W(tmp_path / "a", str(i), aid=f"audio/{i}")
    s = AssetStore(C())
    r = s.load(tmp_path)
    assert r.ok and len(r.loaded) == 5000
