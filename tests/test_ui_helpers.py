from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace

import vietcase.api.routes_documents as routes_documents
import vietcase.db.sqlite as sqlite_module
import vietcase.services.job_service as job_service_module
from vietcase.core.config import Settings
from vietcase.core.presentation import (
    build_document_display_title,
    format_display_date,
    format_display_datetime,
    with_document_display_fields,
    with_job_display_fields,
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
    def save_pdf(
        self,
        pdf_url: str,
        job_folder,
        document_number: str = "",
        *,
        title: str = "",
        source_card_text: str = "",
    ) -> dict[str, str]:
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


def test_with_job_display_fields_hides_non_delete_actions_for_completed_jobs() -> None:
    payload = with_job_display_fields({"status": "completed", "created_at": "2026-04-18T01:02:03Z"})
    assert payload["can_resume"] is False
    assert payload["can_pause"] is False
    assert payload["can_cancel"] is False
    assert payload["created_at_display"] == "18/04/2026 08:02:03"


def test_with_job_display_fields_standardizes_actions_by_status() -> None:
    paused = with_job_display_fields({"status": "paused"})
    interrupted = with_job_display_fields({"status": "interrupted"})
    running = with_job_display_fields({"status": "running"})
    queued = with_job_display_fields({"status": "queued"})
    cancelled = with_job_display_fields({"status": "cancelled"})

    assert paused["can_resume"] is True
    assert paused["can_pause"] is False
    assert paused["can_cancel"] is True

    assert interrupted["can_resume"] is True
    assert interrupted["can_pause"] is False
    assert interrupted["can_cancel"] is True

    assert running["can_resume"] is False
    assert running["can_pause"] is True
    assert running["can_cancel"] is True

    assert queued["can_resume"] is False
    assert queued["can_pause"] is True
    assert queued["can_cancel"] is True

    assert cancelled["can_resume"] is False
    assert cancelled["can_pause"] is False
    assert cancelled["can_cancel"] is False


def test_with_job_display_fields_adds_vietnamese_status_label() -> None:
    assert with_job_display_fields({"status": "queued"})["status_display"] == "Đang chờ"
    assert with_job_display_fields({"status": "running"})["status_display"] == "Đang chạy"
    assert with_job_display_fields({"status": "paused"})["status_display"] == "Tạm dừng"
    assert with_job_display_fields({"status": "cancelled"})["status_display"] == "Đã hủy"
    assert with_job_display_fields({"status": "completed"})["status_display"] == "Hoàn tất"
    assert with_job_display_fields({"status": "interrupted"})["status_display"] == "Bị gián đoạn"


def test_search_index_template_uses_two_column_layout() -> None:
    template = Path("vietcase/templates/index.html").read_text(encoding="utf-8")
    assert 'class="search-shell"' in template
    assert 'class="search-sidebar"' in template
    assert 'class="search-results-column"' in template
    assert template.index('class="search-sidebar"') < template.index('class="search-results-column"')
    assert template.index("search-results-column") < template.index("search-summary-panel")
    assert template.index("search-summary-panel") < template.index("search-results-panel")
    assert template.index('id="download-now"') > template.index("search-results-panel")
    assert 'id="download-now"' not in template.split("</form>", 1)[0]


def test_search_layout_css_defines_two_column_shell_and_mobile_fallback() -> None:
    css = Path("vietcase/static/css/app.css").read_text(encoding="utf-8")
    assert ".search-shell" in css
    assert ".search-sidebar" in css
    assert ".search-results-column" in css
    assert "max-width: 1480px;" in css
    assert "grid-template-columns: minmax(340px, 0.9fr) minmax(0, 2fr);" in css
    assert ".search-summary-panel .summary-item" in css
    assert ".search-sidebar .panel {" in css
    assert ".search-sidebar input[type=\"text\"]," in css


def test_pdf_file_name_prefers_document_number() -> None:
    service = PdfService()
    assert service._build_file_name("116/2026/DS-PT", "https://example.com/sample.pdf") == "116-2026-DS-PT.pdf"
    assert service._build_file_name("13/2026/QĐ-PT", "https://example.com/sample.pdf") == "13-2026-QĐ-PT.pdf"


def test_pdf_document_number_is_extracted_from_pdf_text() -> None:
    service = PdfService()
    assert service._extract_document_number_from_pdf_text("Bản án số 116/2026/DS-PT ngày 09/02/2026") == "116/2026/DS-PT"
    assert service._extract_document_number_from_pdf_text("Quyết định số 13/2026/QĐ-PT ngày 27/03/2026") == "13/2026/QĐ-PT"


def test_pdf_document_number_stops_before_national_motto_text() -> None:
    service = PdfService()
    text = "Số: 01/2026/QĐ-PT CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM Độc lập - Tự do - Hạnh phúc Đà Nẵng, ngày 19 tháng 1 năm 2026"
    assert service._extract_document_number_from_pdf_text(text) == "01/2026/QĐ-PT"


def test_pdf_document_number_prefers_header_number_over_body_reference() -> None:
    service = PdfService()
    text = (
        "TÒA PHÚC THẨM TÒA ÁN NHÂN DÂN TỐI CAO TẠI ĐÀ NẴNG "
        "Số: 02/2026/QĐ-DSPT CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM "
        "Độc lập - Tự do - Hạnh phúc Đà Nẵng, ngày 20 tháng 01 năm 2026 "
        "QUYẾT ĐỊNH GIẢI QUYẾT VIỆC KHÁNG CÁO "
        "Trong hồ sơ khác có Quyết định số 119 A/QĐ-CA ngày 10/11/2025."
    )
    assert service._extract_document_number_from_pdf_text(text) == "02/2026/QĐ-DSPT"


def test_pdf_document_number_reliability_rejects_weak_short_numbers() -> None:
    service = PdfService()
    assert service._is_reliable_document_number("12/2026/DS-PT") is True
    assert service._is_reliable_document_number("02/2026/QĐ-DSPT") is True
    assert service._is_reliable_document_number("03") is False
    assert service._is_reliable_document_number("55") is False
    assert service._is_reliable_document_number("06/2026") is False


def test_pdf_resolved_document_number_uses_cleaned_strong_metadata_fallback() -> None:
    service = PdfService()
    assert service._resolve_document_number("", "12/2026/QĐPT-DS Hà Nội,") == "12/2026/QĐPT-DS"


def test_pdf_file_name_falls_back_to_cleaned_title_when_number_missing() -> None:
    service = PdfService()
    fallback = service._build_metadata_fallback_name("Bản án số: 10 ngày 09/01/2026 (26.03.2026)", "")
    assert fallback == "Bản án số: 10 ngày 09/01/2026"
    assert service._build_file_name("", "https://example.com/sample_6.pdf", fallback_title=fallback) == "Bản án số- 10 ngày 09-01-2026.pdf"


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


def test_search_document_files_uses_derived_document_type_for_options_and_filter(tmp_path, monkeypatch) -> None:
    settings = configure_temp_settings(tmp_path, monkeypatch)
    init_db()
    service = JobService(DummySearchService(), DummyDetailService(), DummyPdfService())

    pdf_a = settings.downloads_dir / "18-04-2026-11-00" / "ban-an.pdf"
    pdf_b = settings.downloads_dir / "18-04-2026-11-00" / "quyet-dinh.pdf"
    pdf_a.parent.mkdir(parents=True, exist_ok=True)
    pdf_a.write_bytes(b"%PDF-1.4")
    pdf_b.write_bytes(b"%PDF-1.4")

    with sqlite3.connect(settings.db_path) as conn:
        conn.execute(
            """
            INSERT INTO documents (
                source_url, document_id, title, document_type, issued_date, court_name,
                case_style, legal_relation, source_card_text, search_text_normalized, pdf_path,
                file_name_original, download_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "https://example.com/doc-ban-an",
                "doc-ban-an",
                "Bản án số: 10 ngày 09/01/2026",
                "Quyết định",
                "2026-01-09",
                "Tòa án A",
                "Dân sự",
                "Tranh chấp quyền sử dụng đất",
                "Bản án: số 10 ngày 09/01/2026 của Tòa án A",
                "ban an so 10 ngay 09/01/2026",
                str(pdf_a),
                "ban-an.pdf",
                "completed",
            ),
        )
        conn.execute(
            """
            INSERT INTO documents (
                source_url, document_id, title, document_type, issued_date, court_name,
                case_style, legal_relation, source_card_text, search_text_normalized, pdf_path,
                file_name_original, download_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "https://example.com/doc-quyet-dinh",
                "doc-quyet-dinh",
                "Quyết định số 15/2026/QĐ-PT ngày 29/03/2026",
                "Quyết định",
                "2026-03-29",
                "Tòa án B",
                "Dân sự",
                "Tranh chấp cổ phần",
                "Quyết định: số 15/2026/QĐ-PT của Tòa án B",
                "quyet dinh so 15/2026/qd-pt",
                str(pdf_b),
                "quyet-dinh.pdf",
                "completed",
            ),
        )
        conn.execute(
            "INSERT INTO document_files (document_source_url, job_id, job_folder, pdf_path, file_name_original) VALUES (?, ?, ?, ?, ?)",
            ("https://example.com/doc-ban-an", 1, str(pdf_a.parent), str(pdf_a), "ban-an.pdf"),
        )
        conn.execute(
            "INSERT INTO document_files (document_source_url, job_id, job_folder, pdf_path, file_name_original) VALUES (?, ?, ?, ?, ?)",
            ("https://example.com/doc-quyet-dinh", 1, str(pdf_b.parent), str(pdf_b), "quyet-dinh.pdf"),
        )
        conn.commit()

    payload = service.search_document_files(page=1, page_size=10)
    assert payload["filter_options"]["document_type"] == [
        {"value": "Bản án", "label": "Bản án"},
        {"value": "Quyết định", "label": "Quyết định"},
    ]

    judgments = service.search_document_files(document_type="Bản án", page=1, page_size=10)
    assert judgments["total"] == 1
    assert judgments["items"][0]["file_name_original"] == "ban-an.pdf"


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


def test_cancelled_job_cannot_be_resumed_and_paused_job_can_be_resumed(tmp_path, monkeypatch) -> None:
    configure_temp_settings(tmp_path, monkeypatch)
    init_db()
    service = JobService(DummySearchService(), DummyDetailService(), DummyPdfService())
    monkeypatch.setattr(service, "start_job", lambda job_id: None)

    cancelled = service.create_job(mode="preview_then_download", job_name="Cancelled job")
    paused = service.create_job(mode="preview_then_download", job_name="Paused job")

    with sqlite3.connect(service.settings.db_path) as conn:
        conn.execute("UPDATE download_jobs SET status = 'cancelled' WHERE id = ?", (int(cancelled["id"]),))
        conn.execute("UPDATE download_jobs SET status = 'paused' WHERE id = ?", (int(paused["id"]),))
        conn.commit()

    service.resume_job(int(cancelled["id"]))
    service.resume_job(int(paused["id"]))

    assert service.get_job(int(cancelled["id"]))["status"] == "cancelled"
    assert service.get_job(int(paused["id"]))["status"] == "queued"


def test_pause_and_cancel_follow_standardized_transitions(tmp_path, monkeypatch) -> None:
    configure_temp_settings(tmp_path, monkeypatch)
    init_db()
    service = JobService(DummySearchService(), DummyDetailService(), DummyPdfService())

    running = service.create_job(mode="preview_then_download", job_name="Running job")
    paused = service.create_job(mode="preview_then_download", job_name="Paused job")
    completed = service.create_job(mode="preview_then_download", job_name="Completed job")

    with sqlite3.connect(service.settings.db_path) as conn:
        conn.execute("UPDATE download_jobs SET status = 'running' WHERE id = ?", (int(running["id"]),))
        conn.execute("UPDATE download_jobs SET status = 'paused' WHERE id = ?", (int(paused["id"]),))
        conn.execute("UPDATE download_jobs SET status = 'completed' WHERE id = ?", (int(completed["id"]),))
        conn.commit()

    service.pause_job(int(running["id"]))
    service.pause_job(int(paused["id"]))
    service.cancel_job(int(paused["id"]))
    service.cancel_job(int(completed["id"]))

    assert service.get_job(int(running["id"]))["status"] == "paused"
    assert service.get_job(int(paused["id"]))["status"] == "cancelled"
    assert service.get_job(int(completed["id"]))["status"] == "completed"


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


def test_completed_job_actions_are_noop(tmp_path, monkeypatch) -> None:
    configure_temp_settings(tmp_path, monkeypatch)
    init_db()
    service = JobService(DummySearchService(), DummyDetailService(), DummyPdfService())

    job = service.create_job(mode="preview_then_download", job_name="Job hoàn tất", items=[])
    job_id = int(job["id"])
    with sqlite3.connect(service.settings.db_path) as conn:
        conn.execute("UPDATE download_jobs SET status = 'completed' WHERE id = ?", (job_id,))
        conn.commit()

    service.resume_job(job_id)
    assert service.get_job(job_id)["status"] == "completed"

    service.pause_job(job_id)
    assert service.get_job(job_id)["status"] == "completed"

    service.cancel_job(job_id)
    assert service.get_job(job_id)["status"] == "completed"


def test_search_page_redirects_to_jobs_after_create_job() -> None:
    js = Path("vietcase/static/js/app.js").read_text(encoding="utf-8")
    assert 'window.location.assign("/jobs");' in js


def test_open_file_allows_unicode_filename_in_inline_content_disposition(tmp_path, monkeypatch) -> None:
    settings = configure_temp_settings(tmp_path, monkeypatch)
    init_db()
    service = JobService(DummySearchService(), DummyDetailService(), DummyPdfService())

    pdf_path = settings.downloads_dir / "18-04-2026-11-00" / "12-2026-QĐPT-DS.pdf"
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.write_bytes(b"%PDF-1.4")

    with sqlite3.connect(settings.db_path) as conn:
        conn.execute(
            "INSERT INTO documents (source_url, document_id, title, pdf_path, file_name_original, download_status) VALUES (?, ?, ?, ?, ?, ?)",
            (
                "https://example.com/doc-unicode",
                "doc-unicode",
                "Quyết định số 12/2026/QĐPT-DS",
                str(pdf_path),
                pdf_path.name,
                "completed",
            ),
        )
        conn.execute(
            "INSERT INTO document_files (document_source_url, job_id, job_folder, pdf_path, file_name_original) VALUES (?, ?, ?, ?, ?)",
            ("https://example.com/doc-unicode", 1, str(pdf_path.parent), str(pdf_path), pdf_path.name),
        )
        file_id = int(conn.execute("SELECT id FROM document_files WHERE document_source_url = ?", ("https://example.com/doc-unicode",)).fetchone()[0])
        conn.commit()

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(services={"job_service": service})))
    response = routes_documents.open_file(file_id, request)

    assert response.headers["content-disposition"].startswith("inline;")
    assert "filename*=" in response.headers["content-disposition"]


