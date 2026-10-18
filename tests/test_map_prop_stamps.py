"""The Full Verification maps' prop stamps (trees, rocks, bushes...) each cut a whole picture
out of the tileset: a picture that runs on past a stamp's edge would leave half of it behind
(the pine bush once carried the bottom of the rock pile on top of it)."""

import sys
from pathlib import Path

import pytest

DEMO = Path(__file__).resolve().parents[1] / "reference_projects" / "full_verification_demo"
sys.path.insert(0, str(DEMO))

import trial_lucifer as lucifer  # noqa: E402
import trial_maps as maps  # noqa: E402

SHEET = (
    lucifer.FREE_ASSETS / "Foozle_2DT0002_Lucifer_Exterior_Tileset_Pixel_Art" / "Png"
) / "OuterTileset.png"


def _cut_edges(image, col, row, w, h, size=16, touching=8):
    """Edges of the stamp a picture runs across: more than ``touching`` opaque pixels inside
    the edge with opaque neighbours just outside it (two pictures that merely touch in the
    sheet share a pixel or a few; a picture cut in half shares a whole run)."""
    alpha = image.getchannel("A")
    x0, y0, x1, y1 = col * size, row * size, (col + w) * size, (row + h) * size

    def solid(x, y):
        return 0 <= x < image.width and 0 <= y < image.height and alpha.getpixel((x, y)) > 0

    runs = {
        "top": sum(solid(x, y0) and solid(x, y0 - 1) for x in range(x0, x1)),
        "bottom": sum(solid(x, y1 - 1) and solid(x, y1) for x in range(x0, x1)),
        "left": sum(solid(x0, y) and solid(x0 - 1, y) for y in range(y0, y1)),
        "right": sum(solid(x1 - 1, y) and solid(x1, y) for y in range(y0, y1)),
    }
    return sorted(edge for edge, count in runs.items() if count > touching)


@pytest.mark.skipif(not SHEET.is_file(), reason="the Lucifer exterior tileset is not here")
@pytest.mark.parametrize("name", sorted(maps.EXTERIOR_PROPS))
def test_every_prop_stamp_holds_a_whole_picture(name):
    from PIL import Image

    image = Image.open(SHEET).convert("RGBA")
    col, row, w, h, _solid = maps.EXTERIOR_PROPS[name]
    assert _cut_edges(image, col, row, w, h) == [], name
