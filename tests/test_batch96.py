import pytest
from asteria.presentation.fidelity_import import *


def test_import_preserves_resolution_alpha_timing_layers_and_metadata():
    s = FidelitySource(
        "hero",
        (SourceFrame("f0", 128, 192, 83.5, True, (64, 180)), SourceFrame("f1", 128, 192, 117.25, True, (64, 180))),
        (SourceLayer("cape", 2, "add", 0.75, "cloth"),),
        metadata={"source": "master.psd", "profile": "srgb"},
    )
    r = FidelityImporter().import_source(s)
    assert r.clip.frame_size == (128, 192)
    assert [x.duration_ms for x in r.clip.timings] == [83.5, 117.25]
    assert r.clip.layers[0].blend_mode == "add" and r.clip.layers[0].material == "cloth"
    assert r.alpha_preserved and r.timing_preserved and r.resolution_preserved and r.layers_preserved
    assert r.source_metadata["source"] == "master.psd"


def test_variable_dimensions_are_not_silently_resampled():
    s = FidelitySource("x", (SourceFrame("a", 64, 64, 100), SourceFrame("b", 96, 80, 100)))
    r = FidelityImporter().import_source(s)
    assert r.clip.frame_size == (96, 80) and "variable_frame_dimensions" in r.review_required
    assert not r.resolution_preserved


def test_detached_content_is_never_silently_discarded():
    r = FidelityImporter().import_source(
        FidelitySource("x", (SourceFrame("a", 1, 1, 1),), detached_candidates=("weapon?", "shadow?"))
    )
    assert "detached_candidates" in r.review_required


def test_per_frame_pivot_variation_requires_review():
    r = FidelityImporter().import_source(
        FidelitySource("x", (SourceFrame("a", 10, 10, 10, pivot=(1, 9)), SourceFrame("b", 10, 10, 10, pivot=(2, 9))))
    )
    assert "per_frame_pivot_variation" in r.review_required


def test_arbitrary_frame_count_and_submillisecond_timing():
    frames = tuple(SourceFrame(str(i), 32, 48, 0.25 + i / 1000) for i in range(37))
    r = FidelityImporter().import_source(FidelitySource("x", frames))
    assert len(r.clip.frames) == 37 and r.clip.timings[-1].duration_ms == pytest.approx(0.286)


def test_invalid_source_rejected():
    with pytest.raises(ValueError):
        FidelitySource("", (SourceFrame("a", 1, 1, 1),))
