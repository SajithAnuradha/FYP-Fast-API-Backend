import json
import httpx
from app.core.config import settings
from app.schemas.patch import GeneratePatchRequest, PatchCandidate


class DeployedPipelineClient:
    """
    This class is the only place that talks to the deployed patch pipeline.

    For starter mode:
    - if PIPELINE_BASE_URL is provided, it proxies the request there
    - otherwise it falls back to a mock patch generator
    """

    async def generate_patch(self, request: GeneratePatchRequest) -> list[PatchCandidate]:
        if settings.openai_api_key:
            return await self._call_openai(request)

        if settings.pipeline_base_url:
            return await self._call_remote_pipeline(request)

        if settings.cf_account_id and settings.cf_api_token:
            return await self._call_cloudflare_workers_ai(request)

        if settings.allow_mock_pipeline:
            return self._mock_generate_patch(request)

        raise RuntimeError(
            "PIPELINE_BASE_URL is not configured, Cloudflare Workers AI is not configured, "
            "and mock pipeline is disabled."
        )
    async def _call_openai(self, request: GeneratePatchRequest) -> list[PatchCandidate]:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        }

        prompt = (
            "Return JSON with key 'patches'. Each item must contain "
            "'patchedText', 'explanation', and 'confidence'.\n\n"
            f"File: {request.fileName}\n"
            f"Language: {request.language}\n"
            f"SelectedText:\n{request.selection.selectedText}\n\n"
            f"Before:\n{request.context.before}\n\n"
            f"After:\n{request.context.after}\n\n"
            f"UserFeedback:\n{request.naturalLanguageFeedback}\n"
        )

        payload = {
            "model": settings.openai_model,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": "You are a code patch generator."},
                {"role": "user", "content": prompt},
            ],
        }

        async with httpx.AsyncClient(timeout=settings.pipeline_timeout_seconds) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()

        body = response.json()
        raw = body["choices"][0]["message"]["content"]
        parsed = self._try_parse_json(raw) or {}
        raw_patches = parsed.get("patches", [])
        return self._validate_patches(raw_patches, request.selection.selectedText)

    async def _call_remote_pipeline(
        self,
        request: GeneratePatchRequest,
    ) -> list[PatchCandidate]:
        url = f"{settings.pipeline_base_url}{settings.pipeline_generate_path}"
        headers = {"Content-Type": "application/json"}

        if settings.pipeline_api_key:
            headers["Authorization"] = f"Bearer {settings.pipeline_api_key}"

        async with httpx.AsyncClient(timeout=settings.pipeline_timeout_seconds) as client:
            response = await client.post(
                url,
                json=request.model_dump(),
                headers=headers,
            )
            response.raise_for_status()

        body = response.json()
        raw_patches = body.get("patches", [])
        return self._validate_patches(raw_patches, request.selection.selectedText)

    def _mock_generate_patch(
        self,
        request: GeneratePatchRequest,
    ) -> list[PatchCandidate]:
        selected = request.selection.selectedText
        feedback = request.naturalLanguageFeedback.lower()

        if "empty dataset" in feedback and "dataset == null" in selected:
            patched = selected.replace(
                "dataset == null",
                "dataset == null || dataset.getRowCount() == 0",
            )
            return [
                PatchCandidate(
                    patchedText=patched,
                    explanation="Added empty dataset guard based on NL feedback.",
                    confidence=0.93,
                )
            ]

        if "null" in feedback and "==" not in selected:
            return [
                PatchCandidate(
                    patchedText=f"if ({selected.strip()} == null) {{\n    return;\n}}",
                    explanation="Mocked null-check patch.",
                    confidence=0.51,
                )
            ]

        return [
            PatchCandidate(
                patchedText=selected,
                explanation="No mock transformation rule matched. Returning original text.",
                confidence=0.20,
            )
        ]

    async def _call_cloudflare_workers_ai(
        self,
        request: GeneratePatchRequest,
    ) -> list[PatchCandidate]:
        url = (
            "https://api.cloudflare.com/client/v4/accounts/"
            f"{settings.cf_account_id}/ai/run/{settings.cf_model}"
        )
        headers = {
            "Authorization": f"Bearer {settings.cf_api_token}",
            "Content-Type": "application/json",
        }

        prompt = (
            "You are a code patch generator. Return a JSON object with a single key "
            '"patches", which is a list of patch candidates. Each patch candidate must '
            'have keys: "patchedText" (string), "explanation" (string), and "confidence" '
            "(number between 0 and 1). Only output valid JSON.\n\n"
            f"File: {request.fileName}\n"
            f"Language: {request.language}\n"
            f"SelectedText:\n{request.selection.selectedText}\n\n"
            f"Before:\n{request.context.before}\n\n"
            f"After:\n{request.context.after}\n\n"
            f"UserFeedback:\n{request.naturalLanguageFeedback}\n"
        )

        payload = {
            "messages": [
                {"role": "system", "content": "You are a code patch generator."},
                {"role": "user", "content": prompt},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "patch_response",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "patches": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "patchedText": {"type": "string"},
                                        "explanation": {"type": "string"},
                                        "confidence": {
                                            "type": "number",
                                            "minimum": 0.0,
                                            "maximum": 1.0,
                                        },
                                    },
                                    "required": [
                                        "patchedText",
                                        "explanation",
                                        "confidence",
                                    ],
                                    "additionalProperties": False,
                                },
                            }
                        },
                        "required": ["patches"],
                        "additionalProperties": False,
                    },
                },
            },
        }

        async with httpx.AsyncClient(timeout=settings.pipeline_timeout_seconds) as client:
            response = await client.post(url, json=payload, headers=headers)
            if response.is_error:
                raise httpx.HTTPStatusError(
                    f"Cloudflare Workers AI error {response.status_code}: {response.text}",
                    request=response.request,
                    response=response,
                )

        body = response.json()
        result = body.get("result", {})
        raw_response = result.get("response", "")

        if isinstance(raw_response, dict):
            parsed = raw_response
        else:
            parsed = self._try_parse_json(raw_response)
        raw_patches = []
        if isinstance(parsed, dict):
            raw_patches = parsed.get("patches", [])

        patches = self._validate_patches(raw_patches, request.selection.selectedText)

        if not patches:
            patches = [
                PatchCandidate(
                    patchedText=request.selection.selectedText,
                    explanation="Cloudflare Workers AI returned no valid patches.",
                    confidence=0.0,
                )
            ]
        return patches

    @classmethod
    def _validate_patches(
        cls,
        raw_patches: list[dict],
        fallback_text: str,
    ) -> list[PatchCandidate]:
        patches = [PatchCandidate.model_validate(cls._normalize_patch(item)) for item in raw_patches]
        if patches:
            return patches

        return [
            PatchCandidate(
                patchedText=fallback_text,
                explanation="Model returned no valid patches.",
                confidence=0.0,
            )
        ]

    @classmethod
    def _normalize_patch(cls, patch: dict) -> dict:
        normalized = dict(patch)
        normalized["confidence"] = cls._normalize_confidence(normalized.get("confidence"))
        return normalized

    @staticmethod
    def _normalize_confidence(value) -> float:
        if isinstance(value, (int, float)):
            return max(0.0, min(1.0, float(value)))

        if isinstance(value, str):
            cleaned = value.strip().lower()
            labels = {
                "very low": 0.1,
                "low": 0.25,
                "medium": 0.5,
                "moderate": 0.5,
                "high": 0.85,
                "very high": 0.95,
            }
            if cleaned in labels:
                return labels[cleaned]

            try:
                parsed = float(cleaned)
                return max(0.0, min(1.0, parsed))
            except ValueError:
                return 0.0

        return 0.0

    @staticmethod
    def _try_parse_json(raw_text: str):
        if not raw_text:
            return None
        try:
            return json.loads(raw_text)
        except json.JSONDecodeError:
            pass

        start = raw_text.find("{")
        end = raw_text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        snippet = raw_text[start : end + 1]
        try:
            return json.loads(snippet)
        except json.JSONDecodeError:
            return None
