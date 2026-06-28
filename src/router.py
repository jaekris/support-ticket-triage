from datetime import UTC, datetime, timedelta

from src.classifier import SLA_HOURS
from src.models import ClassificationResult, ExtractionResult, RoutingDecision, Ticket

_QUEUE_MAP = {
    "IT Support": "IT Support Team",
    "Billing": "Finance Team",
    "Technical Support": "Engineering Team",
    "Account Management": "Account Management Team",
}


def route_ticket(
    ticket: Ticket,
    extraction: ExtractionResult,
    classification: ClassificationResult,
) -> RoutingDecision:
    category = extraction.get("category", "")
    priority = extraction.get("priority", "medium")

    assigned_queue = _QUEUE_MAP.get(category, "Human Review Queue")

    category_sla = SLA_HOURS.get(category, {})
    sla_hours = category_sla.get(priority, 24)

    sla_deadline = (datetime.now(UTC) + timedelta(hours=sla_hours)).isoformat()
    escalation_flag = classification["requires_human_review"] or priority == "critical"

    reason = (
        f"category={category!r} priority={priority!r} "
        f"tier={classification['routing_tier']} "
        f"sla={sla_hours}h"
    )

    return RoutingDecision(
        ticket_id=ticket["id"],
        assigned_queue=assigned_queue,
        sla_hours=sla_hours,
        sla_deadline=sla_deadline,
        escalation_flag=escalation_flag,
        routing_tier=classification["routing_tier"],
        requires_human_review=classification["requires_human_review"],
        reason=reason,
    )
