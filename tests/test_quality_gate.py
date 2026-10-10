import json
from asteria.assets.quality_gate import PackQualityGate


def put(root, aid, q=None):
    p = root / "x.png"
    p.write_bytes(b"x")
    payload = {"asset_type": "icon"}
    if q is not None:
        payload["quality"] = q
    (root / (aid + ".asset.json")).write_text(json.dumps({"asset_id": aid, "source": "x.png", "payload": payload}))


def allpass():
    return {"technical": "pass", "art": "pass", "motion": "pass", "in_scene": "pass", "notes": ["reviewed"]}


def test_missing_evidence_blocks(tmp_path):
    put(tmp_path, "a")
    r = PackQualityGate().validate(tmp_path)
    assert not r.ok and len(r.issues) == 4


def test_review_required_blocks(tmp_path):
    q = allpass()
    q["art"] = "review_required"
    put(tmp_path, "a", q)
    r = PackQualityGate().validate(tmp_path)
    assert not r.ok and r.issues[0].gate == "art"


def test_fail_blocks(tmp_path):
    q = allpass()
    q["technical"] = "fail"
    put(tmp_path, "a", q)
    assert not PackQualityGate().validate(tmp_path).ok


def test_all_four_pass(tmp_path):
    put(tmp_path, "a", allpass())
    put(tmp_path, "b", allpass())
    r = PackQualityGate().validate(tmp_path)
    assert r.ok and r.assets_checked == 2
