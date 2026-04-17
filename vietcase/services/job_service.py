from __future__ import annotations

import json
import logging
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

from vietcase.core.config import get_settings
from vietcase.core.text_utils import build_search_text, normalize_for_search
from vietcase.db.sqlite import connect, execute_fetchall, execute_fetchone
from vietcase.services.detail_service import DetailService
from vietcase.services.pdf_service import PdfService
from vietcase.services.search_service import SearchService
from vietcase.services.source_router import SourceContext


LOGGER = logging.getLogger(__name__)


class JobService:
    def __init__(self, search_service: SearchService, detail_service: DetailService, pdf_service: PdfService) -> None:
        self.search_service = search_service
        self.detail_service = detail_service
        self.pdf_service = pdf_service
        self.settings = get_settings()
        self._threads: dict[int, threading.Thread] = {}

    def create_job(self, mode: str, job_name: str, filters: dict | None = None, items: list[dict] | None = None) -> dict:
        filters = filters or {}
        items = items or []
        job_folder = self._job_folder_path()
        with connect() as conn:
            cursor = conn.execute(
                "INSERT INTO download_jobs (mode, job_name, filters_json, status, source_mode, source_mode_reason, job_folder, last_processed_page, tls_mode) VALUES (?, ?, ?, 'queued', ?, 'initial_default', ?, 0, 'secure')",
                (mode, job_name, json.dumps(filters, ensure_ascii=False), self.settings.download_source_mode, str(job_folder)),
            )
            job_id = int(cursor.lastrowid)
            for item in items:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO job_items (
                        job_id, source_url, document_id, title, document_type, document_number,
                        issued_date, court_name, case_style, summary_text,
                        source_card_text, source_card_html, precedent_applied,
                        correction_count, precedent_vote_count,
                        selected, page_index, result_index
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        job_id,
                        item.get("source_url", ""),
                        item.get("document_id", ""),
                        item.get("title", ""),
                        item.get("document_type", ""),
                        item.get("document_number", ""),
                        item.get("issued_date", ""),
                        item.get("court_name", ""),
                        item.get("case_style", ""),
                        item.get("summary_text", ""),
                        item.get("source_card_text", ""),
                        item.get("source_card_html", ""),
                        item.get("precedent_applied", ""),
                        item.get("correction_count", ""),
                        item.get("precedent_vote_count", ""),
                        1,
                        int(item.get("page_index", 1) or 1),
                        int(item.get("result_index", 0) or 0),
                    ),
                )
            conn.execute("UPDATE download_jobs SET items_total = (SELECT COUNT(*) FROM job_items WHERE job_id = ?) WHERE id = ?", (job_id, job_id))
            conn.commit()
        return self.get_job(job_id)

    def start_job(self, job_id: int) -> None:
        if job_id in self._threads and self._threads[job_id].is_alive():
            return
        thread = threading.Thread(target=self._run_job, args=(job_id,), daemon=True)
        self._threads[job_id] = thread
        thread.start()

    def resume_job(self, job_id: int) -> None:
        if self._job_status(job_id) == "completed":
            return
        with connect() as conn:
            conn.execute("UPDATE download_jobs SET status = 'queued', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (job_id,))
            conn.commit()
        self.start_job(job_id)

    def pause_job(self, job_id: int) -> None:
        if self._job_status(job_id) == "completed":
            return
        with connect() as conn:
            conn.execute("UPDATE download_jobs SET status = 'paused', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (job_id,))
            conn.commit()

    def cancel_job(self, job_id: int) -> None:
        if self._job_status(job_id) == "completed":
            return
        with connect() as conn:
            conn.execute("UPDATE download_jobs SET status = 'cancelled', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (job_id,))
            conn.commit()

    def list_jobs(self) -> list[dict]:
        return [dict(row) for row in execute_fetchall("SELECT * FROM download_jobs ORDER BY id DESC")]

    def get_job(self, job_id: int) -> dict:
        row = execute_fetchone("SELECT * FROM download_jobs WHERE id = ?", (job_id,))
        return dict(row) if row else {}

    def _job_status(self, job_id: int) -> str:
        row = execute_fetchone("SELECT status FROM download_jobs WHERE id = ?", (job_id,))
        return str(row["status"] if row and row["status"] is not None else "")

    def list_job_items(self, job_id: int) -> list[dict]:
        return [dict(row) for row in execute_fetchall("SELECT * FROM job_items WHERE job_id = ? ORDER BY page_index, result_index, id", (job_id,))]

    def list_documents(self) -> list[dict]:
        return [dict(row) for row in execute_fetchall("SELECT * FROM documents ORDER BY id DESC")]

    def get_document_file(self, document_file_id: int) -> dict:
        row = execute_fetchone(
            """
            SELECT
                df.id,
                df.document_source_url,
                df.job_id,
                df.job_folder,
                df.pdf_path,
                df.file_name_original,
                df.created_at AS file_created_at,
                d.source_url,
                d.document_id,
                d.title,
                d.document_type,
                d.document_number,
                d.issued_date,
                d.published_date,
                d.court_level,
                d.court_name,
                d.adjudication_level,
                d.case_style,
                d.legal_relation,
                d.summary_text,
                d.source_card_text,
                d.source_card_html,
                d.precedent_applied,
                d.correction_count,
                d.precedent_vote_count,
                d.pdf_text,
                d.search_text_normalized,
                d.pdf_url,
                d.download_status,
                d.download_error,
                d.created_at,
                d.updated_at,
                d.downloaded_at,
                d.last_job_id
            FROM document_files df
            JOIN documents d ON d.source_url = df.document_source_url
            WHERE df.id = ?
            """,
            (document_file_id,),
        )
        return dict(row) if row else {}

    def search_document_files(
        self,
        *,
        q: str = "",
        document_type: str = "",
        court_name: str = "",
        case_style: str = "",
        legal_relation: str = "",
        date_from: str = "",
        date_to: str = "",
        page: int = 1,
        page_size: int = 10,
    ) -> dict[str, object]:
        page = max(1, int(page or 1))
        page_size = max(1, min(100, int(page_size or 10)))
        rows = [dict(row) for row in execute_fetchall(
            """
            SELECT
                df.id,
                df.document_source_url,
                df.job_id,
                df.job_folder,
                df.pdf_path,
                df.file_name_original,
                df.created_at AS file_created_at,
                d.source_url,
                d.document_id,
                d.title,
                d.document_type,
                d.document_number,
                d.issued_date,
                d.published_date,
                d.court_level,
                d.court_name,
                d.adjudication_level,
                d.case_style,
                d.legal_relation,
                d.summary_text,
                d.source_card_text,
                d.source_card_html,
                d.precedent_applied,
                d.correction_count,
                d.precedent_vote_count,
                d.pdf_text,
                d.search_text_normalized,
                d.pdf_url,
                d.download_status,
                d.download_error,
                d.created_at,
                d.updated_at,
                d.downloaded_at,
                d.last_job_id
            FROM document_files df
            JOIN documents d ON d.source_url = df.document_source_url
            ORDER BY COALESCE(d.published_date, '') DESC, COALESCE(d.issued_date, '') DESC, df.id DESC
            """
        )]

        options = {
            "document_type": self._distinct_values(rows, "document_type"),
            "court_name": self._distinct_values(rows, "court_name"),
            "case_style": self._distinct_values(rows, "case_style"),
            "legal_relation": self._distinct_values(rows, "legal_relation"),
        }

        matched_source_urls = self._find_matching_source_urls(q)
        filtered = []
        for row in rows:
            if matched_source_urls is not None and row.get("source_url") not in matched_source_urls:
                continue
            if document_type and row.get("document_type", "") != document_type:
                continue
            if court_name and row.get("court_name", "") != court_name:
                continue
            if case_style and row.get("case_style", "") != case_style:
                continue
            if legal_relation and row.get("legal_relation", "") != legal_relation:
                continue
            issued_date = str(row.get("issued_date") or "")
            if date_from and issued_date and issued_date < date_from:
                continue
            if date_from and not issued_date:
                continue
            if date_to and issued_date and issued_date > date_to:
                continue
            if date_to and not issued_date:
                continue
            filtered.append(row)

        total = len(filtered)
        start = (page - 1) * page_size
        items = filtered[start : start + page_size]
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "filter_options": options,
        }

    def delete_job(self, job_id: int) -> dict[str, int]:
        return self.delete_jobs([job_id])

    def delete_jobs(self, job_ids: list[int]) -> dict[str, int]:
        normalized_ids = self._normalize_ids(job_ids)
        if not normalized_ids:
            return {"deleted_count": 0}

        placeholders = ", ".join("?" for _ in normalized_ids)
        with connect() as conn:
            rows = conn.execute(
                f"SELECT id FROM download_jobs WHERE id IN ({placeholders})",
                tuple(normalized_ids),
            ).fetchall()
            existing_ids = [int(row["id"]) for row in rows]
            if not existing_ids:
                return {"deleted_count": 0}
            existing_placeholders = ", ".join("?" for _ in existing_ids)
            conn.execute(f"DELETE FROM job_items WHERE job_id IN ({existing_placeholders})", tuple(existing_ids))
            conn.execute(f"DELETE FROM download_jobs WHERE id IN ({existing_placeholders})", tuple(existing_ids))
            conn.commit()

        for job_id in existing_ids:
            self._threads.pop(job_id, None)

        return {"deleted_count": len(existing_ids)}

    def delete_all_jobs(self) -> dict[str, int]:
        all_ids = [int(job["id"]) for job in self.list_jobs()]
        return self.delete_jobs(all_ids)

    def delete_document(self, document_file_id: int) -> dict[str, int]:
        return self.delete_documents([document_file_id])

    def delete_documents(self, document_file_ids: list[int]) -> dict[str, int]:
        normalized_ids = self._normalize_ids(document_file_ids)
        if not normalized_ids:
            return {"deleted_count": 0, "deleted_file_count": 0}

        placeholders = ", ".join("?" for _ in normalized_ids)
        deleted_file_count = 0
        deleted_document_rows = 0
        with connect() as conn:
            rows = conn.execute(
                f"SELECT id, document_source_url, pdf_path FROM document_files WHERE id IN ({placeholders})",
                tuple(normalized_ids),
            ).fetchall()
            file_rows = [dict(row) for row in rows]
            existing_ids = [int(row["id"]) for row in rows]
            if not existing_ids:
                return {"deleted_count": 0, "deleted_file_count": 0}

            existing_placeholders = ", ".join("?" for _ in existing_ids)
            for row in file_rows:
                pdf_path = str(row.get("pdf_path") or "").strip()
                if not pdf_path:
                    continue
                remaining = conn.execute(
                    f"SELECT COUNT(*) FROM document_files WHERE pdf_path = ? AND id NOT IN ({existing_placeholders})",
                    (pdf_path, *existing_ids),
                ).fetchone()[0]
                if int(remaining or 0) == 0 and self._delete_pdf_file(pdf_path):
                    deleted_file_count += 1

            conn.execute(f"DELETE FROM document_files WHERE id IN ({existing_placeholders})", tuple(existing_ids))

            affected_sources = sorted({str(row.get("document_source_url") or "") for row in file_rows if str(row.get("document_source_url") or "").strip()})
            for source_url in affected_sources:
                remaining = conn.execute(
                    "SELECT COUNT(*) FROM document_files WHERE document_source_url = ?",
                    (source_url,),
                ).fetchone()[0]
                if int(remaining or 0) == 0:
                    deleted_document_rows += self._delete_document_canonical(conn, source_url)
            conn.commit()

        return {"deleted_count": len(existing_ids), "deleted_file_count": deleted_file_count, "deleted_document_rows": deleted_document_rows}

    def delete_all_documents(self) -> dict[str, int]:
        all_ids = [int(row["id"]) for row in execute_fetchall("SELECT id FROM document_files ORDER BY id" )]
        return self.delete_documents(all_ids)

    def _run_job(self, job_id: int) -> None:
        job = self.get_job(job_id)
        if not job:
            return
        filters = json.loads(job.get("filters_json") or "{}")
        download_ctx = SourceContext(source_mode=job.get("source_mode") or self.settings.download_source_mode, job_id=job_id)
        job_folder = Path(job.get("job_folder") or self._job_folder_path())
        job_folder.mkdir(parents=True, exist_ok=True)
        self._update_job(job_id, status="running", started_at=self._now(), job_folder=str(job_folder))

        if filters and not self.list_job_items(job_id):
            self._populate_items_from_filters(job_id, filters)

        for item in self.list_job_items(job_id):
            latest_job = self.get_job(job_id)
            if not latest_job:
                LOGGER.info("Stopping job %s because it was deleted", job_id)
                return
            if latest_job.get("status") in {"paused", "cancelled"}:
                LOGGER.info("Stopping job %s because status is %s", job_id, latest_job.get("status"))
                return
            if item.get("status") == "completed":
                continue
            try:
                detail = self.detail_service.fetch(item["source_url"], context=download_ctx)
                if not detail.get("pdf_url"):
                    raise ValueError("Khong tim thay duong dan PDF trong trang chi tiet")
                saved = self.pdf_service.save_pdf(
                    detail["pdf_url"],
                    job_folder,
                    detail.get("document_number", "") or item.get("document_number", ""),
                )
                self._mark_item_completed(job_id, item, detail, saved, download_ctx.source_mode, job_folder)
            except Exception as exc:
                LOGGER.exception("Failed to process item %s in job %s", item.get("id"), job_id)
                self._mark_item_failed(job_id, item["id"], str(exc), download_ctx.source_mode)

        self._update_job(
            job_id,
            status="completed",
            finished_at=self._now(),
            source_mode=download_ctx.source_mode,
            source_mode_reason="auto_fallback_detected" if download_ctx.source_mode == "playwright" else "initial_default",
        )

    def _populate_items_from_filters(self, job_id: int, filters: dict[str, object]) -> None:
        search_ctx = SourceContext(source_mode=self.settings.search_source_mode, job_id=job_id)
        total_pages = 0
        total_results = 0
        for preview in self.search_service.iter_all_results(filters, context=search_ctx):
            total_pages = preview.total_pages
            total_results = preview.total_results
            with connect() as conn:
                for item in preview.results:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO job_items (
                            job_id, source_url, document_id, title, document_type, document_number,
                            issued_date, court_name, case_style, summary_text,
                            source_card_text, source_card_html, precedent_applied,
                            correction_count, precedent_vote_count,
                            selected, page_index, result_index
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            job_id,
                            item.get("source_url", ""),
                            item.get("document_id", ""),
                            item.get("title", ""),
                            item.get("document_type", ""),
                            item.get("document_number", ""),
                            item.get("issued_date", ""),
                            item.get("court_name", ""),
                            item.get("case_style", ""),
                            item.get("summary_text", ""),
                            item.get("source_card_text", ""),
                            item.get("source_card_html", ""),
                            item.get("precedent_applied", ""),
                            item.get("correction_count", ""),
                            item.get("precedent_vote_count", ""),
                            1,
                            int(item.get("page_index", 1) or 1),
                            int(item.get("result_index", 0) or 0),
                        ),
                    )
                conn.execute(
                    "UPDATE download_jobs SET items_total = (SELECT COUNT(*) FROM job_items WHERE job_id = ?), total_results_estimate = ?, total_pages_estimate = ?, last_processed_page = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (job_id, total_results, total_pages, preview.current_page, job_id),
                )
                conn.commit()

    def _mark_item_completed(self, job_id: int, item: dict, detail: dict, saved: dict, source_mode: str, job_folder: Path) -> None:
        title_value = str(detail.get("title") or item.get("title") or "").strip()
        resolved_number = str(saved.get("resolved_document_number") or detail.get("document_number") or item.get("document_number") or "").strip()
        source_card_text = str(item.get("source_card_text") or detail.get("source_card_text") or "").strip()
        source_card_html = str(item.get("source_card_html") or detail.get("source_card_html") or "").strip()
        pdf_text = str(saved.get("pdf_text") or "")
        search_text_normalized = build_search_text([
            title_value,
            detail.get("document_type", item.get("document_type", "")),
            resolved_number,
            detail.get("issued_date", item.get("issued_date", "")),
            detail.get("published_date", ""),
            detail.get("court_name", item.get("court_name", "")),
            detail.get("case_style", item.get("case_style", "")),
            detail.get("legal_relation", ""),
            detail.get("summary_text", item.get("summary_text", "")),
            source_card_text,
            pdf_text,
        ])
        with connect() as conn:
            conn.execute(
                "UPDATE job_items SET title = ?, document_number = ?, pdf_url = ?, pdf_path = ?, source_card_text = ?, source_card_html = ?, precedent_applied = ?, correction_count = ?, precedent_vote_count = ?, status = 'completed', error_message = NULL, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (
                    title_value,
                    resolved_number,
                    detail.get("pdf_url", ""),
                    saved.get("pdf_path", ""),
                    source_card_text,
                    source_card_html,
                    detail.get("precedent_applied", item.get("precedent_applied", "")),
                    detail.get("correction_count", item.get("correction_count", "")),
                    detail.get("precedent_vote_count", item.get("precedent_vote_count", "")),
                    item["id"],
                ),
            )
            conn.execute(
                """
                INSERT INTO documents (
                    source_url, document_id, title, document_type, document_number, issued_date, published_date,
                    court_name, adjudication_level, case_style, legal_relation, summary_text,
                    source_card_text, source_card_html, precedent_applied, correction_count, precedent_vote_count,
                    pdf_text, search_text_normalized, pdf_url, pdf_path, file_name_original,
                    download_status, downloaded_at, last_job_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'completed', ?, ?)
                ON CONFLICT(source_url) DO UPDATE SET
                    document_id=excluded.document_id,
                    title=excluded.title,
                    document_type=excluded.document_type,
                    document_number=excluded.document_number,
                    issued_date=excluded.issued_date,
                    published_date=excluded.published_date,
                    court_name=excluded.court_name,
                    adjudication_level=excluded.adjudication_level,
                    case_style=excluded.case_style,
                    legal_relation=excluded.legal_relation,
                    summary_text=excluded.summary_text,
                    source_card_text=excluded.source_card_text,
                    source_card_html=excluded.source_card_html,
                    precedent_applied=excluded.precedent_applied,
                    correction_count=excluded.correction_count,
                    precedent_vote_count=excluded.precedent_vote_count,
                    pdf_text=excluded.pdf_text,
                    search_text_normalized=excluded.search_text_normalized,
                    pdf_url=excluded.pdf_url,
                    pdf_path=excluded.pdf_path,
                    file_name_original=excluded.file_name_original,
                    download_status='completed',
                    downloaded_at=excluded.downloaded_at,
                    last_job_id=excluded.last_job_id,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    detail.get("source_url", item.get("source_url", "")),
                    detail.get("document_id", item.get("document_id", "")),
                    title_value,
                    detail.get("document_type", item.get("document_type", "")),
                    resolved_number,
                    detail.get("issued_date", item.get("issued_date", "")),
                    detail.get("published_date", ""),
                    detail.get("court_name", item.get("court_name", "")),
                    detail.get("adjudication_level", item.get("adjudication_level", "")),
                    detail.get("case_style", item.get("case_style", "")),
                    detail.get("legal_relation", item.get("legal_relation", "")),
                    detail.get("summary_text", item.get("summary_text", "")),
                    source_card_text,
                    source_card_html,
                    detail.get("precedent_applied", item.get("precedent_applied", "")),
                    detail.get("correction_count", item.get("correction_count", "")),
                    detail.get("precedent_vote_count", item.get("precedent_vote_count", "")),
                    pdf_text,
                    search_text_normalized,
                    detail.get("pdf_url", ""),
                    saved.get("pdf_path", ""),
                    saved.get("file_name_original", ""),
                    self._now(),
                    job_id,
                ),
            )
            conn.execute(
                "INSERT INTO document_files (document_source_url, job_id, job_folder, pdf_path, file_name_original) VALUES (?, ?, ?, ?, ?)",
                (
                    detail.get("source_url", item.get("source_url", "")),
                    job_id,
                    str(job_folder),
                    saved.get("pdf_path", ""),
                    saved.get("file_name_original", ""),
                ),
            )
            self._sync_document_search_index(conn, detail.get("source_url", item.get("source_url", "")), search_text_normalized)
            conn.execute(
                "UPDATE download_jobs SET items_completed = COALESCE(items_completed, 0) + 1, source_mode = ?, source_mode_reason = ?, tls_mode = COALESCE(tls_mode, 'secure'), updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (source_mode, "auto_fallback_detected" if source_mode == "playwright" else "initial_default", job_id),
            )
            conn.commit()

    def _mark_item_failed(self, job_id: int, item_id: int, error_message: str, source_mode: str) -> None:
        with connect() as conn:
            conn.execute("UPDATE job_items SET status = 'failed', error_message = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (error_message, item_id))
            conn.execute(
                "UPDATE download_jobs SET items_failed = COALESCE(items_failed, 0) + 1, source_mode = ?, source_mode_reason = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (source_mode, "auto_fallback_detected" if source_mode == "playwright" else "initial_default", job_id),
            )
            conn.commit()

    def _update_job(self, job_id: int, **fields: object) -> None:
        if not fields:
            return
        columns = []
        values = []
        for key, value in fields.items():
            columns.append(f"{key} = ?")
            values.append(value)
        columns.append("updated_at = CURRENT_TIMESTAMP")
        values.append(job_id)
        with connect() as conn:
            conn.execute(f"UPDATE download_jobs SET {', '.join(columns)} WHERE id = ?", tuple(values))
            conn.commit()

    def _job_folder_path(self) -> Path:
        base_name = datetime.now().strftime("%d-%m-%Y-%H-%M")
        candidate = self.settings.downloads_dir / base_name
        counter = 2
        while candidate.exists():
            candidate = self.settings.downloads_dir / f"{base_name}__{counter}"
            counter += 1
        return candidate

    def _find_matching_source_urls(self, query: str) -> set[str] | None:
        normalized_query = normalize_for_search(query)
        if not normalized_query:
            return None

        matched: set[str] = set()
        with connect() as conn:
            if self._fts_available(conn):
                fts_query = " AND ".join(f'"{term}"' for term in normalized_query.split() if term)
                try:
                    rows = conn.execute(
                        "SELECT source_url FROM documents_fts WHERE search_text_normalized MATCH ?",
                        (fts_query,),
                    ).fetchall()
                    matched = {str(row[0]) for row in rows}
                except sqlite3.Error:
                    matched = set()
            if not matched:
                rows = conn.execute(
                    "SELECT source_url FROM documents WHERE COALESCE(search_text_normalized, '') LIKE ?",
                    (f"%{normalized_query}%",),
                ).fetchall()
                matched = {str(row[0]) for row in rows}
        return matched

    def _sync_document_search_index(self, conn: sqlite3.Connection, source_url: str, search_text_normalized: str) -> None:
        if not source_url or not self._fts_available(conn):
            return
        try:
            conn.execute("DELETE FROM documents_fts WHERE source_url = ?", (source_url,))
            conn.execute(
                "INSERT INTO documents_fts (source_url, search_text_normalized) VALUES (?, ?)",
                (source_url, search_text_normalized),
            )
        except sqlite3.Error:
            return

    def _delete_document_canonical(self, conn: sqlite3.Connection, source_url: str) -> int:
        if not source_url:
            return 0
        conn.execute("DELETE FROM documents WHERE source_url = ?", (source_url,))
        if self._fts_available(conn):
            try:
                conn.execute("DELETE FROM documents_fts WHERE source_url = ?", (source_url,))
            except sqlite3.Error:
                pass
        return 1

    def _fts_available(self, conn: sqlite3.Connection) -> bool:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'documents_fts'"
        ).fetchone()
        return row is not None

    def _delete_pdf_file(self, pdf_path: str) -> bool:
        raw_path = str(pdf_path or "").strip()
        if not raw_path:
            return False

        path = Path(raw_path).expanduser()
        if not path.is_absolute():
            path = (self.settings.base_dir / path).resolve(strict=False)
        else:
            path = path.resolve(strict=False)

        downloads_root = self.settings.downloads_dir.resolve(strict=False)
        try:
            path.relative_to(downloads_root)
        except ValueError:
            LOGGER.warning("Skipping file deletion outside downloads dir: %s", path)
            return False

        if not path.exists() or not path.is_file():
            return False

        path.unlink()
        self._prune_empty_directories(path.parent, downloads_root)
        return True

    def _prune_empty_directories(self, start_dir: Path, stop_dir: Path) -> None:
        current = start_dir.resolve(strict=False)
        stop_dir = stop_dir.resolve(strict=False)
        while current != stop_dir:
            if not current.exists() or not current.is_dir():
                return
            try:
                next(current.iterdir())
                return
            except StopIteration:
                current.rmdir()
                current = current.parent

    def _distinct_values(self, rows: list[dict], key: str) -> list[dict[str, str]]:
        values = sorted({str(row.get(key) or "").strip() for row in rows if str(row.get(key) or "").strip()})
        return [{"value": value, "label": value} for value in values]

    def _normalize_ids(self, values: list[int] | tuple[int, ...]) -> list[int]:
        normalized: list[int] = []
        for value in values:
            try:
                int_value = int(value)
            except (TypeError, ValueError):
                continue
            if int_value not in normalized:
                normalized.append(int_value)
        return normalized

    def _now(self) -> str:
        return datetime.utcnow().isoformat(timespec="seconds") + "Z"
