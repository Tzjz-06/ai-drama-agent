"""运行时路径解析。"""

from __future__ import annotations

import sys
import os
from pathlib import Path


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parents[2]


def app_data_root() -> Path:
    """Return the writable per-user data directory.

    Frozen desktop builds must keep mutable data outside the bundled
    ``_internal`` directory so replacing an installation cannot remove user
    projects, sessions, or generated media.
    """
    if getattr(sys, "frozen", False):
        local_app_data = os.getenv("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "FrameForgeStudio"
    return app_root() / "data"


def web_root() -> Path:
    return app_root() / "web"
