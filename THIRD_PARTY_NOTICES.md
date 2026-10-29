# Third-party notices

Asteria's own source code is under the MIT License (`LICENSE`). It uses, and a packaged
editor or exported game may bundle, the software and assets below under their own licences.

## Libraries

| Library | Used for | Licence |
|---|---|---|
| [PySide6](https://doc.qt.io/qtforpython-6/) (Qt for Python) | the editor (optional extra `editor`) | LGPL-3.0 (also GPL-2.0 / GPL-3.0) |
| [pygame-ce](https://pyga.me/) | the game runtime (optional extra `pygame`) | LGPL-2.1 |
| [NumPy](https://numpy.org/) | faster compute kernels (optional extra `fast`) | BSD-3-Clause |
| [Pillow](https://python-pillow.org/) | image tools and RPG Maker MV import (optional extra `mv`) | MIT-CMU |
| [ModernGL](https://github.com/moderngl/moderngl) | the GPU backend (optional extra `moderngl`) | MIT |

PySide6 and pygame-ce are LGPL: Asteria imports them as separate, dynamically loaded
libraries and does not modify them, so you may replace them with your own builds. A
packaged build must keep them as separate files and ship their licence texts.

## Art, fonts and audio

Every asset committed to this repository is listed, with its source, author and licence, in
[`THIRD_PARTY_ASSETS.md`](THIRD_PARTY_ASSETS.md). In short:

- Pixel art, icons, 3D characters and sounds: CC0 1.0 (Foozle, Kenney, Pixel-boy/AAA,
  OpenGameArt authors, Kay Lousberg). No attribution is required; the authors are credited
  there anyway.
- Noto Sans TC (`asset_library/fonts/noto_sans_tc/`): SIL Open Font License 1.1. Its
  `LICENSE.txt` must travel with the font.
- Packs whose licences forbid redistribution are kept out of the repository (see
  `THIRD_PARTY_ASSETS.md`).

## RPG Maker MV

Asteria can import RPG Maker MV projects. It contains no RPG Maker MV code or assets; an
import reads files from a project you own. RPG Maker is a trademark of its owners, and
Asteria is not affiliated with or endorsed by them.
