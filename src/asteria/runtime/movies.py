"""A movie: PNG frames in a zip, read one at a time (a picture can show one, see ``pictures``)."""

from __future__ import annotations

import io
import zipfile


def is_movie(path):
    return str(path).lower().endswith(".zip")


class Movie:
    """The frames of a zip, in the order of their file names."""

    def __init__(self, pg, path):
        self.pg = pg
        self.archive = zipfile.ZipFile(path)
        self.names = sorted(n for n in self.archive.namelist() if n.lower().endswith(".png"))
        if not self.names:
            raise ValueError(f"{path}: a movie is a zip of .png frames")
        self._index = None
        self._image = None

    def __len__(self):
        return len(self.names)

    def frame_at(self, age, rate, first=0, loop=False):
        """The frame number ``age`` seconds in, at ``rate`` frames a second (0: ``first``)."""
        step = int(first) + int(age * rate + 1e-9) if rate > 0 else int(first)
        return step % len(self) if loop else max(0, min(step, len(self) - 1))

    def image(self, index):
        if index != self._index:
            data = io.BytesIO(self.archive.read(self.names[index]))
            self._image = self.pg.image.load(data, "frame.png").convert()
            self._index = index
        return self._image
