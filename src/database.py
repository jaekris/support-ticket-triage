import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from src.metrics import RunMetrics
from src.models import ClassificationResult, ExtractionResult, RoutingDecision, Ticket

CREATE_TICKETS = """
CREATE TABLE IF NOT EXISTS tickets (
    id         TEXT PRIMARY KEY,
    subject    TEXT NOT NULL,
    body_hash  TEXT NOT NULL,
    created_at TEXT NOT NULL,
    source     TEXT NOT NULL
);
"""

CREATE_EXTRACTIONS = """
CREATE TABLE IF NOT EXISTS extractions (
    ticket_id               TEXT PRIMARY KEY,
    category                TEXT,
    priority                TEXT,
    sentiment               TEXT,
    confidence              REAL,
    explanation             TEXT,
    issue_summary           TEXT,
    urgency_indicators_json TEXT,
    model_used              TEXT,
    processed_at            TEXT,
    extraction_failed       INTEGER NOT NULL,
    input_tokens            INTEGER,
    output_tokens           INTEGER,
    latency_ms              REAL
);
"""

CREATE_CLASSIFICATIONS = """
CREATE TABLE IF NOT EXISTS classifications (
    ticket_id             TEXT PRIMARY KEY,
    routing_tier          TEXT NOT NULL,
    requires_human_review INTEGER NOT NULL,
    confidence_tier_reason TEXT
);
"""

CREATE_ROUTING_DECISIONS = """
CREATE TABLE IF NOT EXISTS routing_decisions (
    ticket_id             TEXT PRIMARY KEY,
    assigned_queue        TEXT NOT NULL,
    sla_hours             INTEGER NOT NULL,
    sla_deadline          TEXT NOT NULL,
    escalation_flag       INTEGER NOT NULL,
    reason                TEXT
);
"""

CREATE_AUDIT_LOG = """
CREATE TABLE IF NOT EXISTS audit_log (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    ticket_id TEXT,
    stage     TEXT NOT NULL,
    status    TEXT NOT NULL,
    notes     TEXT
);
"""

CREATE_RUN_METRICS = """
CREATE TABLE IF NOT EXISTS run_metrics (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp           TEXT NOT NULL,
    ticket_count        INTEGER NOT NULL,
    ok_count            INTEGER NOT NULL,
    failed_count        INTEGER NOT NULL,
    total_input_tokens  INTEGER NOT NULL,
    total_output_tokens INTEGER NOT NULL,
    avg_latency_ms      REAL NOT NULL,
    elapsed_seconds     REAL NOT NULL,
    throughput_per_sec  REAL NOT NULL,
    estimated_cost_usd  REAL NOT NULL,
    tier_auto           INTEGER NOT NULL,
    tier_soft           INTEGER NOT NULL,
    tier_human          INTEGER NOT NULL
);
"""


class DatabaseManager:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "DatabaseManager":
        self.connect()
        return self

    def __exit__(self, *_) -> None:
        self.close()

    def setup_schema(self) -> None:
        assert self._conn, "Not connected"
        self._conn.execute(CREATE_TICKETS)
        self._conn.execute(CREATE_EXTRACTIONS)
        self._conn.execute(CREATE_CLASSIFICATIONS)
        self._conn.execute(CREATE_ROUTING_DECISIONS)
        self._conn.execute(CREATE_AUDIT_LOG)
        self._conn.execute(CREATE_RUN_METRICS)
        self._conn.commit()

    def execute(self, sql: str, params: tuple = ()) -> None:
        assert self._conn, "Not connected"
        self._conn.execute(sql, params)
        self._conn.commit()

    def insert_ticket(self, ticket: Ticket, body_hash: str) -> None:
        assert self._conn, "Not connected"
        self._conn.execute(
            "INSERT OR IGNORE INTO tickets (id, subject, body_hash, created_at, source) VALUES (?, ?, ?, ?, ?)",
            (ticket["id"], ticket["subject"], body_hash, ticket["created_at"], ticket["source"]),
        )
        self._conn.commit()

    def insert_extraction(self, extraction: ExtractionResult) -> None:
        assert self._conn, "Not connected"
        self._conn.execute(
            """INSERT OR REPLACE INTO extractions
               (ticket_id, category, priority, sentiment, confidence, explanation,
                issue_summary, urgency_indicators_json, model_used, processed_at, extraction_failed,
                input_tokens, output_tokens, latency_ms)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                extraction["ticket_id"],
                extraction.get("category"),
                extraction.get("priority"),
                extraction.get("sentiment"),
                extraction.get("confidence"),
                extraction.get("explanation"),
                extraction.get("issue_summary"),
                json.dumps(extraction.get("urgency_indicators", [])),
                extraction.get("model_used"),
                extraction.get("processed_at"),
                int(extraction["extraction_failed"]),
                extraction.get("input_tokens", 0),
                extraction.get("output_tokens", 0),
                extraction.get("latency_ms", 0.0),
            ),
        )
        self._conn.commit()

    def insert_classification(self, classification: ClassificationResult) -> None:
        assert self._conn, "Not connected"
        self._conn.execute(
            """INSERT OR REPLACE INTO classifications
               (ticket_id, routing_tier, requires_human_review, confidence_tier_reason)
               VALUES (?, ?, ?, ?)""",
            (
                classification["ticket_id"],
                classification["routing_tier"],
                int(classification["requires_human_review"]),
                classification.get("confidence_tier_reason"),
            ),
        )
        self._conn.commit()

    def insert_routing_decision(self, decision: RoutingDecision) -> None:
        assert self._conn, "Not connected"
        self._conn.execute(
            """INSERT OR REPLACE INTO routing_decisions
               (ticket_id, assigned_queue, sla_hours, sla_deadline, escalation_flag, reason)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                decision["ticket_id"],
                decision["assigned_queue"],
                decision["sla_hours"],
                decision["sla_deadline"],
                int(decision["escalation_flag"]),
                decision.get("reason"),
            ),
        )
        self._conn.commit()

    def insert_run_metrics(self, metrics: RunMetrics) -> None:
        assert self._conn, "Not connected"
        self._conn.execute(
            """INSERT INTO run_metrics
               (timestamp, ticket_count, ok_count, failed_count, total_input_tokens,
                total_output_tokens, avg_latency_ms, elapsed_seconds, throughput_per_sec,
                estimated_cost_usd, tier_auto, tier_soft, tier_human)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                datetime.now(UTC).isoformat(),
                metrics.ticket_count,
                metrics.ok_count,
                metrics.failed_count,
                metrics.total_input_tokens,
                metrics.total_output_tokens,
                metrics.avg_latency_ms,
                metrics.elapsed_seconds,
                metrics.throughput_per_sec,
                metrics.estimated_cost_usd,
                metrics.tier_auto,
                metrics.tier_soft,
                metrics.tier_human,
            ),
        )
        self._conn.commit()
