"""Runtime configuration, loaded from environment / .env."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite:///./dev.db"

    # Telemetry
    telemetry_source: str = "none"  # local | winrm | none
    winrm_endpoint: str = ""
    winrm_port: int = 5985
    winrm_user: str = ""
    winrm_password: str = ""
    winrm_transport: str = "ntlm"
    poll_interval: float = 5.0

    # AI engine — all LLM calls route through OpenRouter's OpenAI-compatible API.
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "anthropic/claude-sonnet-4.5"
    # Comma-separated models tried when the primary fails (e.g. out of credits).
    openrouter_fallback_models: str = "openrouter/free"

    # Lab-tool integration placeholders for the (unimplemented) execute() adapters.
    # All read from .env and default to empty, so the app runs without them set;
    # the operator fills these in only when wiring their own authorized adapters.
    hydra_wordlist_dir: str = ""    # BruteForce: directory of operator-provided wordlists
    locust_file_path: str = ""      # DDoS: path to an operator-authored locustfile
    caldera_url: str = ""           # RAT: base URL of the operator's MITRE Caldera server
    caldera_api_key: str = ""       # RAT: Caldera API key (secret; keep in .env only)

    @property
    def fallback_models(self) -> list[str]:
        return [m.strip() for m in self.openrouter_fallback_models.split(",") if m.strip()]


settings = Settings()
