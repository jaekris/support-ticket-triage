import csv
from pathlib import Path

from src.models import RoutingDecision

_FIELDS = [
    "ticket_id", "assigned_queue", "sla_hours", "sla_deadline",
    "escalation_flag", "routing_tier", "requires_human_review", "reason",
]


def write_processing_results(decisions: list[RoutingDecision], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_FIELDS)
        writer.writeheader()
        writer.writerows(decisions)


def write_human_review_queue(decisions: list[RoutingDecision], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    review_decisions = [d for d in decisions if d["requires_human_review"]]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_FIELDS)
        writer.writeheader()
        writer.writerows(review_decisions)
