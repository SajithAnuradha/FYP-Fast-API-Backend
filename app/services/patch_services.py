from app.schemas.patch import (
    GeneratePatchRequest,
    GeneratePatchResponse,
    PatchCandidate,
)
from app.services.deployed_api_client import DeployedPipelineClient


class PatchService:
    def __init__(self, pipeline_client: DeployedPipelineClient):
        self.pipeline_client = pipeline_client

    async def generate_patch(
        self,
        request: GeneratePatchRequest,
    ) -> GeneratePatchResponse:
        patches = await self.pipeline_client.generate_patch(request)

        if not patches:
            patches = [
                PatchCandidate(
                    patchedText=request.selection.selectedText,
                    explanation="No patches were returned by the pipeline.",
                    confidence=0.0,
                )
            ]

        return GeneratePatchResponse(patches=patches)