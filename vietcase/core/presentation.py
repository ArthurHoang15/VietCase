from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path


LOCAL_TIMEZONE = timezone(timedelta(hours=7))


def format_display_date(value: str | None) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(text, fmt).strftime("%d/%m/%Y")
        except ValueError:
            continue
    return text


def format_display_date_dots(value: str | None) -> str:
    formatted = format_display_date(value)
    return formatted.replace("/", ".") if formatted else ""


def format_display_datetime(value: str | None) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    normalized = text.replace("Z", "+00:00")
    parsed: datetime | None = None
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        parsed = None
    if parsed is None:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%d/%m/%Y %H:%M:%S", "%d-%m-%Y %H:%M:%S"):
            try:
                parsed = datetime.strptime(text, fmt)
                break
            except ValueError:
                continue
    if parsed is None:
        return text
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(LOCAL_TIMEZONE).strftime("%d/%m/%Y %H:%M:%S")


def build_document_display_title(document: dict) -> str:
    title = str(document.get("title") or "").strip()
    if title:
        return title

    document_type = str(document.get("document_type") or "").strip()
    document_number = str(document.get("document_number") or "").strip()
    issued_date = format_display_date(str(document.get("issued_date") or ""))
    published_date = format_display_date_dots(str(document.get("published_date") or ""))
    court_name = str(document.get("court_name") or "").strip()

    parts: list[str] = []
    if document_type:
        parts.append(f"{document_type}:")
    if document_number:
        parts.append(f"s\u1ed1 {document_number}")
    if issued_date:
        parts.append(f"ng\u00e0y {issued_date}")
    if court_name:
        parts.append(f"c\u1ee7a {court_name}")

    display_title = " ".join(parts).strip()
    if published_date:
        display_title = f"{display_title} ({published_date})".strip()
    return display_title or "T\u00e0i li\u1ec7u \u0111\u00e3 t\u1ea3i"


def build_local_file_url(pdf_path: str | None) -> tuple[bool, str]:
    raw_path = str(pdf_path or "").strip()
    if not raw_path:
        return False, ""
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = path.resolve(strict=False)
    if not path.exists():
        return False, ""
    return True, path.resolve().as_uri()


def with_document_display_fields(document: dict) -> dict:
    payload = dict(document)
    payload["issued_date_display"] = format_display_date(str(payload.get("issued_date") or ""))
    payload["published_date_display"] = format_display_date(str(payload.get("published_date") or ""))
    payload["published_date_dot_display"] = format_display_date_dots(str(payload.get("published_date") or ""))
    payload["display_title"] = build_document_display_title(payload)
    file_exists, local_file_url = build_local_file_url(payload.get("pdf_path"))
    payload["file_exists"] = file_exists
    payload["local_file_url"] = local_file_url
    return payload


def with_job_display_fields(job: dict) -> dict:
    payload = dict(job)
    for key in ("created_at", "started_at", "finished_at", "updated_at"):
        payload[f"{key}_display"] = format_display_datetime(str(payload.get(key) or ""))
    status = str(payload.get("status") or "").strip().lower()
    payload["can_resume"] = status != "completed"
    payload["can_pause"] = status != "completed"
    payload["can_cancel"] = status != "completed"
    return payload
