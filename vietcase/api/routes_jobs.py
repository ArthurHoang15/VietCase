from __future__ import annotations

from fastapi import APIRouter, Request

from vietcase.core.presentation import with_job_display_fields


router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("")
def list_jobs(request: Request) -> list[dict]:
    jobs = request.app.state.services["job_service"].list_jobs()
    return [with_job_display_fields(job) for job in jobs]


@router.get("/{job_id}")
def get_job(job_id: int, request: Request) -> dict:
    job = request.app.state.services["job_service"].get_job(job_id)
    return with_job_display_fields(job) if job else {}


@router.get("/{job_id}/items")
def get_job_items(job_id: int, request: Request) -> list[dict]:
    return request.app.state.services["job_service"].list_job_items(job_id)


@router.post("")
async def create_job(request: Request) -> dict:
    payload = await request.json()
    job_service = request.app.state.services["job_service"]
    job = job_service.create_job(
        mode=payload.get("mode", "preview_then_download"),
        job_name=payload.get("job_name", "??t t?i VietCase"),
        filters=payload.get("filters") or {},
        items=payload.get("items") or [],
    )
    job_service.start_job(int(job["id"]))
    return with_job_display_fields(job)


@router.post("/{job_id}/resume")
def resume_job(job_id: int, request: Request) -> dict:
    service = request.app.state.services["job_service"]
    service.resume_job(job_id)
    return with_job_display_fields(service.get_job(job_id))


@router.post("/{job_id}/pause")
def pause_job(job_id: int, request: Request) -> dict:
    service = request.app.state.services["job_service"]
    service.pause_job(job_id)
    return with_job_display_fields(service.get_job(job_id))


@router.post("/{job_id}/cancel")
def cancel_job(job_id: int, request: Request) -> dict:
    service = request.app.state.services["job_service"]
    service.cancel_job(job_id)
    return with_job_display_fields(service.get_job(job_id))
