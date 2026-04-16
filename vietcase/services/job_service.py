from __future__ import annotations

import json
import logging
import threading
from datetime import datetime
from pathlib import Path

from vietcase.core.config import get_settings
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
        with connect() as conn:
            cursor = conn.execute(
                "INSERT INTO download_jobs (mode, job_name, filters_json, status, source_mode, source_mode_reason, job_folder, last_processed_page, tls_mode) VALUES (?, ?, ?, 'queued', ?, 'initial_default', ?, 0, 'secure')",
                (mode, job_name, json.dumps(filters, ensure_ascii=False), self.settings.download_source_mode, str(self._job_folder_path(None))),
            )
            job_id = int(cursor.lastrowid)
            job_folder = self._job_folder_path(job_id)
            conn.execute("UPDATE download_jobs SET job_folder = ? WHERE id = ?", (str(job_folder), job_id))
            for item in items:
                conn.execute(
                    "INSERT OR IGNORE INTO job_items (job_id, source_url, document_id, document_type, document_number, issued_date, court_name, case_style, summary_text, selected, page_index, result_index) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        job_id,
                        item.get("source_url", ""),
                        item.get("document_id", ""),
                        item.get("document_type", ""),
                        item.get("document_number", ""),
                        item.get("issued_date", ""),
                        item.get("court_name", ""),
                        item.get("case_style", ""),
                        item.get("summary_text", ""),
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
        with connect() as conn:
            conn.execute("UPDATE download_jobs SET status = 'queued', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (job_id,))
            conn.commit()
        self.start_job(job_id)

    def pause_job(self, job_id: int) -> None:
        with connect() as conn:
            conn.execute("UPDATE download_jobs SET status = 'paused', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (job_id,))
            conn.commit()

    def cancel_job(self, job_id: int) -> None:
        with connect() as conn:
            conn.execute("UPDATE download_jobs SET status = 'cancelled', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (job_id,))
            conn.commit()

    def list_jobs(self) -> list[dict]:
        return [dict(row) for row in execute_fetchall("SELECT * FROM download_jobs ORDER BY id DESC")]

    def get_job(self, job_id: int) -> dict:
        row = execute_fetchone("SELECT * FROM download_jobs WHERE id = ?", (job_id,))
        return dict(row) if row else {}

    def list_job_items(self, job_id: int) -> list[dict]:
        return [dict(row) for row in execute_fetchall("SELECT * FROM job_items WHERE job_id = ? ORDER BY page_index, result_index, id", (job_id,))]

    def list_documents(self) -> list[dict]:
        return [dict(row) for row in execute_fetchall("SELECT * FROM documents ORDER BY id DESC")]

    def _run_job(self, job_id: int) -> None:
        job = self.get_job(job_id)
        if not job:
            return
        filters = json.loads(job.get("filters_json") or "{}")
        download_ctx = SourceContext(source_mode=job.get("source_mode") or self.settings.download_source_mode, job_id=job_id)
        job_folder = Path(job.get("job_folder") or self._job_folder_path(job_id))
        job_folder.mkdir(parents=True, exist_ok=True)
        self._update_job(job_id, status="running", started_at=self._now())

        if filters and not self.list_job_items(job_id):
            self._populate_items_from_filters(job_id, filters)

        for item in self.list_job_items(job_id):
            latest_job = self.get_job(job_id)
            if latest_job.get("status") in {"paused", "cancelled"}:
                LOGGER.info("Stopping job %s because status is %s", job_id, latest_job.get("status"))
                return
            if item.get("status") == "completed":
                continue
            try:
                detail = self.detail_service.fetch(item["source_url"], context=download_ctx)
                if not detail.get("pdf_url"):
                    raise ValueError("Kh?ng t?m th?y ???ng d?n PDF trong trang chi ti?t")
                saved = self.pdf_service.save_pdf(detail["pdf_url"], detail.get("court_name", ""), detail.get("document_type", ""), job_folder, detail.get("document_number", "") or item.get("document_number", ""))
                self._mark_item_completed(job_id, item, detail, saved, download_ctx.source_mode)
            except Exception as exc:
                LOGGER.exception("Failed to process item %s in job %s", item.get("id"), job_id)
                self._mark_item_failed(job_id, item["id"], str(exc), download_ctx.source_mode)

        self._update_job(job_id, status="completed", finished_at=self._now(), source_mode=download_ctx.source_mode, source_mode_reason="auto_fallback_detected" if download_ctx.source_mode == "playwright" else "initial_default")

    def _populate_items_from_filters(self, job_id: int, filters: dict[str, object]) -> None:
        search_ctx = SourceContext(source_mode=self.settings.search_source_mode, job_id=job_id)
        total_items = 0
        total_pages = 0
        total_results = 0
        for preview in self.search_service.iter_all_results(filters, context=search_ctx):
            total_pages = preview.total_pages
            total_results = preview.total_results
            with connect() as conn:
                for item in preview.results:
                    conn.execute(
                        "INSERT OR IGNORE INTO job_items (job_id, source_url, document_id, document_type, document_number, issued_date, court_name, case_style, summary_text, selected, page_index, result_index) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            job_id,
                            item.get("source_url", ""),
                            item.get("document_id", ""),
                            item.get("document_type", ""),
                            item.get("document_number", ""),
                            item.get("issued_date", ""),
                            item.get("court_name", ""),
                            item.get("case_style", ""),
                            item.get("summary_text", ""),
                            1,
                            int(item.get("page_index", 1) or 1),
                            int(item.get("result_index", 0) or 0),
                        ),
                    )
                conn.execute("UPDATE download_jobs SET items_total = (SELECT COUNT(*) FROM job_items WHERE job_id = ?), total_results_estimate = ?, total_pages_estimate = ?, last_processed_page = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (job_id, total_results, total_pages, preview.current_page, job_id))
                conn.commit()
            total_items += len(preview.results)

    def _mark_item_completed(self, job_id: int, item: dict, detail: dict, saved: dict, source_mode: str) -> None:
        with connect() as conn:
            conn.execute(
                "UPDATE job_items SET pdf_url = ?, pdf_path = ?, status = 'completed', error_message = NULL, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (detail.get("pdf_url", ""), saved.get("pdf_path", ""), item["id"]),
            )
            conn.execute(
                "INSERT INTO documents (source_url, document_id, document_type, document_number, issued_date, published_date, court_name, adjudication_level, case_style, legal_relation, summary_text, pdf_url, pdf_path, file_name_original, download_status, downloaded_at, last_job_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'completed', ?, ?) ON CONFLICT(source_url) DO UPDATE SET document_id=excluded.document_id, document_type=excluded.document_type, document_number=excluded.document_number, issued_date=excluded.issued_date, published_date=excluded.published_date, court_name=excluded.court_name, adjudication_level=excluded.adjudication_level, case_style=excluded.case_style, legal_relation=excluded.legal_relation, summary_text=excluded.summary_text, pdf_url=excluded.pdf_url, pdf_path=excluded.pdf_path, file_name_original=excluded.file_name_original, download_status='completed', downloaded_at=excluded.downloaded_at, last_job_id=excluded.last_job_id, updated_at=CURRENT_TIMESTAMP",
                (
                    detail.get("source_url", item.get("source_url", "")),
                    detail.get("document_id", item.get("document_id", "")),
                    detail.get("document_type", item.get("document_type", "")),
                    detail.get("document_number", item.get("document_number", "")),
                    detail.get("issued_date", item.get("issued_date", "")),
                    detail.get("published_date", ""),
                    detail.get("court_name", item.get("court_name", "")),
                    detail.get("adjudication_level", ""),
                    detail.get("case_style", item.get("case_style", "")),
                    detail.get("legal_relation", ""),
                    detail.get("summary_text", item.get("summary_text", "")),
                    detail.get("pdf_url", ""),
                    saved.get("pdf_path", ""),
                    saved.get("file_name_original", ""),
                    self._now(),
                    job_id,
                ),
            )
            conn.execute("UPDATE download_jobs SET items_completed = COALESCE(items_completed, 0) + 1, source_mode = ?, source_mode_reason = ?, tls_mode = COALESCE(tls_mode, 'secure'), updated_at = CURRENT_TIMESTAMP WHERE id = ?", (source_mode, "auto_fallback_detected" if source_mode == "playwright" else "initial_default", job_id))
            conn.commit()

    def _mark_item_failed(self, job_id: int, item_id: int, error_message: str, source_mode: str) -> None:
        with connect() as conn:
            conn.execute("UPDATE job_items SET status = 'failed', error_message = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (error_message, item_id))
            conn.execute("UPDATE download_jobs SET items_failed = COALESCE(items_failed, 0) + 1, source_mode = ?, source_mode_reason = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (source_mode, "auto_fallback_detected" if source_mode == "playwright" else "initial_default", job_id))
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

    def _job_folder_path(self, job_id: int | None) -> Path:
        name = str(job_id) if job_id is not None else "pending"
        return self.settings.downloads_dir / name

    def _now(self) -> str:
        return datetime.utcnow().isoformat(timespec="seconds") + "Z"
