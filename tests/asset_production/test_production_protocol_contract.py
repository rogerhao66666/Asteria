from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_skill_v2_has_deterministic_control_contract():
    text = read(".agents/skills/asteria-asset-production/SKILL.md")
    required = [
        "AnimationProductionPlan",
        "Master Reference",
        "Source Integrity",
        "Technical",
        "Cross-animation",
        "Visual Continuity",
        "Motion Readability",
        "Character Identity",
        "Assistant Art/Motion Review",
        "Technical PASS alone is never final",
    ]
    for marker in required:
        assert marker in text


def test_pipeline_places_source_integrity_before_canonicalization():
    text = read("docs/spec/ASTERIA_ASSET_PIPELINE.md")
    section = text[text.index("# 37. Deterministic animation production control") :]
    assert section.index("Source Integrity") < section.index("canonicalization + stabilization")
    assert "generation provider must not silently invent or replace these semantics" in section


def test_canonical_docs_share_production_control_invariant():
    for rel in [
        "docs/spec/ASTERIA_ASSET_SPEC.md",
        "docs/spec/ASTERIA_ART_DIRECTION.md",
        "docs/history/ASTERIA_PROGRESS.md",
    ]:
        text = read(rel)
        assert "Master Reference" in text
    assert "starter defaults/examples" in read("docs/spec/ASTERIA_ASSET_SPEC.md")
    assert "temporal playback" in read("docs/spec/ASTERIA_ART_DIRECTION.md")
