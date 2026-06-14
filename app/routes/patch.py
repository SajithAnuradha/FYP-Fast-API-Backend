import httpx
import logging
from fastapi import APIRouter, HTTPException, Request, status

from app.schemas.patch import GeneratePatchRequest, GeneratePatchResponse
from app.services.deployed_api_client import DeployedPipelineClient
from app.services.patch_services import PatchService
from app.services.usage_store import usage_store

router = APIRouter(prefix="/generate-patch", tags=["patch"])
logger = logging.getLogger(__name__)

pipeline_client = DeployedPipelineClient()
patch_service = PatchService(pipeline_client=pipeline_client)


@router.post("", response_model=GeneratePatchResponse)
async def generate_patch(
    request: GeneratePatchRequest,
    api_request: Request,
) -> GeneratePatchResponse:
    response: GeneratePatchResponse | None = None
    error_message: str | None = None
    try:
        response = await patch_service.generate_patch(request)
        return response
    except httpx.HTTPError as exc:
        error_message = f"Upstream pipeline call failed: {str(exc)}"
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=error_message,
        ) from exc
    except Exception as exc:
        error_message = f"Patch generation failed: {str(exc)}"
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_message,
        ) from exc
    finally:
        try:
            await usage_store.record_generate_patch_attempt(
                api_request=api_request,
                patch_request=request,
                response=response,
                error_message=error_message,
            )
        except Exception:
            logger.exception("Failed to persist generate-patch usage record")
