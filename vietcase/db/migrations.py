from __future__ import annotations

from vietcase.db.sqlite import connect


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_url TEXT NOT NULL UNIQUE,
    document_id TEXT,
    title TEXT,
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
    source_card_text TEXT,
    source_card_html TEXT,
    precedent_applied TEXT,
    correction_count TEXT,
    precedent_vote_count TEXT,
    pdf_text TEXT,
    search_text_normalized TEXT,
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
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    job_folder TEXT,
    last_processed_page INTEGER DEFAULT 0,
    tls_mode TEXT DEFAULT 'secure'
);

CREATE TABLE IF NOT EXISTS job_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    source_url TEXT NOT NULL,
    document_id TEXT,
    title TEXT,
    document_type TEXT,
    document_number TEXT,
    issued_date TEXT,
    court_name TEXT,
    case_style TEXT,
    summary_text TEXT,
    source_card_text TEXT,
    source_card_html TEXT,
    precedent_applied TEXT,
    correction_count TEXT,
    precedent_vote_count TEXT,
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

CREATE TABLE IF NOT EXISTS document_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_source_url TEXT NOT NULL,
    job_id INTEGER,
    job_folder TEXT,
    pdf_path TEXT NOT NULL,
    file_name_original TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
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


DOCUMENT_FTS_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
    source_url UNINDEXED,
    search_text_normalized
);
"""


def _ensure_column(conn, table: str, column: str, column_def: str) -> None:
    existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_def}")


def _seed_document_files_from_documents(conn) -> None:
    existing_count = conn.execute("SELECT COUNT(*) FROM document_files").fetchone()[0]
    if int(existing_count or 0) > 0:
        return
    rows = conn.execute(
        "SELECT source_url, last_job_id, pdf_path, file_name_original, downloaded_at, created_at FROM documents WHERE COALESCE(pdf_path, '') <> ''"
    ).fetchall()
    for row in rows:
        conn.execute(
            "INSERT INTO document_files (document_source_url, job_id, job_folder, pdf_path, file_name_original, created_at) VALUES (?, ?, '', ?, ?, COALESCE(?, ?, CURRENT_TIMESTAMP))",
            (
                row[0],
                row[1],
                row[2],
                row[3],
                row[4],
                row[5],
            ),
        )


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA_SQL)
        for table, columns in {
            'documents': {
                'title': 'TEXT',
                'source_card_text': 'TEXT',
                'source_card_html': 'TEXT',
                'precedent_applied': 'TEXT',
                'correction_count': 'TEXT',
                'precedent_vote_count': 'TEXT',
                'pdf_text': 'TEXT',
                'search_text_normalized': 'TEXT',
            },
            'job_items': {
                'title': 'TEXT',
                'source_card_text': 'TEXT',
                'source_card_html': 'TEXT',
                'precedent_applied': 'TEXT',
                'correction_count': 'TEXT',
                'precedent_vote_count': 'TEXT',
            },
            'download_jobs': {
                'job_folder': 'TEXT',
                'last_processed_page': 'INTEGER DEFAULT 0',
                'tls_mode': "TEXT DEFAULT 'secure'",
            },
        }.items():
            for column, column_def in columns.items():
                _ensure_column(conn, table, column, column_def)

        try:
            conn.executescript(DOCUMENT_FTS_SQL)
        except Exception:
            pass

        _seed_document_files_from_documents(conn)
        conn.commit()
