from typing import TypedDict


class Ticket(TypedDict):
    id: str
    subject: str
    body: str
    created_at: str
    source: str


class ExtractionResult(TypedDict):
    ticket_id: str
    category: str
    priority: str
    sentiment: str
    confidence: float
    explanation: str
    issue_summary: str
    urgency_indicators: list[str]
    model_used: str
    processed_at: str
    extraction_failed: bool
    input_tokens: int
    output_tokens: int
    latency_ms: float


class ClassificationResult(TypedDict):
    ticket_id: str
    routing_tier: str  # "AUTO_ROUTE" | "SOFT_ROUTE" | "HUMAN_REVIEW"
    requires_human_review: bool
    confidence_tier_reason: str


class RoutingDecision(TypedDict):
    ticket_id: str
    assigned_queue: str
    sla_hours: int
    sla_deadline: str
    escalation_flag: bool
    routing_tier: str
    requires_human_review: bool
    reason: str
