import hashlib
import logging
import sys
import time

from src.audit import AuditLogger
from src.classifier import classify_extraction
from src.config import load_config
from src.data_generator import generate_tickets, save_tickets_csv
from src.database import DatabaseManager
from src.extractor import build_client, extract_tickets
from src.ingestion import load_tickets
from src.metrics import RunMetrics
from src.models import ClassificationResult, ExtractionResult, RoutingDecision
from src.output import write_human_review_queue, write_processing_results
from src.router import route_ticket


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def run_pipeline() -> None:
    config = load_config()
    config.ensure_directories()

    logging.basicConfig(
        level=getattr(logging, config.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )

    print("=" * 60)
    print("AI Support Ticket Triage Pipeline")
    print("=" * 60)

    # Stage 1: Generate synthetic data if needed
    print("\n[1/6] Data generation")
    if not config.input_csv.exists():
        tickets_raw = generate_tickets(config.n_tickets, config.random_seed)
        save_tickets_csv(tickets_raw, config.input_csv)
        print(f"      Generated {len(tickets_raw)} tickets → {config.input_csv}")
    else:
        print(f"      Using existing file: {config.input_csv}")

    # Stage 2: Ingest
    print("\n[2/6] Ingestion")
    tickets = load_tickets(config.input_csv)
    print(f"      Loaded {len(tickets)} tickets")

    with DatabaseManager(config.db_path) as db:
        db.setup_schema()
        audit = AuditLogger(db, config.audit_log_path)

        # Stage 3: Persist tickets
        print("\n[3/6] Persisting tickets to database")
        for ticket in tickets:
            db.insert_ticket(ticket, _sha256(ticket["body"]))
        audit.log_stage("persist_tickets", len(tickets), len(tickets), notes="body stored as SHA-256 hash only")
        print(f"      Persisted {len(tickets)} tickets")

        # Stage 4: Extract (LLM calls) — concurrent, one shared client
        print(f"\n[4/6] Extracting via LLM (up to {config.max_concurrency} in parallel...)")
        client = build_client(config)
        extract_started = time.perf_counter()
        extractions: list[ExtractionResult] = extract_tickets(tickets, config, client)
        extract_elapsed = time.perf_counter() - extract_started
        failed = 0
        for extraction in extractions:
            db.insert_extraction(extraction)
            status = "failed" if extraction["extraction_failed"] else "ok"
            audit.log_event(
                extraction["ticket_id"], "extraction", status,
                f"category={extraction.get('category', '?')!r}",
            )
            if extraction["extraction_failed"]:
                failed += 1
        audit.log_stage("extraction", len(tickets), len(extractions), error_count=failed)
        print(f"      Extraction complete: {len(extractions) - failed} ok, {failed} failed")

        # Stage 5: Classify
        print("\n[5/6] Classifying")
        classifications: list[ClassificationResult] = []
        for extraction in extractions:
            classification = classify_extraction(extraction, config)
            classifications.append(classification)
            db.insert_classification(classification)
            audit.log_event(
                extraction["ticket_id"],
                "classification",
                classification["routing_tier"],
                classification["confidence_tier_reason"],
            )
        auto = sum(1 for c in classifications if c["routing_tier"] == "AUTO_ROUTE")
        soft = sum(1 for c in classifications if c["routing_tier"] == "SOFT_ROUTE")
        human = sum(1 for c in classifications if c["routing_tier"] == "HUMAN_REVIEW")
        audit.log_stage("classification", len(extractions), len(classifications),
                        notes=f"AUTO={auto} SOFT={soft} HUMAN={human}")
        print(f"      AUTO_ROUTE={auto}  SOFT_ROUTE={soft}  HUMAN_REVIEW={human}")

        # Stage 6: Route + output
        print("\n[6/6] Routing and writing output")
        decisions: list[RoutingDecision] = []
        for ticket, extraction, classification in zip(tickets, extractions, classifications, strict=True):
            decision = route_ticket(ticket, extraction, classification)
            decisions.append(decision)
            db.insert_routing_decision(decision)
            audit.log_event(
                ticket["id"], "routing", decision["assigned_queue"],
                f"sla={decision['sla_hours']}h escalation={decision['escalation_flag']}",
            )

        results_path = config.output_dir / "processing_results.csv"
        review_path = config.output_dir / "human_review_queue.csv"
        write_processing_results(decisions, results_path)
        write_human_review_queue(decisions, review_path)
        review_count = sum(1 for d in decisions if d["requires_human_review"])
        audit.log_stage("output", len(decisions), len(decisions),
                        notes=f"results={results_path} review_queue={review_path}")

        print(f"      Results  → {results_path}")
        print(f"      Review Q → {review_path} ({review_count} tickets)")

        # Run metrics: cost, latency, throughput, tier distribution
        metrics = RunMetrics.from_results(extractions, classifications, extract_elapsed)
        db.insert_run_metrics(metrics)
        audit.log_stage("metrics", len(extractions), len(extractions),
                        notes=f"cost_usd={metrics.estimated_cost_usd:.4f}")

        print("\n" + "-" * 60)
        print("Run metrics")
        print("-" * 60)
        for line in metrics.summary_lines():
            print(f"  {line}")

    print("\n" + "=" * 60)
    print(f"Pipeline complete. Database: {config.db_path}")
    print("=" * 60)


if __name__ == "__main__":
    try:
        run_pipeline()
    except ValueError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        sys.exit(1)
