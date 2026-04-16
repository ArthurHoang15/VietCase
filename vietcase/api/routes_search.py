from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request


router = APIRouter(prefix="/api", tags=["search"])


@router.get("/filters/bootstrap")
def filters_bootstrap(request: Request) -> dict[str, object]:
    form_service = request.app.state.services["form_service"]
    payload = form_service.get_bootstrap_filters()
    return {
        "hidden_fields": payload.hidden_fields,
        "fields": payload.fields,
        "selects": payload.selects,
        "source_mode": payload.source_mode,
        "form_state_id": payload.form_state_id,
    }


@router.get("/filters/dependent")
def filters_dependent(parent_field: str, parent_value: str, form_state_id: str, request: Request) -> dict[str, object]:
    form_service = request.app.state.services["form_service"]
    return form_service.get_dependent_options(parent_field, parent_value, form_state_id)


@router.post("/search/preview")
async def search_preview(request: Request) -> dict[str, object]:
    payload = await request.json()
    filters = payload.get("filters", {})
    page_index = int(payload.get("page_index", 1) or 1)
    search_service = request.app.state.services["search_service"]
    result = search_service.preview(filters, page_index=page_index)
    return {
        "total_results": result.total_results,
        "total_pages": result.total_pages,
        "results": result.results,
        "source_mode": result.source_mode,
        "preview_id": result.preview_id,
        "current_page": result.current_page,
    }


@router.post("/search/page")
async def search_page(request: Request) -> dict[str, object]:
    payload = await request.json()
    preview_id = payload.get("preview_id", "")
    page_index = int(payload.get("page_index", 1) or 1)
    search_service = request.app.state.services["search_service"]
    try:
        result = search_service.page(preview_id, page_index)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Preview ?? h?t h?n ho?c kh?ng t?n t?i") from exc
    return {
        "total_results": result.total_results,
        "total_pages": result.total_pages,
        "results": result.results,
        "source_mode": result.source_mode,
        "preview_id": result.preview_id,
        "current_page": result.current_page,
    }
