from __future__ import annotations

from vietcase.db.sqlite import connect


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_url TEXT NOT NULL UNIQUE,
    document_id TEXT,
    document_type TEXT,
    document_number TEXT,
    issued_date TEXT,
    published_date TEXT,
    court_level TEXT,
    court_name TEXT,
    adjudication_level TEXT,
    case_style TEXT,
    legal_relation TEXT,
    summary_text TEXT,
    pdf_url TEXT,
    pdf_path TEXT,
    file_name_original TEXT,
    download_status TEXT DEFAULT 'pending',
    download_error TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    downloaded_at TEXT,
    last_job_id INTEGER
);

CREATE TABLE IF NOT EXISTS download_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mode TEXT NOT NULL,
    job_name TEXT,
    filters_json TEXT,
    status TEXT NOT NULL DEFAULT 'queued',
    source_mode TEXT NOT NULL DEFAULT 'requests',
    source_mode_reason TEXT NOT NULL DEFAULT 'initial_default',
    total_results_estimate INTEGER DEFAULT 0,
    total_pages_estimate INTEGER DEFAULT 0,
    items_total INTEGER DEFAULT 0,
    items_completed INTEGER DEFAULT 0,
    items_failed INTEGER DEFAULT 0,
    started_at TEXT,
    finished_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS job_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    source_url TEXT NOT NULL,
    document_id TEXT,
    document_type TEXT,
    document_number TEXT,
    issued_date TEXT,
    court_name TEXT,
    case_style TEXT,
    summary_text TEXT,
    pdf_url TEXT,
    pdf_path TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    error_message TEXT,
    selected INTEGER DEFAULT 1,
    page_index INTEGER DEFAULT 1,
    result_index INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(job_id, source_url)
);

CREATE TABLE IF NOT EXISTS filter_option_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_key TEXT NOT NULL,
    parent_key TEXT,
    parent_value TEXT,
    option_value TEXT,
    option_label TEXT,
    sort_order INTEGER DEFAULT 0,
    fetched_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
