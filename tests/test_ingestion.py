import csv
import tempfile
from pathlib import Path

import pytest

from src.ingestion import load_tickets


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_valid_csv_loads_correctly():
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as tmp:
        path = Path(tmp.name)
    _write_csv(path, [
        {"id": "t1", "subject": "Test", "body": "Body text", "created_at": "2026-01-01T00:00:00+00:00", "source": "email"},
    ], ["id", "subject", "body", "created_at", "source"])
    tickets = load_tickets(path)
    assert len(tickets) == 1
    assert tickets[0]["id"] == "t1"
    assert tickets[0]["subject"] == "Test"


def test_missing_column_raises_value_error():
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as tmp:
        path = Path(tmp.name)
    _write_csv(path, [
        {"id": "t1", "subject": "Test", "body": "Body"},
    ], ["id", "subject", "body"])
    with pytest.raises(ValueError, match="missing required columns"):
        load_tickets(path)


def test_duplicate_ticket_id_drops_second():
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as tmp:
        path = Path(tmp.name)
    _write_csv(path, [
        {"id": "dup", "subject": "First", "body": "B1", "created_at": "2026-01-01T00:00:00+00:00", "source": "email"},
        {"id": "dup", "subject": "Second", "body": "B2", "created_at": "2026-01-02T00:00:00+00:00", "source": "chat"},
    ], ["id", "subject", "body", "created_at", "source"])
    tickets = load_tickets(path)
    assert len(tickets) == 1
    assert tickets[0]["subject"] == "First"
