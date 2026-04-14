from __future__ import annotations

from pathlib import Path

from vietcase.core.config import get_settings


def ensure_runtime_dirs() -> None:
    settings = get_settings()
    for path in (settings.data_dir, settings.logs_dir, settings.downloads_dir):
        Path(path).mkdir(parents=True, exist_ok=True)
