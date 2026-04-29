import httpx
from fastapi import APIRouter, HTTPException, status

from app.schemas.patch import GeneratePatchRequest, GeneratePatchResponse
from app.services.deployed_api_client import DeployedPipelineClient
from app.services.patch_services import PatchService

router = APIRouter(prefix="/generate-patch", tags=["patch"])

pipeline_client = DeployedPipelineClient()
patch_service = PatchService(pipeline_client=pipeline_client)


@router.post("", response_model=GeneratePatchResponse)
async def generate_patch(request: GeneratePatchRequest) -> GeneratePatchResponse:
    try:
        return await patch_service.generate_patch(request)
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Upstream pipeline call failed: {str(exc)}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Patch generation failed: {str(exc)}",
        ) from exc