from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse


router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.get("")
def list_documents(request: Request) -> list[dict]:
    return request.app.state.services["job_service"].list_documents()


@router.get("/{document_id}")
def get_document(document_id: int, request: Request) -> dict:
    documents = request.app.state.services["job_service"].list_documents()
    for document in documents:
        if int(document["id"]) == document_id:
            return document
    raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu")


@router.get("/{document_id}/download-file")
def download_file(document_id: int, request: Request) -> FileResponse:
    document = get_document(document_id, request)
    path = Path(document.get("pdf_path", ""))
    if not path.exists():
        raise HTTPException(status_code=404, detail="Không tìm thấy file PDF trên máy")
    return FileResponse(path)
