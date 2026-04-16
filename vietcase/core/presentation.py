from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone


LOCAL_TIMEZONE = timezone(timedelta(hours=7))


def format_display_date(value: str | None) -> str:
    text = (value or '').strip()
    if not text:
        return ''
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%d.%m.%Y'):
        try:
            return datetime.strptime(text, fmt).strftime('%d/%m/%Y')
        except ValueError:
            continue
    return text


def format_display_datetime(value: str | None) -> str:
    text = (value or '').strip()
    if not text:
        return ''

    normalized = text.replace('Z', '+00:00')
    parsed: datetime | None = None

    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        parsed = None

    if parsed is None:
        for fmt in (
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d %H:%M:%S.%f',
            '%d/%m/%Y %H:%M:%S',
            '%d-%m-%Y %H:%M:%S',
        ):
            try:
                parsed = datetime.strptime(text, fmt)
                break
            except ValueError:
                continue

    if parsed is None:
        return text

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)

    return parsed.astimezone(LOCAL_TIMEZONE).strftime('%d/%m/%Y %H:%M:%S')


def with_document_display_fields(document: dict) -> dict:
    payload = dict(document)
    payload['issued_date_display'] = format_display_date(str(payload.get('issued_date') or ''))
    return payload


def with_job_display_fields(job: dict) -> dict:
    payload = dict(job)
    for key in ('created_at', 'started_at', 'finished_at', 'updated_at'):
        payload[f'{key}_display'] = format_display_datetime(str(payload.get(key) or ''))
    return payload
