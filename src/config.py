import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass
class PipelineConfig:
    db_path: Path
    input_csv: Path
    output_dir: Path
    anthropic_api_key: str
    model_name: str
    confidence_auto_route: float
    confidence_soft_route: float
    max_retries: int
    retry_base_delay_seconds: float
    max_concurrency: int
    n_tickets: int
    random_seed: int
    log_level: str

    @property
    def audit_log_path(self) -> Path:
        return self.output_dir / "audit" / "pipeline.log"

    @property
    def has_api_key(self) -> bool:
        return bool(self.anthropic_api_key)

    def require_api_key(self) -> str:
        """Return the API key, or raise a clear error if none is configured.

        The key is never bundled with the app — a client supplies their own via
        the ANTHROPIC_API_KEY environment variable. Call this at the point an
        Anthropic request is about to be made, not at startup.
        """
        if not self.anthropic_api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY is not set. Provide your Anthropic API key via the "
                "ANTHROPIC_API_KEY environment variable (e.g. in a .env file or your "
                "deployment's secret store) so tickets can be sent to the LLM."
            )
        return self.anthropic_api_key

    def ensure_directories(self) -> None:
        self.input_csv.parent.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / "audit").mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)


def load_config() -> PipelineConfig:
    # The API key is intentionally optional here: the app must import and start
    # without one (e.g. to serve /healthz). Key presence is enforced lazily via
    # PipelineConfig.require_api_key() only when an LLM call is about to happen.
    return PipelineConfig(
        db_path=Path(os.getenv("DB_PATH", "data/triage.db")),
        input_csv=Path(os.getenv("INPUT_CSV", "data/sample_tickets.csv")),
        output_dir=Path(os.getenv("OUTPUT_DIR", "data/outputs")),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        model_name=os.getenv("MODEL_NAME", "claude-haiku-4-5-20251001"),
        confidence_auto_route=float(os.getenv("CONFIDENCE_AUTO_ROUTE", "0.85")),
        confidence_soft_route=float(os.getenv("CONFIDENCE_SOFT_ROUTE", "0.60")),
        max_retries=int(os.getenv("MAX_RETRIES", "3")),
        retry_base_delay_seconds=float(os.getenv("RETRY_BASE_DELAY_SECONDS", "2.0")),
        max_concurrency=int(os.getenv("MAX_CONCURRENCY", "5")),
        n_tickets=int(os.getenv("N_TICKETS", "50")),
        random_seed=int(os.getenv("RANDOM_SEED", "42")),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )
