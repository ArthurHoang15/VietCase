from __future__ import annotations

from dataclasses import dataclass

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from vietcase.core.presentation import with_document_display_fields, with_job_display_fields


def get_templates(request: Request) -> Jinja2Templates:
    return request.app.state.templates


@dataclass(slots=True)
class PageServices:
    form_service: object
    job_service: object


def get_services(request: Request) -> PageServices:
    return PageServices(
        form_service=request.app.state.services["form_service"],
        job_service=request.app.state.services["job_service"],
    )


router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def index(request: Request, templates: Jinja2Templates = Depends(get_templates), services: PageServices = Depends(get_services)) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "filters": services.form_service.get_cached_options(),
            "page": "index",
        },
    )


@router.get("/jobs", response_class=HTMLResponse)
def jobs_page(request: Request, templates: Jinja2Templates = Depends(get_templates), services: PageServices = Depends(get_services)) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "jobs.html",
        {
            "jobs": [with_job_display_fields(job) for job in services.job_service.list_jobs()],
            "page": "jobs",
        },
    )


@router.get("/documents", response_class=HTMLResponse)
def documents_page(request: Request, templates: Jinja2Templates = Depends(get_templates), services: PageServices = Depends(get_services)) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "documents.html",
        {
            "documents": [with_document_display_fields(document) for document in services.job_service.list_documents()],
            "page": "documents",
        },
    )


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
