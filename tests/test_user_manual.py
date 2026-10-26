"""The user manual (docs/manual): its API chapter matches the code and every picture exists."""

import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANUAL = ROOT / "docs" / "manual"
IMAGE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")


def _generator():
    spec = importlib.util.spec_from_file_location(
        "manual_api_list", ROOT / "scripts" / "manual_api_list.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _slug(heading):
    return re.sub(r"[^\w\- ]", "", heading.strip().lower()).replace(" ", "-")


def test_api_chapter_matches_the_code():
    generator = _generator()
    for lang, path in generator.MANUALS.items():
        text = path.read_text(encoding="utf-8")
        assert generator.BEGIN in text and generator.END in text, path.name
        assert generator.apply(text, lang) == text, f"{path.name}: run manual_api_list.py"


def test_every_api_target_resolves():
    generator = _generator()
    for section in generator.SECTIONS:
        for target, *_texts in section["items"]:
            assert generator._resolve(target) is not None, target


def test_pictures_exist_and_both_languages_have_the_same_number():
    counts = {}
    for name in ("USER_MANUAL.en.md", "USER_MANUAL.zh-TW.md"):
        text = (MANUAL / name).read_text(encoding="utf-8")
        pictures = IMAGE.findall(text)
        missing = [p for p in pictures if not (MANUAL / p).is_file()]
        assert not missing, f"{name}: {missing}"
        counts[name] = len(pictures)
    assert len(set(counts.values())) == 1, counts


def test_contents_links_point_at_headings():
    for name in ("USER_MANUAL.en.md", "USER_MANUAL.zh-TW.md"):
        text = (MANUAL / name).read_text(encoding="utf-8")
        slugs = {_slug(h) for h in re.findall(r"^#{1,6} (.+)$", text, re.M)}
        broken = [a for a in re.findall(r"\]\(#([^)]+)\)", text) if a not in slugs]
        assert not broken, f"{name}: {broken}"
