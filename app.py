"""HTTP service for the triage pipeline.

Exposes the same classification + routing logic as the batch pipeline over a
REST API, so a client can plug in their own ANTHROPIC_API_KEY and send tickets
to their LLM. The app starts without a key (so /healthz works for liveness
probes); /triage enforces the key at request time.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.classifier import classify_extraction
from src.config import load_config
from src.extractor import extract_ticket
from src.models import Ticket
from src.router import route_ticket

app = FastAPI(
    title="AI Support Ticket Triage",
    version="1.0.0",
    description="Classify, score, and route support tickets with Claude.",
)


class TriageRequest(BaseModel):
    subject: str = Field(..., min_length=1, description="Ticket subject line")
    body: str = Field(..., min_length=1, description="Ticket body text")
    source: str = Field("api", description="Origin of the ticket (e.g. email, web, chat)")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    """Liveness probe — always succeeds, requires no API key."""
    return {"status": "ok"}


@app.get("/readyz")
def readyz() -> dict[str, Any]:
    """Readiness probe — reports whether an API key is configured."""
    config = load_config()
    return {
        "status": "ready" if config.has_api_key else "no_api_key",
        "api_key_configured": config.has_api_key,
        "model": config.model_name,
    }


@app.post("/triage")
def triage(request: TriageRequest) -> dict[str, Any]:
    """Triage a single ticket: extract → classify → route."""
    config = load_config()
    if not config.has_api_key:
        raise HTTPException(
            status_code=503,
            detail=(
                "ANTHROPIC_API_KEY is not configured. Set it in the service environment "
                "so tickets can be sent to the LLM."
            ),
        )

    ticket = Ticket(
        id=str(uuid.uuid4()),
        subject=request.subject,
        body=request.body,
        created_at=datetime.now(UTC).isoformat(),
        source=request.source,
    )

    extraction = extract_ticket(ticket, config)
    classification = classify_extraction(extraction, config)
    decision = route_ticket(ticket, extraction, classification)

    # Note: the raw ticket body is intentionally not echoed back.
    return {
        "ticket_id": ticket["id"],
        "extraction": extraction,
        "classification": classification,
        "routing": decision,
    }
