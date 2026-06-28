from src.config import PipelineConfig
from src.models import ClassificationResult, ExtractionResult

SLA_HOURS: dict = {
    "IT Support":          {"critical": 4,  "high": 8,  "medium": 24, "low": 48},
    "Billing":             {"critical": 2,  "high": 4,  "medium": 8,  "low": 24},
    "Technical Support":   {"critical": 1,  "high": 4,  "medium": 24, "low": 72},
    "Account Management":  {"critical": 2,  "high": 4,  "medium": 8,  "low": 24},
}

_ESCALATION_PHRASES = {
    "production down", "data loss", "security breach", "legal",
    "outage", "urgent", "immediately",
}


def _escalation_triggers(urgency_indicators: list[str]) -> list[str]:
    """Return the escalation phrases present in the model's urgency indicators.

    A phrase matches an indicator when *every* word in the phrase appears
    (case-insensitively, as a substring) within that indicator. This catches
    paraphrases like "the production is down right now" for "production down" and
    "urgently" for "urgent", without firing on unrelated text such as
    "production schedule" or "downloaded the report".
    """
    indicators = [i.lower() for i in urgency_indicators]
    triggered = []
    for phrase in sorted(_ESCALATION_PHRASES):
        words = phrase.split()
        if any(all(word in indicator for word in words) for indicator in indicators):
            triggered.append(phrase)
    return triggered


def classify_extraction(
    extraction: ExtractionResult, config: PipelineConfig
) -> ClassificationResult:
    if extraction["extraction_failed"]:
        return ClassificationResult(
            ticket_id=extraction["ticket_id"],
            routing_tier="HUMAN_REVIEW",
            requires_human_review=True,
            confidence_tier_reason="extraction_failed",
        )

    confidence = extraction["confidence"]

    if confidence >= config.confidence_auto_route:
        return ClassificationResult(
            ticket_id=extraction["ticket_id"],
            routing_tier="AUTO_ROUTE",
            requires_human_review=False,
            confidence_tier_reason=f"confidence={confidence:.2f} >= {config.confidence_auto_route}",
        )

    if confidence >= config.confidence_soft_route:
        triggered = _escalation_triggers(extraction.get("urgency_indicators", []))
        if triggered:
            return ClassificationResult(
                ticket_id=extraction["ticket_id"],
                routing_tier="HUMAN_REVIEW",
                requires_human_review=True,
                confidence_tier_reason=(
                    f"SOFT_ROUTE escalated to HUMAN_REVIEW due to urgency indicators: {', '.join(triggered)}"
                ),
            )
        return ClassificationResult(
            ticket_id=extraction["ticket_id"],
            routing_tier="SOFT_ROUTE",
            requires_human_review=False,
            confidence_tier_reason=f"confidence={confidence:.2f} in [{config.confidence_soft_route}, {config.confidence_auto_route})",
        )

    return ClassificationResult(
        ticket_id=extraction["ticket_id"],
        routing_tier="HUMAN_REVIEW",
        requires_human_review=True,
        confidence_tier_reason=f"confidence={confidence:.2f} < {config.confidence_soft_route}",
    )
