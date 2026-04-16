from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from vietcase.api.routes_documents import router as documents_router
from vietcase.api.routes_jobs import router as jobs_router
from vietcase.api.routes_pages import router as pages_router
from vietcase.api.routes_search import router as search_router
from vietcase.core.config import get_settings
from vietcase.core.logging import configure_logging
from vietcase.core.paths import ensure_runtime_dirs
from vietcase.db.migrations import init_db
from vietcase.services.detail_service import DetailService
from vietcase.services.form_service import FormService
from vietcase.services.job_service import JobService
from vietcase.services.pdf_service import PdfService
from vietcase.services.resume_service import repair_interrupted_jobs
from vietcase.services.search_service import SearchService
from vietcase.services.source_client_playwright import PlaywrightSourceClient
from vietcase.services.source_client_requests import RequestsSourceClient
from vietcase.services.source_router import SourceRouter


LOGGER = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()
    ensure_runtime_dirs()
    configure_logging()
    init_db()
    repair_interrupted_jobs()

    requests_client = RequestsSourceClient()
    if settings.tls_mode == "auto":
        warmup_mode = requests_client.warm_up_tls_cache()
        if warmup_mode:
            LOGGER.info("Requests client TLS warm-up completed in %s mode", warmup_mode)
    playwright_client = PlaywrightSourceClient()
    source_router = SourceRouter(requests_client, playwright_client)

    form_service = FormService(source_router)
    search_service = SearchService(source_router)
    detail_service = DetailService(source_router)
    pdf_service = PdfService()
    job_service = JobService(search_service, detail_service, pdf_service)

    app = FastAPI(title="VietCase", version="0.1.0")
    app.state.settings = settings
    app.state.templates = Jinja2Templates(directory=str(settings.base_dir / "vietcase" / "templates"))
    app.state.services = {
        "form_service": form_service,
        "search_service": search_service,
        "detail_service": detail_service,
        "pdf_service": pdf_service,
        "job_service": job_service,
    }

    app.mount("/static", StaticFiles(directory=str(settings.base_dir / "vietcase" / "static")), name="static")
    app.include_router(pages_router)
    app.include_router(search_router)
    app.include_router(jobs_router)
    app.include_router(documents_router)
    return app
