"""Scene, entity and other generated ids that come out the same on every build.

A build script calls ``install("some-namespace")`` first: from then on the ids the engine makes
(``asteria.core.ids``) are a counter in a fixed namespace instead of random, so rebuilding a
project does not change the ids its saves, templates and derived projects refer to.
"""

from __future__ import annotations

import itertools
import uuid


def install(namespace):
    from asteria.core import ids

    counter = itertools.count()
    ids.uuid4 = lambda: uuid.uuid5(uuid.NAMESPACE_URL, f"{namespace}:{next(counter)}")
