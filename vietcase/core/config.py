from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    host: str = "127.0.0.1"
    port: int = 8000
    request_timeout: int = 120
    rate_limit_ms: int = 1500
    interactive_rate_limit_ms: int = 0
    crawl_rate_limit_ms: int = 1500
    max_retries: int = 3
    playwright_enabled: bool = True
    source_mode_default: str = "auto"
    search_source_mode: str = "requests"
    download_source_mode: str = "requests"
    playwright_browser: str = "chromium"
    tls_mode: str = "auto"
    preview_state_ttl_seconds: int = 1800
    debug_search_snapshots: bool = False
    base_dir: Path = Path(__file__).resolve().parents[2]

    @property
    def data_dir(self) -> Path:
        return self.base_dir / "data"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "app.db"

    @property
    def downloads_dir(self) -> Path:
        return self.base_dir / "downloads"

    @property
    def debug_dir(self) -> Path:
        return self.data_dir / "search_debug"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
