from __future__ import annotations

from datetime import datetime

from vietcase.db.sqlite import execute, execute_fetchall


def repair_interrupted_jobs() -> None:
    execute(
        "UPDATE download_jobs SET status = 'interrupted', updated_at = ? WHERE status = 'running'",
        (datetime.utcnow().isoformat(timespec='seconds') + 'Z',),
    )


def list_interrupted_jobs() -> list[dict]:
    rows = execute_fetchall("SELECT * FROM download_jobs WHERE status = 'interrupted' ORDER BY id DESC")
    return [dict(row) for row in rows]
