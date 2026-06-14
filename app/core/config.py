import os
from dataclasses import dataclass


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _as_list(value: str | None, default: list[str] | None = None) -> list[str]:
    if value is None:
        return list(default or [])
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_version: str
    host: str
    port: int
    cors_allow_origins: list[str]
    usage_log_path: str
    pipeline_base_url: str
    pipeline_generate_path: str
    pipeline_api_key: str
    pipeline_timeout_seconds: float
    allow_mock_pipeline: bool
    cf_account_id: str
    cf_api_token: str
    cf_model: str
    openai_api_key: str
    openai_model: str


def get_settings() -> Settings:
    return Settings(
        app_name=os.getenv("APP_NAME", "APR Patch Backend"),
        app_version=os.getenv("APP_VERSION", "0.1.0"),
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8000")),
        cors_allow_origins=_as_list(
            os.getenv("CORS_ALLOW_ORIGINS"),
            ["http://localhost:5173", "http://127.0.0.1:5173"],
        ),
        usage_log_path=os.getenv("USAGE_LOG_PATH", "data/usage_logs/generate_patch_requests.jsonl"),
        pipeline_base_url=os.getenv("PIPELINE_BASE_URL", "").rstrip("/"),
        pipeline_generate_path=os.getenv("PIPELINE_GENERATE_PATH", "/generate-patch"),
        pipeline_api_key=os.getenv("PIPELINE_API_KEY", ""),
        pipeline_timeout_seconds=float(os.getenv("PIPELINE_TIMEOUT_SECONDS", "30")),
        allow_mock_pipeline=_as_bool(os.getenv("ALLOW_MOCK_PIPELINE"), True),
        cf_account_id=os.getenv("CF_ACCOUNT_ID", ""),
        cf_api_token=os.getenv("CF_API_TOKEN", ""),
        cf_model=os.getenv("CF_MODEL", "@cf/meta/llama-3.1-8b-instruct"),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
    )


settings = get_settings()
