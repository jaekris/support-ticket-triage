import csv
import tempfile
from pathlib import Path

from src.models import RoutingDecision
from src.output import write_human_review_queue, write_processing_results

_FIELDS = [
    "ticket_id", "assigned_queue", "sla_hours", "sla_deadline",
    "escalation_flag", "routing_tier", "requires_human_review", "reason",
]


def _decision(ticket_id: str, requires_human_review: bool) -> RoutingDecision:
    return RoutingDecision(
        ticket_id=ticket_id,
        assigned_queue="IT Support Team",
        sla_hours=8,
        sla_deadline="2026-01-01T08:00:00+00:00",
        escalation_flag=False,
        routing_tier="AUTO_ROUTE",
        requires_human_review=requires_human_review,
        reason="test",
    )


def test_write_processing_results_row_count():
    decisions = [_decision(f"t{i}", i % 2 == 0) for i in range(5)]
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "results.csv"
        write_processing_results(decisions, path)
        with open(path) as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 5


def test_write_human_review_queue_filters():
    decisions = [
        _decision("t1", True),
        _decision("t2", False),
        _decision("t3", True),
    ]
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "review.csv"
        write_human_review_queue(decisions, path)
        with open(path) as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 2
        assert all(r["requires_human_review"] in ("True", "1", "true") for r in rows)


def test_correct_csv_headers():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "results.csv"
        write_processing_results([_decision("t1", False)], path)
        with open(path) as f:
            reader = csv.DictReader(f)
            assert set(reader.fieldnames) == set(_FIELDS)


def test_idempotent_overwrite():
    decisions_v1 = [_decision("t1", False)]
    decisions_v2 = [_decision("t2", True), _decision("t3", False)]
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "results.csv"
        write_processing_results(decisions_v1, path)
        write_processing_results(decisions_v2, path)
        with open(path) as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 2
        assert rows[0]["ticket_id"] == "t2"
