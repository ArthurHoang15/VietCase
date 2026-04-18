from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse

from vietcase.core.presentation import with_document_display_fields


router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.get("")
def list_documents(
    request: Request,
    q: str = "",
    document_type: str = "",
    court_name: str = "",
    case_style: str = "",
    legal_relation: str = "",
    date_from: str = "",
    date_to: str = "",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
) -> dict[str, object]:
    service = request.app.state.services["job_service"]
    payload = service.search_document_files(
        q=q,
        document_type=document_type,
        court_name=court_name,
        case_style=case_style,
        legal_relation=legal_relation,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
    return {
        "items": [with_document_display_fields(document) for document in payload["items"]],
        "total": payload["total"],
        "page": payload["page"],
        "page_size": payload["page_size"],
        "filter_options": payload["filter_options"],
    }


@router.post("/delete-selected")
async def delete_selected_documents(request: Request) -> dict:
    payload = await request.json()
    service = request.app.state.services["job_service"]
    return service.delete_documents(payload.get("ids") or [])


@router.post("/delete-all")
def delete_all_documents(request: Request) -> dict:
    service = request.app.state.services["job_service"]
    return service.delete_all_documents()


@router.get("/{document_id}")
def get_document(document_id: int, request: Request) -> dict:
    document = request.app.state.services["job_service"].get_document_file(document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Khong tim thay tai lieu")
    return with_document_display_fields(document)


@router.delete("/{document_id}")
def delete_document(document_id: int, request: Request) -> dict:
    service = request.app.state.services["job_service"]
    return service.delete_document(document_id)


@router.get("/{document_id}/open-file")
def open_file(document_id: int, request: Request) -> FileResponse:
    document = get_document(document_id, request)
    path = Path(document.get("pdf_path", ""))
    if not path.exists():
        raise HTTPException(status_code=404, detail="Khong tim thay file PDF tren may")
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=path.name,
        content_disposition_type="inline",
    )


@router.get("/{document_id}/download-file")
def download_file(document_id: int, request: Request) -> FileResponse:
    document = get_document(document_id, request)
    path = Path(document.get("pdf_path", ""))
    if not path.exists():
        raise HTTPException(status_code=404, detail="Khong tim thay file PDF tren may")
    return FileResponse(path, filename=path.name, content_disposition_type="attachment")
