import json
import importlib
from pathlib import Path

from fastapi.testclient import TestClient
from app.core.config import _default_usage_log_path
from app.services.deployed_api_client import DeployedPipelineClient


def _make_client(monkeypatch, tmp_path):
    monkeypatch.setenv("PIPELINE_BASE_URL", "")
    monkeypatch.setenv("ALLOW_MOCK_PIPELINE", "true")
    monkeypatch.setenv("USAGE_LOG_PATH", str(tmp_path / "usage.jsonl"))

    import app.core.config as config
    import app.main as main
    import app.routes.patch as patch_route
    import app.services.usage_store as usage_store_module

    importlib.reload(config)
    importlib.reload(usage_store_module)
    importlib.reload(patch_route)
    importlib.reload(main)

    return TestClient(main.app), Path(config.settings.usage_log_path)


def test_generate_patch_mock_empty_dataset_rule(monkeypatch, tmp_path):
    client, usage_log_path = _make_client(monkeypatch, tmp_path)

    payload = {
        "fileName": "Example.java",
        "language": "java",
        "selection": {
            "startLine": 10,
            "endLine": 12,
            "selectedText": "if (dataset == null) { return; }",
        },
        "context": {"before": "", "after": ""},
        "naturalLanguageFeedback": "Handle empty dataset as well",
    }

    response = client.post("/generate-patch", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["patches"], "Expected at least one patch candidate"

    patch = body["patches"][0]
    assert "dataset == null || dataset.getRowCount() == 0" in patch["patchedText"]
    assert patch["confidence"] == 0.93

    usage_lines = usage_log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(usage_lines) == 1
    usage_record = json.loads(usage_lines[0])
    assert usage_record["route"] == "/generate-patch"
    assert usage_record["result"]["success"] is True
    assert usage_record["result"]["patchCount"] == 1
    assert usage_record["bugReport"]["selection"]["selectedText"] == payload["selection"]["selectedText"]
    assert usage_record["bugReport"]["naturalLanguageFeedback"] == payload["naturalLanguageFeedback"]


def test_normalize_patch_converts_text_confidence():
    normalized = DeployedPipelineClient._normalize_patch(
        {
            "patchedText": "return value;",
            "explanation": "Updated return path.",
            "confidence": "high",
        }
    )

    assert normalized["confidence"] == 0.85


def test_default_usage_log_path_prefers_persistent_storage(tmp_path):
    persistent_root = tmp_path / "data_mount"
    persistent_root.mkdir()

    assert _default_usage_log_path(str(persistent_root)) == str(
        persistent_root / "usage_logs" / "generate_patch_requests.jsonl"
    )


def test_default_usage_log_path_falls_back_to_repo_relative_path(tmp_path):
    missing_root = tmp_path / "missing_mount"

    assert _default_usage_log_path(str(missing_root)) == "data/usage_logs/generate_patch_requests.jsonl"


def test_generate_patch_validation_errors_do_not_create_usage_record(monkeypatch, tmp_path):
    client, usage_log_path = _make_client(monkeypatch, tmp_path)

    payload = {
        "fileName": "Example.java",
        "language": "java",
        "selection": {
            "startLine": 12,
            "endLine": 10,
            "selectedText": "if (dataset == null) { return; }",
        },
        "context": {"before": "", "after": ""},
        "naturalLanguageFeedback": "Handle empty dataset as well",
    }

    response = client.post("/generate-patch", json=payload)
    assert response.status_code == 422
    usage_lines = usage_log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(usage_lines) == 1
    usage_record = json.loads(usage_lines[0])
    assert usage_record["result"]["success"] is False
    assert usage_record["result"]["patchCount"] == 0
    assert usage_record["bugReport"]["selection"]["startLine"] == 12
