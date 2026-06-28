import csv
import random
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from src.models import Ticket

_IT_SUBJECTS = [
    "Password reset request",
    "VPN access not working",
    "Software installation needed",
    "Laptop keeps crashing",
    "Printer not responding",
    "Cannot login to email",
    "Two-factor auth locked out",
    "New computer setup",
    "Remote desktop connection failing",
    "Shared drive access denied",
]

_IT_BODIES = [
    "I need to reset my password urgently. I'm locked out and have a meeting in 20 minutes.",
    "My VPN stopped working this morning. I can't access any internal resources and need help immediately.",
    "Please install Adobe Acrobat Pro on my machine. Our department has a license.",
    "My laptop crashes with a blue screen every few hours. This is making it impossible to work.",
    "The office printer on floor 3 shows offline. Several people are waiting to print documents.",
    "I cannot login to my work email. It says my account is disabled but I haven't been notified of any changes.",
    "I was locked out of my two-factor authentication after changing phones. Can you help restore access?",
    "I have a new computer and need the standard software suite installed and my files migrated.",
    "Remote desktop to the server is failing with 'connection refused'. I need access for a report due today.",
    "I was denied access to the shared marketing drive. My manager said I should have permissions.",
]

_BILLING_SUBJECTS = [
    "Invoice dispute - overcharged",
    "Requesting payment plan",
    "Subscription tier change",
    "Unexpected charge on account",
    "Billing address update",
    "Request for refund",
    "Annual vs monthly billing switch",
    "Tax exemption certificate",
    "Invoice not received",
    "Double charged this month",
]

_BILLING_BODIES = [
    "I was charged $450 but our contract says $350 per month. Please review invoice #INV-2024-0892 and issue a correction.",
    "Due to financial difficulties we'd like to request a payment plan for our outstanding balance of $1,200.",
    "We'd like to downgrade from the Enterprise plan to Professional. Please confirm the new monthly rate.",
    "There's a $99 charge on my account dated March 15th that I don't recognize. Please investigate.",
    "Our company address changed. Please update billing to 123 New Street, Chicago IL 60601.",
    "I cancelled my subscription on March 1st but was still charged for March. I'd like a refund.",
    "We're currently on monthly billing and would like to switch to annual to take advantage of the discount.",
    "We are a non-profit and qualify for tax exemption. I'm attaching our certificate - please remove tax charges.",
    "I haven't received my invoice for last month. Please resend to billing@company.com.",
    "I was charged twice on April 3rd - two identical $299 charges. Please refund the duplicate.",
]

_TECHNICAL_SUBJECTS = [
    "API returning 500 errors",
    "Feature not working as expected",
    "Integration failure with third-party service",
    "System running very slowly",
    "Data export not completing",
    "Authentication token expiring too quickly",
    "Webhook events not triggering",
    "Search returning wrong results",
    "File upload failing for large files",
    "Dashboard charts showing incorrect data",
]

_TECHNICAL_BODIES = [
    "Our API calls to /api/v2/orders have been returning 500 errors since 2pm EST. This is affecting production. Logs attached.",
    "The bulk import feature stopped working after your last update. It processes some records then silently fails.",
    "Our Salesforce integration stopped syncing data last night. Both sides show connected but no records are flowing.",
    "The application is extremely slow today - page loads taking 30+ seconds. We have a demo in 2 hours.",
    "Data exports for our Q1 report are stuck at 67% and never complete. We've tried 3 times with the same result.",
    "Our authentication tokens are expiring after 15 minutes instead of the 1-hour documented. This is breaking our mobile app.",
    "Webhook events for order.created are not firing. We've verified the endpoint and it was working yesterday.",
    "Full-text search is returning completely unrelated results. Searching for 'invoice' returns customer records.",
    "File uploads fail with a 413 error for anything over 5MB. The documentation says 50MB is supported.",
    "The revenue chart on our dashboard shows $0 for March but we can see transactions in the database.",
]

_ACCOUNT_SUBJECTS = [
    "Update profile information",
    "Request account closure",
    "Upgrade to premium tier",
    "Remove user access",
    "Change primary contact email",
    "Add team member seats",
    "Transfer account ownership",
    "Enable SSO for organization",
    "Download account data",
    "Reset organization settings",
]

_ACCOUNT_BODIES = [
    "I need to update my company name and phone number in my profile. The company was recently rebranded.",
    "We've decided not to renew and would like to close our account. Please confirm the process and data retention policy.",
    "We've grown significantly and need to upgrade to Premium. Please provide pricing and the upgrade process.",
    "Employee John Smith (john.smith@company.com) left the company last Friday. Please revoke his access immediately.",
    "Our primary contact email needs to change from old@company.com to new@company.com for all communications.",
    "We need to add 5 more user seats to our account. Please let me know how to purchase additional licenses.",
    "I'm the new IT director and need to transfer account ownership from the previous director to myself.",
    "We'd like to enable SSO with our Azure AD setup. Can you walk us through the configuration process?",
    "Under GDPR I'd like to download all data associated with our account before we migrate to another provider.",
    "After some testing we made changes to our organization settings that we'd like to revert. Is that possible?",
]

_CATEGORY_DATA = {
    "IT Support": (_IT_SUBJECTS, _IT_BODIES),
    "Billing": (_BILLING_SUBJECTS, _BILLING_BODIES),
    "Technical Support": (_TECHNICAL_SUBJECTS, _TECHNICAL_BODIES),
    "Account Management": (_ACCOUNT_SUBJECTS, _ACCOUNT_BODIES),
}

_SOURCES = ["email", "web_form", "chat", "phone_transcript"]


def generate_tickets(n_records: int = 50, seed: int = 42) -> list[Ticket]:
    rng = random.Random(seed)
    tickets: list[Ticket] = []
    categories = list(_CATEGORY_DATA.keys())
    per_category = n_records // len(categories)
    remainder = n_records % len(categories)

    base_time = datetime(2026, 1, 1, tzinfo=UTC)

    for cat_idx, category in enumerate(categories):
        subjects, bodies = _CATEGORY_DATA[category]
        count = per_category + (1 if cat_idx < remainder else 0)
        for _ in range(count):
            subject_idx = rng.randrange(len(subjects))
            body_idx = rng.randrange(len(bodies))
            source_idx = rng.randrange(len(_SOURCES))
            offset_hours = rng.randrange(24 * 90)
            created_at = (base_time + timedelta(hours=offset_hours)).isoformat()
            ticket: Ticket = {
                "id": str(uuid.UUID(int=rng.getrandbits(128))),
                "subject": subjects[subject_idx],
                "body": bodies[body_idx],
                "created_at": created_at,
                "source": _SOURCES[source_idx],
            }
            tickets.append(ticket)

    rng.shuffle(tickets)
    return tickets


def save_tickets_csv(tickets: list[Ticket], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "subject", "body", "created_at", "source"])
        writer.writeheader()
        writer.writerows(tickets)
