from __future__ import annotations

from fastapi import APIRouter, Request

from vietcase.services.source_router import SourceContext


router = APIRouter(prefix="/api", tags=["search"])


@router.get("/filters/bootstrap")
def filters_bootstrap(request: Request) -> dict[str, object]:
    form_service = request.app.state.services["form_service"]
    payload = form_service.get_bootstrap_filters(SourceContext())
    return {
        "hidden_fields": payload.hidden_fields,
        "selects": payload.selects,
        "source_mode": payload.source_mode,
    }


@router.get("/filters/dependent")
def filters_dependent(parent_field: str, parent_value: str, request: Request) -> dict[str, object]:
    form_service = request.app.state.services["form_service"]
    return form_service.get_dependent_options(parent_field, parent_value, SourceContext())


@router.post("/search/preview")
async def search_preview(request: Request) -> dict[str, object]:
    payload = await request.json()
    filters = payload.get("filters", {})
    page_index = int(payload.get("page_index", 1) or 1)
    search_service = request.app.state.services["search_service"]
    result = search_service.preview(filters, page_index=page_index, context=SourceContext())
    return {
        "total_results": result.total_results,
        "total_pages": result.total_pages,
        "results": result.results,
        "source_mode": result.source_mode,
    }


@router.post("/search/page")
async def search_page(request: Request) -> dict[str, object]:
    return await search_preview(request)
