from __future__ import annotations

import sqlite3
from pathlib import Path

import vietcase.db.sqlite as sqlite_module
import vietcase.services.job_service as job_service_module
from vietcase.core.config import Settings
from vietcase.core.presentation import (
    build_document_display_title,
    format_display_date,
    format_display_datetime,
    with_document_display_fields,
)
from vietcase.db.migrations import init_db
from vietcase.services.job_service import JobService
from vietcase.services.pdf_service import PdfService


class DummySearchService:
    def iter_all_results(self, filters: dict, context=None):
        yield from ()


class DummyDetailService:
    def fetch(self, source_url: str, context=None) -> dict:
        return {"source_url": source_url}


class DummyPdfService:
    def save_pdf(self, pdf_url: str, job_folder, document_number: str = "") -> dict[str, str]:
        return {
            "pdf_path": str(job_folder / "dummy.pdf"),
            "file_name_original": "dummy.pdf",
            "pdf_text": "Bản án số 116/2026/DS-PT ngày 09/02/2026",
            "resolved_document_number": document_number or "116/2026/DS-PT",
        }


def configure_temp_settings(tmp_path, monkeypatch) -> Settings:
    settings = Settings(base_dir=tmp_path)
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.downloads_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(sqlite_module, "get_settings", lambda: settings)
    monkeypatch.setattr(job_service_module, "get_settings", lambda: settings)
    return settings


def test_format_display_date_supports_iso_and_vn_formats() -> None:
    assert format_display_date("2026-03-29") == "29/03/2026"
    assert format_display_date("29/03/2026") == "29/03/2026"
    assert format_display_date("29-03-2026") == "29/03/2026"
    assert format_display_date("29.03.2026") == "29/03/2026"


def test_format_display_datetime_converts_utc_to_utc_plus_7() -> None:
    assert format_display_datetime("2026-04-16T00:18:29Z") == "16/04/2026 07:18:29"
    assert format_display_datetime("2026-04-16 00:18:29") == "16/04/2026 07:18:29"


def test_build_document_display_title_prefers_real_title() -> None:
    document = {
        "title": "Bản án dân sự phúc thẩm số 18/2026/DS-PT",
        "document_type": "Bản án",
        "document_number": "18/2026/DS-PT",
    }
    assert build_document_display_title(document) == document["title"]


def test_with_document_display_fields_builds_fallback_title_from_metadata() -> None:
    payload = with_document_display_fields(
        {
            "document_type": "Quyết định",
            "document_number": "13/2026/QĐ-PT",
            "issued_date": "2026-03-27",
            "published_date": "2026-04-11",
            "court_name": "Tòa Phúc thẩm Tòa án nhân dân tối cao tại Hà Nội",
        }
    )
    assert payload["display_title"] == (
        "Quyết định: số 13/2026/QĐ-PT ngày 27/03/2026 của "
        "Tòa Phúc thẩm Tòa án nhân dân tối cao tại Hà Nội (11.04.2026)"
    )
    assert payload["issued_date_display"] == "27/03/2026"
    assert payload["published_date_display"] == "11/04/2026"


def test_pdf_file_name_prefers_document_number() -> None:
    service = PdfService()
    assert service._build_file_name("116/2026/DS-PT", "https://example.com/sample.pdf") == "116-2026-DS-PT.pdf"
    assert service._build_file_name("13/2026/QĐ-PT", "https://example.com/sample.pdf") == "13-2026-QĐ-PT.pdf"


def test_pdf_document_number_is_extracted_from_pdf_text() -> None:
    service = PdfService()
    assert service._extract_document_number_from_pdf_text("Bản án số 116/2026/DS-PT ngày 09/02/2026") == "116/2026/DS-PT"
    assert service._extract_document_number_from_pdf_text("Quyết định số 13/2026/QĐ-PT ngày 27/03/2026") == "13/2026/QĐ-PT"


def test_init_db_adds_search_snapshot_columns_and_document_files_table(tmp_path, monkeypatch) -> None:
    settings = configure_temp_settings(tmp_path, monkeypatch)
    init_db()

    with sqlite3.connect(settings.db_path) as conn:
        document_columns = {row[1] for row in conn.execute("PRAGMA table_info(documents)").fetchall()}
        job_item_columns = {row[1] for row in conn.execute("PRAGMA table_info(job_items)").fetchall()}
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}

    assert "title" in document_columns
    assert "source_card_text" in document_columns
    assert "pdf_text" in document_columns
    assert "search_text_normalized" in document_columns
    assert "title" in job_item_columns
    assert "source_card_text" in job_item_columns
    assert "document_files" in tables


