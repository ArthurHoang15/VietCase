from __future__ import annotations

import sqlite3
from typing import Any, Iterable

from vietcase.core.config import get_settings


def connect() -> sqlite3.Connection:
    settings = get_settings()
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    return conn


def execute(query: str, params: Iterable[Any] = ()) -> None:
    with connect() as conn:
        conn.execute(query, tuple(params))
        conn.commit()


def execute_fetchall(query: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
    with connect() as conn:
        cursor = conn.execute(query, tuple(params))
        return cursor.fetchall()


def execute_fetchone(query: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
    with connect() as conn:
        cursor = conn.execute(query, tuple(params))
        return cursor.fetchone()
