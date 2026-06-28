"""Cost and latency aggregation for a triage run.

Token pricing is in USD per million tokens (input, output). Rates are kept here
as a small, easily-updated table so a client can see and adjust the cost model.
Source: Anthropic pricing for Claude Haiku 4.5 ($1.00 in / $5.00 out per MTok).
"""

from __future__ import annotations

from dataclasses import dataclass

from src.models import ClassificationResult, ExtractionResult

# (input_per_mtok, output_per_mtok) in USD.
PRICING_USD_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-haiku-4-5-20251001": (1.0, 5.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-opus-4-8": (5.0, 25.0),
}

# Used when a model isn't in the table, so cost reporting never crashes a run.
_FALLBACK_RATE: tuple[float, float] = (1.0, 5.0)


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    in_rate, out_rate = PRICING_USD_PER_MTOK.get(model, _FALLBACK_RATE)
    return (input_tokens / 1_000_000) * in_rate + (output_tokens / 1_000_000) * out_rate


@dataclass
class RunMetrics:
    ticket_count: int
    ok_count: int
    failed_count: int
    total_input_tokens: int
    total_output_tokens: int
    total_latency_ms: float
    avg_latency_ms: float
    estimated_cost_usd: float
    elapsed_seconds: float
    throughput_per_sec: float
    tier_auto: int
    tier_soft: int
    tier_human: int

    @classmethod
    def from_results(
        cls,
        extractions: list[ExtractionResult],
        classifications: list[ClassificationResult],
        elapsed_seconds: float,
    ) -> RunMetrics:
        ticket_count = len(extractions)
        ok = sum(1 for e in extractions if not e["extraction_failed"])
        total_in = sum(e["input_tokens"] for e in extractions)
        total_out = sum(e["output_tokens"] for e in extractions)
        total_latency = sum(e["latency_ms"] for e in extractions)
        cost = sum(
            estimate_cost_usd(e["model_used"], e["input_tokens"], e["output_tokens"])
            for e in extractions
        )
        avg_latency = total_latency / ticket_count if ticket_count else 0.0
        throughput = ticket_count / elapsed_seconds if elapsed_seconds > 0 else 0.0

        return cls(
            ticket_count=ticket_count,
            ok_count=ok,
            failed_count=ticket_count - ok,
            total_input_tokens=total_in,
            total_output_tokens=total_out,
            total_latency_ms=total_latency,
            avg_latency_ms=avg_latency,
            estimated_cost_usd=cost,
            elapsed_seconds=elapsed_seconds,
            throughput_per_sec=throughput,
            tier_auto=sum(1 for c in classifications if c["routing_tier"] == "AUTO_ROUTE"),
            tier_soft=sum(1 for c in classifications if c["routing_tier"] == "SOFT_ROUTE"),
            tier_human=sum(1 for c in classifications if c["routing_tier"] == "HUMAN_REVIEW"),
        )

    def cost_per_ticket_usd(self) -> float:
        return self.estimated_cost_usd / self.ticket_count if self.ticket_count else 0.0

    def summary_lines(self) -> list[str]:
        return [
            f"tickets={self.ticket_count} ok={self.ok_count} failed={self.failed_count}",
            f"tiers: AUTO={self.tier_auto} SOFT={self.tier_soft} HUMAN={self.tier_human}",
            f"tokens: in={self.total_input_tokens} out={self.total_output_tokens}",
            f"latency: avg={self.avg_latency_ms:.0f}ms total={self.total_latency_ms:.0f}ms",
            f"throughput: {self.throughput_per_sec:.2f} tickets/sec over {self.elapsed_seconds:.1f}s",
            f"est. cost: ${self.estimated_cost_usd:.4f} total (${self.cost_per_ticket_usd():.5f}/ticket)",
        ]
