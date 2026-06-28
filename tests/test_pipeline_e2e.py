import csv
import sqlite3
from unittest.mock import MagicMock, patch

import main


def _tool_response(confidence: float) -> MagicMock:
    block = MagicMock()
    block.type = "tool_use"
    block.input = {
        "category": "IT Support",
        "priority": "high",
        "sentiment": "frustrated",
        "confidence": confidence,
        "explanation": "x",
        "issue_summary": "x",
        "urgency_indicators": [],
    }
    msg = MagicMock()
    msg.content = [block]
    msg.usage = MagicMock(input_tokens=100, output_tokens=20)
    return msg


def _configure_env(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("INPUT_CSV", str(tmp_path / "tickets.csv"))
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("DB_PATH", str(tmp_path / "triage.db"))
    monkeypatch.setenv("N_TICKETS", "4")
    monkeypatch.setenv("MAX_CONCURRENCY", "1")  # deterministic side_effect order
    monkeypatch.setenv("RETRY_BASE_DELAY_SECONDS", "0")


def test_pipeline_end_to_end_with_mocked_llm(monkeypatch, tmp_path):
    _configure_env(monkeypatch, tmp_path)

    mock_client = MagicMock()
    # Two high-confidence (AUTO_ROUTE) and two low-confidence (HUMAN_REVIEW).
    mock_client.messages.create.side_effect = [
        _tool_response(0.95),
        _tool_response(0.40),
        _tool_response(0.95),
        _tool_response(0.40),
    ]

    with patch("src.extractor.anthropic.Anthropic", return_value=mock_client):
        main.run_pipeline()

    db_path = tmp_path / "triage.db"
    assert db_path.exists()

    conn = sqlite3.connect(db_path)
    try:
        counts = {
            t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in ("tickets", "extractions", "classifications", "routing_decisions", "run_metrics")
        }
        # The raw body is never persisted — only a hash column exists.
        ticket_cols = {row[1] for row in conn.execute("PRAGMA table_info(tickets)")}
    finally:
        conn.close()

    assert counts["tickets"] == 4
    assert counts["extractions"] == 4
    assert counts["classifications"] == 4
    assert counts["routing_decisions"] == 4
    assert counts["run_metrics"] == 1
    assert "body_hash" in ticket_cols
    assert "body" not in ticket_cols

    out_dir = tmp_path / "out"
    results = out_dir / "processing_results.csv"
    review = out_dir / "human_review_queue.csv"
    assert results.exists() and review.exists()

    with open(results, newline="", encoding="utf-8") as f:
        result_rows = list(csv.DictReader(f))
    with open(review, newline="", encoding="utf-8") as f:
        review_rows = list(csv.DictReader(f))

    assert len(result_rows) == 4
    # The two low-confidence tickets land in the human-review queue.
    assert len(review_rows) == 2
    assert all(r["requires_human_review"] == "True" for r in review_rows)
