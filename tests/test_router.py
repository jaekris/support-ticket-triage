from datetime import UTC, datetime

from src.models import ClassificationResult, ExtractionResult, Ticket
from src.router import route_ticket


def _ticket() -> Ticket:
    return Ticket(id="t1", subject="Test", body="Body", created_at="2026-01-01T00:00:00+00:00", source="email")


def _extraction(category: str, priority: str) -> ExtractionResult:
    return ExtractionResult(
        ticket_id="t1", category=category, priority=priority, sentiment="neutral",
        confidence=0.90, explanation="", issue_summary="", urgency_indicators=[],
        model_used="model", processed_at="2026-01-01T00:00:00+00:00", extraction_failed=False,
    )


def _classification(tier: str, human_review: bool) -> ClassificationResult:
    return ClassificationResult(
        ticket_id="t1", routing_tier=tier, requires_human_review=human_review, confidence_tier_reason="test",
    )


def test_it_support_critical_4h():
    d = route_ticket(_ticket(), _extraction("IT Support", "critical"), _classification("AUTO_ROUTE", False))
    assert d["sla_hours"] == 4
    assert d["assigned_queue"] == "IT Support Team"


def test_billing_low_24h():
    d = route_ticket(_ticket(), _extraction("Billing", "low"), _classification("AUTO_ROUTE", False))
    assert d["sla_hours"] == 24
    assert d["assigned_queue"] == "Finance Team"


def test_technical_critical_1h():
    d = route_ticket(_ticket(), _extraction("Technical Support", "critical"), _classification("AUTO_ROUTE", False))
    assert d["sla_hours"] == 1
    assert d["assigned_queue"] == "Engineering Team"


def test_human_review_flows_to_routing_decision():
    d = route_ticket(_ticket(), _extraction("Account Management", "medium"), _classification("HUMAN_REVIEW", True))
    assert d["requires_human_review"] is True
    assert d["escalation_flag"] is True


def test_sla_deadline_is_in_future():
    d = route_ticket(_ticket(), _extraction("IT Support", "high"), _classification("AUTO_ROUTE", False))
    deadline = datetime.fromisoformat(d["sla_deadline"])
    assert deadline > datetime.now(UTC)


def test_unknown_category_human_review_queue():
    d = route_ticket(_ticket(), _extraction("", "medium"), _classification("HUMAN_REVIEW", True))
    assert d["assigned_queue"] == "Human Review Queue"
