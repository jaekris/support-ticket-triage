import csv
import logging
from pathlib import Path

from src.models import Ticket

_REQUIRED_COLUMNS = {"id", "subject", "body", "created_at", "source"}
logger = logging.getLogger(__name__)


def load_tickets(csv_path: Path) -> list[Ticket]:
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("CSV file is empty or has no header")
        missing = _REQUIRED_COLUMNS - set(reader.fieldnames)
        if missing:
            raise ValueError(f"CSV missing required columns: {missing}")

        seen_ids: set = set()
        tickets: list[Ticket] = []
        for row in reader:
            ticket_id = row["id"]
            if ticket_id in seen_ids:
                logger.warning("Duplicate ticket id %s — skipping", ticket_id)
                continue
            seen_ids.add(ticket_id)
            tickets.append(
                Ticket(
                    id=ticket_id,
                    subject=row["subject"],
                    body=row["body"],
                    created_at=row["created_at"],
                    source=row["source"],
                )
            )
    return tickets
