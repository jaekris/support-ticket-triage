import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import anthropic

from src.config import PipelineConfig
from src.models import ExtractionResult, Ticket
from src.prompts import SYSTEM_PROMPT, TRIAGE_TOOL, build_user_prompt


def build_client(config: PipelineConfig) -> anthropic.Anthropic:
    """Construct an Anthropic client, validating the API key is present.

    Create one client per run and reuse it across tickets rather than building a
    new one per request.
    """
    return anthropic.Anthropic(api_key=config.require_api_key())


def extract_ticket(
    ticket: Ticket,
    config: PipelineConfig,
    client: anthropic.Anthropic | None = None,
) -> ExtractionResult:
    if client is None:
        client = build_client(config)
    last_error: Exception | None = None

    for attempt in range(config.max_retries):
        start = time.perf_counter()
        try:
            response = client.messages.create(  # type: ignore[call-overload]
                model=config.model_name,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                tools=[TRIAGE_TOOL],
                tool_choice={"type": "tool", "name": "triage_ticket"},
                messages=[{"role": "user", "content": build_user_prompt(ticket)}],
            )
            latency_ms = (time.perf_counter() - start) * 1000
            tool_block = next(
                (b for b in response.content if b.type == "tool_use"),
                None,
            )
            if tool_block is None:
                raise ValueError("No tool_use block in response")

            input_tokens, output_tokens = _usage_tokens(response)
            inp = tool_block.input
            return ExtractionResult(
                ticket_id=ticket["id"],
                category=inp.get("category", ""),
                priority=inp.get("priority", ""),
                sentiment=inp.get("sentiment", ""),
                confidence=float(inp.get("confidence", 0.0)),
                explanation=inp.get("explanation", ""),
                issue_summary=inp.get("issue_summary", ""),
                urgency_indicators=inp.get("urgency_indicators", []),
                model_used=config.model_name,
                processed_at=datetime.now(UTC).isoformat(),
                extraction_failed=False,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
            )
        except (anthropic.APIStatusError, anthropic.RateLimitError, ValueError) as exc:
            last_error = exc
            if attempt < config.max_retries - 1:
                delay = config.retry_base_delay_seconds * (2 ** attempt)
                time.sleep(delay)

    return ExtractionResult(
        ticket_id=ticket["id"],
        category="",
        priority="",
        sentiment="",
        confidence=0.0,
        explanation=f"Extraction failed after {config.max_retries} attempts: {last_error}",
        issue_summary="",
        urgency_indicators=[],
        model_used=config.model_name,
        processed_at=datetime.now(UTC).isoformat(),
        extraction_failed=True,
        input_tokens=0,
        output_tokens=0,
        latency_ms=0.0,
    )


def _usage_tokens(response: object) -> tuple[int, int]:
    """Best-effort read of token usage from a response, defaulting to 0.

    Kept defensive so the pipeline tolerates SDK shape changes and test doubles
    that don't populate usage.
    """
    usage = getattr(response, "usage", None)
    try:
        input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
        output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
    except (TypeError, ValueError):
        return 0, 0
    return input_tokens, output_tokens


def extract_tickets(
    tickets: list[Ticket],
    config: PipelineConfig,
    client: anthropic.Anthropic | None = None,
) -> list[ExtractionResult]:
    """Extract a batch of tickets concurrently, preserving input order.

    Runs up to ``config.max_concurrency`` extractions in parallel over a shared
    client. Each extraction keeps its own retry/backoff behavior, and a failure
    in one ticket never aborts the batch (it returns a failed ExtractionResult).
    """
    if not tickets:
        return []
    if client is None:
        client = build_client(config)

    workers = max(1, min(config.max_concurrency, len(tickets)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(lambda t: extract_ticket(t, config, client), tickets))
