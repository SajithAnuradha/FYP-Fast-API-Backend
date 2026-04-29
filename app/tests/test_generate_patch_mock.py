import importlib

from fastapi.testclient import TestClient
from app.services.deployed_api_client import DeployedPipelineClient


def _make_client(monkeypatch):
    monkeypatch.setenv("PIPELINE_BASE_URL", "")
    monkeypatch.setenv("ALLOW_MOCK_PIPELINE", "true")

    import app.core.config as config
    import app.main as main

    importlib.reload(config)
    importlib.reload(main)

    return TestClient(main.app)


def test_generate_patch_mock_empty_dataset_rule(monkeypatch):
    client = _make_client(monkeypatch)

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


def test_normalize_patch_converts_text_confidence():
    normalized = DeployedPipelineClient._normalize_patch(
        {
            "patchedText": "return value;",
            "explanation": "Updated return path.",
            "confidence": "high",
        }
    )

    assert normalized["confidence"] == 0.85
