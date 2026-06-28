import logging
from datetime import UTC, datetime
from pathlib import Path

from src.database import DatabaseManager


class AuditLogger:
    def __init__(self, db: DatabaseManager, log_file: Path) -> None:
        self.db = db
        self.log_file = log_file
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self._file_logger = self._setup_file_logger()

    def log_stage(
        self,
        stage: str,
        records_in: int,
        records_out: int,
        error_count: int = 0,
        warning_count: int = 0,
        notes: str = "",
    ) -> None:
        timestamp = datetime.now(UTC).isoformat()
        self.db.execute(
            """INSERT INTO audit_log (timestamp, ticket_id, stage, status, notes)
               VALUES (?, ?, ?, ?, ?)""",
            (timestamp, None, stage, f"in={records_in} out={records_out} errors={error_count} warnings={warning_count}", notes),
        )
        self._file_logger.info(
            "%s | stage=%-20s in=%-6d out=%-6d errors=%-4d warnings=%-4d | %s",
            timestamp, stage, records_in, records_out, error_count, warning_count, notes,
        )

    def log_event(self, ticket_id: str, stage: str, status: str, notes: str) -> None:
        timestamp = datetime.now(UTC).isoformat()
        self.db.execute(
            """INSERT INTO audit_log (timestamp, ticket_id, stage, status, notes)
               VALUES (?, ?, ?, ?, ?)""",
            (timestamp, ticket_id, stage, status, notes),
        )
        self._file_logger.info(
            "%s | ticket=%-36s stage=%-20s status=%-10s | %s",
            timestamp, ticket_id, stage, status, notes,
        )

    def _setup_file_logger(self) -> logging.Logger:
        logger = logging.getLogger(f"audit.{id(self)}")
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            handler = logging.FileHandler(self.log_file, encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(message)s"))
            logger.addHandler(handler)
        return logger
