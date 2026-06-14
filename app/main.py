import json

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.requests import Request
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import configure_logging
from app.routes.health import router as health_router
from app.routes.patch import router as patch_router
from app.services.usage_store import usage_store

configure_logging()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(patch_router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    if request.url.path == "/generate-patch":
        raw_body = exc.body
        if isinstance(raw_body, (bytes, bytearray)):
            try:
                raw_body = json.loads(raw_body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                raw_body = {"rawBody": raw_body.decode("utf-8", errors="replace")}

        await usage_store.record_generate_patch_validation_failure(
            api_request=request,
            request_body=raw_body,
            error_message=str(exc),
        )

    return await request_validation_exception_handler(request, exc)


@app.get("/")
async def root():
    return {
        "name": settings.app_name,
        "version": settings.app_version,
    }
