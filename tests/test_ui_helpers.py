from __future__ import annotations

from vietcase.core.presentation import format_display_date, format_display_datetime
from vietcase.services.pdf_service import PdfService


def test_format_display_date_supports_iso_and_vn_formats() -> None:
    assert format_display_date('2026-03-29') == '29/03/2026'
    assert format_display_date('29/03/2026') == '29/03/2026'
    assert format_display_date('29-03-2026') == '29/03/2026'
    assert format_display_date('29.03.2026') == '29/03/2026'


def test_format_display_datetime_converts_utc_to_utc_plus_7() -> None:
    assert format_display_datetime('2026-04-16T00:18:29Z') == '16/04/2026 07:18:29'
    assert format_display_datetime('2026-04-16 00:18:29') == '16/04/2026 07:18:29'


def test_pdf_file_name_prefers_document_number() -> None:
    service = PdfService()
    assert service._build_file_name('116/2026/DS-PT', 'https://example.com/sample.pdf') == '116-2026-DS-PT.pdf'
    assert service._build_file_name('13/2026/Q\u0110-PT', 'https://example.com/sample.pdf') == '13-2026-Q\u0110-PT.pdf'


def test_pdf_file_name_falls_back_to_url_name() -> None:
    service = PdfService()
    assert service._build_file_name('', 'https://example.com/files/sample.pdf') == 'sample.pdf'