def test_create_job_persists_item_title_and_source_card_text(tmp_path, monkeypatch) -> None:
    configure_temp_settings(tmp_path, monkeypatch)
    init_db()
    service = JobService(DummySearchService(), DummyDetailService(), DummyPdfService())

    job = service.create_job(
        mode="preview_then_download",
        job_name="Tải các mục đã chọn",
        items=[
            {
                "source_url": "https://example.com/doc-1",
                "document_id": "doc-1",
                "title": "Bản án dân sự phúc thẩm số 12/2026/DS-PT",
                "document_type": "Bản án",
                "document_number": "12/2026/DS-PT",
                "source_card_text": "Quan hệ pháp luật: Tranh chấp hợp đồng",
            }
        ],
    )

    item = service.list_job_items(int(job["id"]))[0]
    assert item["title"] == "Bản án dân sự phúc thẩm số 12/2026/DS-PT"
    assert item["source_card_text"] == "Quan hệ pháp luật: Tranh chấp hợp đồng"


def test_mark_item_completed_persists_canonical_document_and_file_copy(tmp_path, monkeypatch) -> None:
    settings = configure_temp_settings(tmp_path, monkeypatch)
    init_db()
    service = JobService(DummySearchService(), DummyDetailService(), DummyPdfService())

    job = service.create_job(
        mode="preview_then_download",
        job_name="Tải các mục đã chọn",
        items=[
            {
                "source_url": "https://example.com/doc-2",
                "document_id": "doc-2",
                "title": "Tiêu đề từ preview",
                "document_type": "Quyết định",
                "document_number": "15/2026/QĐ-PT",
                "issued_date": "2026-03-27",
                "court_name": "Tòa án nhân dân cấp cao tại Hà Nội",
                "source_card_text": "Quan hệ pháp luật: Tranh chấp hợp đồng",
                "precedent_applied": "Không",
            }
        ],
    )
    item = service.list_job_items(int(job["id"]))[0]
    pdf_path = settings.downloads_dir / "16-04-2026-09-14" / "15-2026-QĐ-PT.pdf"
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.write_bytes(b"%PDF-1.4")

    service._mark_item_completed(
        int(job["id"]),
        item,
        {
            "source_url": "https://example.com/doc-2",
            "document_id": "doc-2",
            "title": "",
            "document_type": "Quyết định",
            "document_number": "15/2026/QĐ-PT",
            "issued_date": "2026-03-27",
            "published_date": "2026-04-11",
            "court_name": "Tòa án nhân dân cấp cao tại Hà Nội",
            "adjudication_level": "Phúc thẩm",
            "case_style": "Dân sự",
            "legal_relation": "Tranh chấp hợp đồng",
            "summary_text": "Tóm tắt vụ việc",
            "precedent_applied": "Không",
            "correction_count": "0",
            "precedent_vote_count": "0",
            "pdf_url": "https://example.com/doc-2.pdf",
        },
        {
            "pdf_path": str(pdf_path),
            "file_name_original": "15-2026-QĐ-PT.pdf",
            "pdf_text": "Quyết định số 15/2026/QĐ-PT ngày 27/03/2026",
            "resolved_document_number": "15/2026/QĐ-PT",
        },
        "requests",
        pdf_path.parent,
    )

    rows = service.search_document_files(page=1, page_size=10)
    assert rows["total"] == 1
    document = rows["items"][0]
    assert document["title"] == "Tiêu đề từ preview"
    assert document["document_number"] == "15/2026/QĐ-PT"
    assert document["precedent_applied"] == "Không"
    assert "tranh chap hop dong" in document["search_text_normalized"]
    assert document["file_name_original"] == "15-2026-QĐ-PT.pdf"


