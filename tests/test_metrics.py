from src.metrics import RunMetrics, estimate_cost_usd
from src.models import ClassificationResult, ExtractionResult


def _extraction(tier_ok=True, inp=1000, out=200, latency=150.0) -> ExtractionResult:
    return ExtractionResult(
        ticket_id="t",
        category="IT Support",
        priority="medium",
        sentiment="neutral",
        confidence=0.9,
        explanation="x",
        issue_summary="x",
        urgency_indicators=[],
        model_used="claude-haiku-4-5-20251001",
        processed_at="2026-01-01T00:00:00+00:00",
        extraction_failed=not tier_ok,
        input_tokens=inp,
        output_tokens=out,
        latency_ms=latency,
    )


def _classification(tier: str) -> ClassificationResult:
    return ClassificationResult(
        ticket_id="t",
        routing_tier=tier,
        requires_human_review=tier == "HUMAN_REVIEW",
        confidence_tier_reason="x",
    )


def test_estimate_cost_haiku_rates():
    # Haiku 4.5: $1.00 / MTok input, $5.00 / MTok output.
    # 1,000,000 input + 1,000,000 output = $1.00 + $5.00 = $6.00
    cost = estimate_cost_usd("claude-haiku-4-5-20251001", 1_000_000, 1_000_000)
    assert round(cost, 6) == 6.0


def test_estimate_cost_unknown_model_uses_fallback():
    # Unknown models must not crash; fall back to a default rate.
    cost = estimate_cost_usd("some-future-model", 1_000_000, 0)
    assert cost > 0


def test_run_metrics_aggregates_counts_tokens_and_tiers():
    extractions = [_extraction(), _extraction(), _extraction(tier_ok=False, inp=0, out=0, latency=50.0)]
    classifications = [
        _classification("AUTO_ROUTE"),
        _classification("SOFT_ROUTE"),
        _classification("HUMAN_REVIEW"),
    ]
    m = RunMetrics.from_results(extractions, classifications, elapsed_seconds=2.0)

    assert m.ticket_count == 3
    assert m.ok_count == 2
    assert m.failed_count == 1
    assert m.total_input_tokens == 2000
    assert m.total_output_tokens == 400
    assert m.tier_auto == 1
    assert m.tier_soft == 1
    assert m.tier_human == 1
    assert m.estimated_cost_usd > 0
    assert m.avg_latency_ms == (150.0 + 150.0 + 50.0) / 3
    assert m.throughput_per_sec == 3 / 2.0


def test_run_metrics_handles_zero_elapsed():
    m = RunMetrics.from_results([_extraction()], [_classification("AUTO_ROUTE")], elapsed_seconds=0.0)
    assert m.throughput_per_sec == 0.0  # no division by zero


def test_run_metrics_empty_is_safe():
    m = RunMetrics.from_results([], [], elapsed_seconds=1.0)
    assert m.ticket_count == 0
    assert m.avg_latency_ms == 0.0
    assert m.estimated_cost_usd == 0.0
