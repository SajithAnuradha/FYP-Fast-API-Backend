import asyncio
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import Request

from app.core.config import settings
from app.schemas.patch import GeneratePatchRequest, GeneratePatchResponse


class UsageStore:
    def __init__(self, log_path: str):
        self.log_path = Path(log_path)
        self._write_lock = asyncio.Lock()

    async def record_generate_patch_attempt(
        self,
        *,
        api_request: Request,
        patch_request: GeneratePatchRequest,
        response: GeneratePatchResponse | None,
        error_message: str | None,
    ) -> None:
        record = {
            "eventId": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "route": str(api_request.url.path),
            "method": api_request.method,
            "client": self._extract_client_metadata(api_request),
            "bugReport": {
                "fileName": patch_request.fileName,
                "language": patch_request.language,
                "selection": patch_request.selection.model_dump(),
                "context": patch_request.context.model_dump(),
                "naturalLanguageFeedback": patch_request.naturalLanguageFeedback,
            },
            "result": {
                "success": error_message is None,
                "patchCount": len(response.patches) if response else 0,
                "errorMessage": error_message,
            },
        }
        await self._append_record(record)

    async def record_generate_patch_validation_failure(
        self,
        *,
        api_request: Request,
        request_body: Any,
        error_message: str,
    ) -> None:
        record = {
            "eventId": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "route": str(api_request.url.path),
            "method": api_request.method,
            "client": self._extract_client_metadata(api_request),
            "bugReport": request_body,
            "result": {
                "success": False,
                "patchCount": 0,
                "errorMessage": error_message,
            },
        }
        await self._append_record(record)

    def _extract_client_metadata(self, api_request: Request) -> dict[str, Any]:
        forwarded_for = api_request.headers.get("x-forwarded-for")
        real_ip = api_request.headers.get("x-real-ip")
        return {
            "ipAddress": forwarded_for or real_ip or (api_request.client.host if api_request.client else None),
            "userAgent": api_request.headers.get("user-agent"),
            "origin": api_request.headers.get("origin"),
            "referer": api_request.headers.get("referer"),
        }

    async def _append_record(self, record: dict[str, Any]) -> None:
        async with self._write_lock:
            await asyncio.to_thread(self._append_record_sync, record)

    def _append_record_sync(self, record: dict[str, Any]) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=True))
            handle.write("\n")


usage_store = UsageStore(settings.usage_log_path)
