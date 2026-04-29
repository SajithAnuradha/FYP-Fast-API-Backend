from fastapi import FastAPI

from app.core.config import settings
from app.core.logging import configure_logging
from app.routes.health import router as health_router
from app.routes.patch import router as patch_router

configure_logging()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
)

app.include_router(health_router)
app.include_router(patch_router)


@app.get("/")
async def root():
    return {
        "name": settings.app_name,
        "version": settings.app_version,
    }