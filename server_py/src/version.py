"""The release this code is, and the exact commit it is running.

Releases use calendar versions, `vYYYY.MM.N`: the Nth release cut in that
month (`v2026.09.3` is the third release of September 2026). The number
carries no compatibility promise. The one contract an external consumer
depends on, the eval harness's audit event, has its own `schema_version`.

Two values, because `main` is not always a release. Work unrelated to a cut is
committed straight to `main`, so the head the target pulls can sit past the
last release:

* `APP_VERSION` is the `VERSION` file at the repo root: the last release this
  code contains. It is bumped in the release commit, which is then tagged
  `v<VERSION>` (see CLAUDE.md, *Releases*).
* `APP_BUILD` is `git describe` on the running checkout: exactly `v2026.09.2`
  on a release, `v2026.09.2-3-gabc1234` three commits past it. `None` when git
  or the tags are not available. It then falls back to `VERSION` alone.

Both are read once, at import, and never raise: a version label must not stop
the server starting.
"""

from __future__ import annotations

import logging
import os
import subprocess
from typing import Optional

logger = logging.getLogger("app")

# server_py/src/version.py -> src -> server_py -> repo root
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
VERSION_FILE = os.path.join(_REPO_ROOT, "VERSION")


def read_version(path: str = VERSION_FILE) -> str:
    """The `VERSION` file's content, or "unknown" if it cannot be read."""
    try:
        with open(path, encoding="utf-8") as f:
            return f.read().strip() or "unknown"
    except OSError:
        return "unknown"


def read_build(cwd: str = _REPO_ROOT) -> Optional[str]:
    """`git describe` against the release tags, or None.

    `--match "v[0-9]*"` keeps the rollback tags (`pre-prepilot-fixes-...`)
    out of it. No `--dirty`: the target carries per-machine edits to tracked
    files (`.env.native`), so every build there would read as dirty.
    """
    try:
        out = subprocess.run(
            ["git", "describe", "--tags", "--match", "v[0-9]*", "--always"],
            cwd=cwd, capture_output=True, text=True, timeout=5,
        )
    except Exception:  # noqa: BLE001 — no git, or it hung: no build label
        return None
    build = (out.stdout or "").strip()
    return build if out.returncode == 0 and build else None


APP_VERSION = read_version()
APP_BUILD = read_build()
