"""AST-11 / AP §17, §21: deterministic auto-fixes and atlas packing; destructive fixes need confirmation."""

import pytest
from PIL import Image, ImageDraw

from asteria.assets.autofix import (
    FIXES,
    ConfirmationRequired,
    apply_fix,
    content_pivot,
    preview_fix,
    repack_atlas,
)


def _sprite(size=(32, 32), box=(10, 6, 19, 25)):
    image = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(image).rectangle(box, fill=(200, 60, 40, 255))
    return image


def test_all_spec_fixes_exist():
    assert FIXES == (
        "crop_transparent_border",
        "pad_frame",
        "resize_nearest",
        "align_pivot",
        "shift_frame",
        "normalize_alpha",
        "remove_empty_outer",
        "repack_atlas",
    )


def test_crop_and_pad_are_safe_and_deterministic():
    cropped, report = apply_fix("crop_transparent_border", _sprite())
    assert cropped.size == (10, 20) and not report.destructive
    padded, report = apply_fix("pad_frame", cropped, (32, 32))
    assert padded.size == (32, 32) and not report.destructive
    assert padded.getchannel("A").getbbox() == (11, 12, 21, 32)  # feet on the bottom edge, centred
    assert apply_fix("pad_frame", cropped, (32, 32))[0].tobytes() == padded.tobytes()


def test_align_pivot_moves_content_to_feet_centre():
    aligned, report = apply_fix("align_pivot", _sprite(box=(2, 2, 9, 11)))
    assert content_pivot(aligned) == (0.5, 1.0) and not report.destructive


def test_destructive_fixes_need_preview_and_confirmation():
    sprite = _sprite()
    with pytest.raises(ConfirmationRequired):
        apply_fix("resize_nearest", sprite, (8, 8))  # downscale loses pixels
    before, after, report = preview_fix("resize_nearest", sprite, (8, 8))
    assert before is sprite and after.size == (8, 8) and report.destructive
    out, _ = apply_fix("resize_nearest", sprite, (8, 8), confirmed=True)
    assert out.size == (8, 8)
    assert not apply_fix("resize_nearest", sprite, (64, 64))[1].destructive  # upscale is safe
    with pytest.raises(ConfirmationRequired):
        apply_fix("shift_frame", sprite, 20, 0)  # pushes content off the frame
    soft = Image.new("RGBA", (4, 4), (255, 0, 0, 100))
    with pytest.raises(ConfirmationRequired):
        apply_fix("normalize_alpha", soft)


def test_repack_atlas_places_every_frame_without_overlap():
    frames = {f"f{i}": _sprite((8 + i * 3, 10 + (i % 3) * 7), (0, 0, 4, 4)) for i in range(12)}
    atlas, report = repack_atlas(frames, padding=1, max_width=64)
    regions = atlas.regions
    assert set(regions) == set(frames) and report.after_size == atlas.image.size
    boxes = list(regions.values())
    for i, (ax, ay, aw, ah) in enumerate(boxes):
        assert ax + aw <= atlas.image.width and ay + ah <= atlas.image.height
        for bx, by, bw, bh in boxes[i + 1 :]:
            assert ax + aw <= bx or bx + bw <= ax or ay + ah <= by or by + bh <= ay
    for name, (x, y, w, h) in regions.items():
        assert atlas.image.crop((x, y, x + w, y + h)).tobytes() == frames[name].tobytes()
    again, _ = repack_atlas(frames, padding=1, max_width=64)
    assert again.regions == regions and again.image.tobytes() == atlas.image.tobytes()