def test_download_file_keeps_attachment_with_unicode_filename(tmp_path, monkeypatch) -> None:
    settings = configure_temp_settings(tmp_path, monkeypatch)
    init_db()
    service = JobService(DummySearchService(), DummyDetailService(), DummyPdfService())

    pdf_path = settings.downloads_dir / "18-04-2026-11-00" / "Bản án số- 06-2026 ngày 27-01-2026.pdf"
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.write_bytes(b"%PDF-1.4")

    with sqlite3.connect(settings.db_path) as conn:
        conn.execute(
            "INSERT INTO documents (source_url, document_id, title, pdf_path, file_name_original, download_status) VALUES (?, ?, ?, ?, ?, ?)",
            (
                "https://example.com/doc-download",
                "doc-download",
                "Bản án số 06/2026 ngày 27/01/2026",
                str(pdf_path),
                pdf_path.name,
                "completed",
            ),
        )
        conn.execute(
            "INSERT INTO document_files (document_source_url, job_id, job_folder, pdf_path, file_name_original) VALUES (?, ?, ?, ?, ?)",
            ("https://example.com/doc-download", 1, str(pdf_path.parent), str(pdf_path), pdf_path.name),
        )
        file_id = int(conn.execute("SELECT id FROM document_files WHERE document_source_url = ?", ("https://example.com/doc-download",)).fetchone()[0])
        conn.commit()

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(services={"job_service": service})))
    response = routes_documents.download_file(file_id, request)

    assert response.headers["content-disposition"].startswith("attachment;")
    assert "filename*=" in response.headers["content-disposition"]
