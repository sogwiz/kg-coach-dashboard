"""
Locate the seed ``data/`` directory at runtime.

Locally the data lives at the repo root (``<repo>/data``), two levels above the
``backend`` package.  On Vercel's services deploy the backend is built from the
``backend`` entrypoint and the function's filesystem layout may differ, so we
search upward from this file for the first ancestor that contains a ``data``
directory with the exercise catalog rather than hard-coding a fixed depth.

``data/**`` is shipped into the backend bundle via ``includeFiles`` in
vercel.json, so the directory is present somewhere on the path either way.
"""

from __future__ import annotations

import functools
from pathlib import Path

# A file that must exist inside a real data directory — used to disambiguate
# the seed data dir from any unrelated folder that happens to be named "data".
_SENTINEL = "exercises.json"


@functools.lru_cache(maxsize=1)
def find_data_dir() -> Path:
    """Return the seed ``data`` directory, searching ancestors of this file.

    Falls back to ``<repo>/data`` (the local layout) when no candidate contains
    the sentinel, so callers still get a stable, predictable path for error
    messages even if the data was not shipped.
    """
    here = Path(__file__).resolve()
    for ancestor in here.parents:
        candidate = ancestor / "data"
        if (candidate / _SENTINEL).is_file():
            return candidate
    # Fallback: the in-package location (backend/app/data/paths.py → parents[2]
    # is the backend dir, which holds data/).
    return here.parents[2] / "data"
