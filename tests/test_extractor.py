from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock, patch

import anthropic

from src.config import PipelineConfig
from src.extractor import extract_ticket, extract_tickets
from src.models import Ticket


def _make_config() -> PipelineConfig:
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


def _make_ticket() -> Ticket:
    return Ticket(id="ticket-1", subject="Help!", body="I need help urgently.", created_at="2026-01-01T00:00:00+00:00", source="email")


def _mock_llm_response(tool_input: dict) -> MagicMock:
    block = MagicMock()
    block.type = "tool_use"
    block.input = tool_input
    msg = MagicMock()
    msg.content = [block]
    msg.stop_reason = "tool_use"
    return msg


@patch("src.extractor.anthropic.Anthropic")
def test_successful_extraction(mock_anthropic_cls):
    tool_input = {
        "category": "IT Support",
        "priority": "high",
        "sentiment": "frustrated",
        "confidence": 0.92,
        "explanation": "User locked out",
        "issue_summary": "Password reset needed",
        "urgency_indicators": ["urgently"],
    }
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_llm_response(tool_input)
    mock_anthropic_cls.return_value = mock_client

    result = extract_ticket(_make_ticket(), _make_config())

    assert result["extraction_failed"] is False
    assert result["category"] == "IT Support"
    assert result["priority"] == "high"
    assert result["confidence"] == 0.92
    assert result["urgency_indicators"] == ["urgently"]
    assert result["ticket_id"] == "ticket-1"


@patch("src.extractor.anthropic.Anthropic")
def test_injected_client_is_reused_not_reconstructed(mock_anthropic_cls):
    """When a client is injected, the extractor must not build its own — this is
    what lets the batch pipeline share one client across many tickets."""
    tool_input = {
        "category": "Billing",
        "priority": "low",
        "sentiment": "neutral",
        "confidence": 0.9,
        "explanation": "x",
        "issue_summary": "x",
        "urgency_indicators": [],
    }
    injected = MagicMock()
    injected.messages.create.return_value = _mock_llm_response(tool_input)

    result = extract_ticket(_make_ticket(), _make_config(), client=injected)

    assert result["extraction_failed"] is False
    injected.messages.create.assert_called_once()
    mock_anthropic_cls.assert_not_called()


@patch("src.extractor.time.sleep")
@patch("src.extractor.anthropic.Anthropic")
def test_all_retries_exhausted_returns_failed(mock_anthropic_cls, mock_sleep):
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = anthropic.RateLimitError(
        message="rate limit", response=MagicMock(status_code=429), body={}
    )
    mock_anthropic_cls.return_value = mock_client

    result = extract_ticket(_make_ticket(), _make_config())

    assert result["extraction_failed"] is True
    assert result["confidence"] == 0.0


@patch("src.extractor.time.sleep")
@patch("src.extractor.anthropic.Anthropic")
def test_retry_count_on_two_failures_then_success(mock_anthropic_cls, mock_sleep):
    tool_input = {
        "category": "Billing",
        "priority": "medium",
        "sentiment": "neutral",
        "confidence": 0.88,
        "explanation": "Invoice dispute",
        "issue_summary": "Overcharged",
        "urgency_indicators": [],
    }
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = [
        anthropic.RateLimitError(message="rate limit", response=MagicMock(status_code=429), body={}),
        anthropic.RateLimitError(message="rate limit", response=MagicMock(status_code=429), body={}),
        _mock_llm_response(tool_input),
    ]
    mock_anthropic_cls.return_value = mock_client

    result = extract_ticket(_make_ticket(), _make_config())

    assert mock_client.messages.create.call_count == 3
    assert result["extraction_failed"] is False


@patch("src.extractor.time.sleep")
@patch("src.extractor.anthropic.Anthropic")
def test_exponential_backoff_delays(mock_anthropic_cls, mock_sleep):
    config = replace(_make_config(), max_retries=3, retry_base_delay_seconds=2.0)
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = anthropic.RateLimitError(
        message="rate limit", response=MagicMock(status_code=429), body={}
    )
    mock_anthropic_cls.return_value = mock_client

    extract_ticket(_make_ticket(), config)

    delays = [call.args[0] for call in mock_sleep.call_args_list]
    assert delays == [2.0, 4.0]


def _tool_response_for(ticket_subject: str) -> MagicMock:
    return _mock_llm_response({
        "category": "IT Support",
        "priority": "medium",
        "sentiment": "neutral",
        "confidence": 0.9,
        "explanation": ticket_subject,
        "issue_summary": ticket_subject,
        "urgency_indicators": [],
    })


def test_extract_tickets_preserves_order_with_shared_client():
    tickets = [
        Ticket(id=f"t{i}", subject=f"s{i}", body=f"b{i}",
               created_at="2026-01-01T00:00:00+00:00", source="email")
        for i in range(8)
    ]
    client = MagicMock()
    # Each call echoes the body it received so we can verify ordering survives
    # the thread pool.
    client.messages.create.side_effect = lambda **kw: _tool_response_for(
        kw["messages"][0]["content"]
    )

    results = extract_tickets(tickets, _make_config(), client=client)

    assert [r["ticket_id"] for r in results] == [t["id"] for t in tickets]
    assert all(r["extraction_failed"] is False for r in results)
    assert client.messages.create.call_count == len(tickets)


def test_extract_tickets_empty_list_makes_no_calls():
    client = MagicMock()
    assert extract_tickets([], _make_config(), client=client) == []
    client.messages.create.assert_not_called()
