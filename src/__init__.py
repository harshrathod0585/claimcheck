"""ClaimCheck.

Loads claimcheck/.env before any module reads configuration. Doing this in a
single module meant settings read at import time elsewhere saw an unpopulated
environment, which silently disabled live verification.
"""
from __future__ import annotations

import os
import pathlib


def _load_dotenv() -> None:
    """Read claimcheck/.env if present, without adding a dependency.

    Real environment variables win, so an explicit export still overrides the
    file. The file is gitignored: a key belongs on disk, not in shell history.
    """
    env = pathlib.Path(__file__).parent.parent / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()