def test_search_document_files_matches_without_diacritics(tmp_path, monkeypatch) -> None:
    settings = configure_temp_settings(tmp_path, monkeypatch)
    init_db()
    service = JobService(DummySearchService(), DummyDetailService(), DummyPdfService())

    pdf_path = settings.downloads_dir / "16-04-2026-09-15" / "126-2026-DS-PT.pdf"
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.write_bytes(b"%PDF-1.4")

    with sqlite3.connect(settings.db_path) as conn:
        conn.execute(
            """
            INSERT INTO documents (
                source_url, document_id, title, document_type, document_number,
                issued_date, published_date, court_name, adjudication_level,
                case_style, legal_relation, summary_text, source_card_text,
                pdf_text, search_text_normalized, pdf_path, file_name_original,
                download_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "https://example.com/doc-3",
                "doc-3",
                "Bản án dân sự phúc thẩm số 126/2026/DS-PT",
                "Bản án",
                "126/2026/DS-PT",
                "2026-02-25",
                "2026-03-22",
                "Tòa Phúc thẩm Tòa án nhân dân tối cao tại Thành phố Hồ Chí Minh",
                "Phúc thẩm",
                "Dân sự",
                "Tranh chấp thừa kế quyền sử dụng đất",
                "Tóm tắt vụ việc",
                "Quan hệ pháp luật: Tranh chấp thừa kế quyền sử dụng đất",
                "Bản án số 126/2026/DS-PT ngày 25/02/2026",
                "ban an dan su phuc tham so 126/2026/ds-pt tranh chap thua ke quyen su dung dat",
                str(pdf_path),
                "126-2026-DS-PT.pdf",
                "completed",
            ),
        )
        conn.execute(
            "INSERT INTO document_files (document_source_url, job_id, job_folder, pdf_path, file_name_original) VALUES (?, ?, ?, ?, ?)",
            (
                "https://example.com/doc-3",
                1,
                str(pdf_path.parent),
                str(pdf_path),
                "126-2026-DS-PT.pdf",
            ),
        )
        conn.commit()

    payload = service.search_document_files(q="tranh chap thua ke", page=1, page_size=10)
    assert payload["total"] == 1
    assert payload["items"][0]["document_number"] == "126/2026/DS-PT"


def test_delete_document_removes_file_copy_and_canonical_when_last_copy(tmp_path, monkeypatch) -> None:
    settings = configure_temp_settings(tmp_path, monkeypatch)
    init_db()
    service = JobService(DummySearchService(), DummyDetailService(), DummyPdfService())

    pdf_path = settings.downloads_dir / "16-04-2026-09-16" / "sample.pdf"
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.write_bytes(b"%PDF-1.4")

    with sqlite3.connect(settings.db_path) as conn:
        conn.execute(
            "INSERT INTO documents (source_url, document_id, title, pdf_path, download_status) VALUES (?, ?, ?, ?, ?)",
            ("https://example.com/doc-1", "doc-1", "Tài liệu 1", str(pdf_path), "completed"),
        )
        conn.execute(
            "INSERT INTO document_files (document_source_url, job_id, job_folder, pdf_path, file_name_original) VALUES (?, ?, ?, ?, ?)",
            ("https://example.com/doc-1", 1, str(pdf_path.parent), str(pdf_path), "sample.pdf"),
        )
        file_id = int(conn.execute("SELECT id FROM document_files WHERE document_source_url = ?", ("https://example.com/doc-1",)).fetchone()[0])
        conn.commit()

    result = service.delete_document(file_id)

    assert result["deleted_count"] == 1
    assert result["deleted_file_count"] == 1
    assert pdf_path.exists() is False
    assert service.search_document_files(page=1, page_size=10)["items"] == []
    assert service.list_documents() == []


def test_delete_document_keeps_canonical_and_file_when_other_copy_exists(tmp_path, monkeypatch) -> None:
    settings = configure_temp_settings(tmp_path, monkeypatch)
    init_db()
    service = JobService(DummySearchService(), DummyDetailService(), DummyPdfService())

    pdf_path_a = settings.downloads_dir / "16-04-2026-09-17" / "shared-a.pdf"
    pdf_path_b = settings.downloads_dir / "16-04-2026-09-18" / "shared-b.pdf"
    pdf_path_a.parent.mkdir(parents=True, exist_ok=True)
    pdf_path_b.parent.mkdir(parents=True, exist_ok=True)
    pdf_path_a.write_bytes(b"%PDF-1.4")
    pdf_path_b.write_bytes(b"%PDF-1.4")

    with sqlite3.connect(settings.db_path) as conn:
        conn.execute(
            "INSERT INTO documents (source_url, document_id, title, pdf_path, download_status) VALUES (?, ?, ?, ?, ?)",
            ("https://example.com/doc-a", "doc-a", "Tài liệu A", str(pdf_path_a), "completed"),
        )
        conn.execute(
            "INSERT INTO document_files (document_source_url, job_id, job_folder, pdf_path, file_name_original) VALUES (?, ?, ?, ?, ?)",
            ("https://example.com/doc-a", 1, str(pdf_path_a.parent), str(pdf_path_a), "shared-a.pdf"),
        )
        conn.execute(
            "INSERT INTO document_files (document_source_url, job_id, job_folder, pdf_path, file_name_original) VALUES (?, ?, ?, ?, ?)",
            ("https://example.com/doc-a", 2, str(pdf_path_b.parent), str(pdf_path_b), "shared-b.pdf"),
        )
        file_id = int(conn.execute("SELECT id FROM document_files WHERE pdf_path = ?", (str(pdf_path_a),)).fetchone()[0])
        conn.commit()

    result = service.delete_document(file_id)

    assert result["deleted_count"] == 1
    assert pdf_path_a.exists() is False
    assert pdf_path_b.exists() is True
    assert len(service.list_documents()) == 1
    assert service.search_document_files(page=1, page_size=10)["total"] == 1

def test_job_folder_path_uses_timestamp_and_suffix_on_collision(tmp_path, monkeypatch) -> None:
    configure_temp_settings(tmp_path, monkeypatch)
    init_db()
    service = JobService(DummySearchService(), DummyDetailService(), DummyPdfService())

    class FixedDateTime:
        @classmethod
        def now(cls):
            from datetime import datetime
            return datetime(2026, 4, 16, 9, 14, 0)

    monkeypatch.setattr(job_service_module, "datetime", FixedDateTime)
    first_folder = service._job_folder_path()
    first_folder.mkdir(parents=True, exist_ok=True)
    second_folder = service._job_folder_path()

    assert first_folder.name == "16-04-2026-09-14"
    assert second_folder.name == "16-04-2026-09-14__2"
