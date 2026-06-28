from pathlib import Path

from src.classifier import classify_extraction
from src.config import PipelineConfig
from src.models import ExtractionResult


def _config() -> PipelineConfig:
    return PipelineConfig(
        db_path=Path("data/triage.db"),
        input_csv=Path("data/sample_tickets.csv"),
        output_dir=Path("data/outputs"),
        anthropic_api_key="test-key",
        model_name="claude-haiku-4-5-20251001",
        confidence_auto_route=0.85,
        confidence_soft_route=0.60,
        max_retries=3,
        retry_base_delay_seconds=0.0,
        max_concurrency=5,
        n_tickets=10,
        random_seed=42,
        log_level="INFO",
    )


def _extraction(confidence: float, failed: bool = False, urgency: list | None = None) -> ExtractionResult:
    return ExtractionResult(
        ticket_id="t1",
        category="IT Support",
        priority="medium",
        sentiment="neutral",
        confidence=confidence,
        explanation="test",
        issue_summary="test",
        urgency_indicators=urgency or [],
        model_used="model",
        processed_at="2026-01-01T00:00:00+00:00",
        extraction_failed=failed,
    )


def test_high_confidence_auto_route():
    result = classify_extraction(_extraction(0.90), _config())
    assert result["routing_tier"] == "AUTO_ROUTE"
    assert result["requires_human_review"] is False


def test_boundary_085_auto_route():
    result = classify_extraction(_extraction(0.85), _config())
    assert result["routing_tier"] == "AUTO_ROUTE"


def test_boundary_060_soft_route():
    result = classify_extraction(_extraction(0.60), _config())
    assert result["routing_tier"] == "SOFT_ROUTE"
    assert result["requires_human_review"] is False


def test_low_confidence_human_review():
    result = classify_extraction(_extraction(0.45), _config())
    assert result["routing_tier"] == "HUMAN_REVIEW"
    assert result["requires_human_review"] is True


def test_extraction_failed_human_review():
    result = classify_extraction(_extraction(0.0, failed=True), _config())
    assert result["routing_tier"] == "HUMAN_REVIEW"
    assert result["requires_human_review"] is True
    assert result["confidence_tier_reason"] == "extraction_failed"


def test_soft_route_with_urgency_escalates():
    result = classify_extraction(_extraction(0.70, urgency=["production down", "urgent"]), _config())
    assert result["routing_tier"] == "HUMAN_REVIEW"
    assert result["requires_human_review"] is True
    assert "urgency indicators" in result["confidence_tier_reason"]


def test_soft_route_without_urgency_stays_soft():
    result = classify_extraction(_extraction(0.70, urgency=["please help"]), _config())
    assert result["routing_tier"] == "SOFT_ROUTE"


def test_soft_route_escalates_on_phrase_embedded_in_longer_indicator():
    # The model paraphrases: "production is down" should still trip the
    # "production down"/"down" escalation rather than slip through as SOFT_ROUTE.
    result = classify_extraction(
        _extraction(0.70, urgency=["the production is down right now"]), _config()
    )
    assert result["routing_tier"] == "HUMAN_REVIEW"
    assert result["requires_human_review"] is True


def test_escalation_is_case_insensitive():
    result = classify_extraction(_extraction(0.70, urgency=["SECURITY BREACH detected"]), _config())
    assert result["routing_tier"] == "HUMAN_REVIEW"


def test_no_false_escalation_on_unrelated_text():
    result = classify_extraction(
        _extraction(0.70, urgency=["downloaded the report", "production schedule"]), _config()
    )
    assert result["routing_tier"] == "SOFT_ROUTE"
