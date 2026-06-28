from src.models import Ticket

SYSTEM_PROMPT = """You are an expert support ticket triage specialist. Your job is to analyze incoming support tickets and classify them using the triage_ticket tool.

For each ticket you will:
1. Identify the correct category from the four available options
2. Assign an appropriate priority based on urgency and business impact
3. Assess the customer's sentiment from their message tone
4. Provide a confidence score reflecting how certain you are of the classification
5. Write a concise issue summary (1-2 sentences)
6. List specific urgency indicators found in the text (words/phrases signaling urgency)
7. Explain your classification reasoning

Always call the triage_ticket tool — do not respond with plain text."""


def build_user_prompt(ticket: Ticket) -> str:
    return f"Subject: {ticket['subject']}\n\n{ticket['body']}"


TRIAGE_TOOL: dict = {
    "name": "triage_ticket",
    "description": "Classify and triage a support ticket into the appropriate category, priority, and routing tier.",
    "input_schema": {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "enum": ["IT Support", "Billing", "Technical Support", "Account Management"],
                "description": "The support category this ticket belongs to",
            },
            "priority": {
                "type": "string",
                "enum": ["critical", "high", "medium", "low"],
                "description": "Priority level based on urgency and business impact",
            },
            "sentiment": {
                "type": "string",
                "enum": ["angry", "frustrated", "neutral", "satisfied"],
                "description": "Customer sentiment detected in the ticket",
            },
            "confidence": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "Confidence score for this classification (0.0-1.0)",
            },
            "explanation": {
                "type": "string",
                "description": "Brief explanation of the classification reasoning",
            },
            "issue_summary": {
                "type": "string",
                "description": "Concise 1-2 sentence summary of the core issue",
            },
            "urgency_indicators": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of words or phrases in the ticket that indicate urgency",
            },
        },
        "required": ["category", "priority", "sentiment", "confidence", "explanation", "issue_summary", "urgency_indicators"],
    },
}
