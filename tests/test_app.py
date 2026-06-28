from unittest.mock import patch

from fastapi.testclient import TestClient

import app as app_module
from app import app
from src.models import ExtractionResult

client = TestClient(app)


def _canned_extraction(ticket_id: str) -> ExtractionResult:
    return ExtractionResult(
        ticket_id=ticket_id,
        category="IT Support",
        priority="high",
        sentiment="frustrated",
        confidence=0.93,
        explanation="locked out",
        issue_summary="password reset",
        urgency_indicators=["urgently"],
        model_used="claude-haiku-4-5-20251001",
        processed_at="2026-01-01T00:00:00+00:00",
        extraction_failed=False,
        input_tokens=1200,
        output_tokens=180,
        latency_ms=140.0,
    )


def test_healthz_always_ok(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_readyz_reports_missing_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    resp = client.get("/readyz")
    assert resp.status_code == 200
    assert resp.json()["api_key_configured"] is False


def test_triage_returns_503_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    resp = client.post("/triage", json={"subject": "Help", "body": "I am locked out"})
    assert resp.status_code == 503
    assert "ANTHROPIC_API_KEY" in resp.json()["detail"]


def test_triage_validation_error_on_empty_body(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    resp = client.post("/triage", json={"subject": "Help", "body": ""})
    assert resp.status_code == 422


def test_triage_success_with_mocked_llm(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    with patch.object(app_module, "extract_ticket", side_effect=lambda t, c: _canned_extraction(t["id"])):
        resp = client.post(
            "/triage",
            json={"subject": "VPN down", "body": "Cannot connect, need it urgently", "source": "web"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["extraction"]["category"] == "IT Support"
    assert data["classification"]["routing_tier"] == "AUTO_ROUTE"
    assert data["routing"]["assigned_queue"] == "IT Support Team"
    # The raw ticket body must never be echoed back in the triage response.
    assert "body" not in data
    assert "Cannot connect" not in resp.text
