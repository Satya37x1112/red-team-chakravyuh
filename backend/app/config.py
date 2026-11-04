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
    # Optional per-module keys (e.g. one free key each) to spread request quota.
    # Falls back to openrouter_api_key when a module's own key is blank.
    openrouter_api_key_ddos: str = ""
    openrouter_api_key_bruteforce: str = ""
    openrouter_api_key_ratuba: str = ""
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

    # ---- External tool integrations (all optional, all degrade gracefully) ----
    # CALDERA report analyzer. The AI analysis reuses the OpenRouter key above;
    # caldera_report_dir points at a folder of Caldera operation JSON reports to
    # offer as samples in the UI (defaults to the vendored sample set).
    caldera_report_dir: str = ""

    # Locust load-test adapter (the real DDoS driver behind locust_file_path).
    # Disabled unless locust_enabled is true AND a locustfile + target are set.
    # Even then it only drives an operator-authored locustfile at an authorized
    # target, headless, with the bounded limits below.
    locust_enabled: bool = False
    locust_target_url: str = ""         # e.g. http://10.0.0.5:8080 (authorized lab host)
    locust_max_users: int = 50          # hard cap on simulated users
    locust_max_spawn_rate: int = 10     # hard cap on users spawned per second
    locust_max_run_seconds: int = 120   # hard cap on run duration

    # THC-Hydra login-cracker (the real credential-test driver behind the
    # BruteForce module). Fail-closed, mirroring the Locust gate above: it does
    # nothing unless hydra_enabled is true AND an authorized target AND an
    # operator-provided username list AND password list are set. Even then it
    # only runs that one list pair against that one target, with the attempt
    # count, parallel task count, and wall-clock duration hard-capped below.
    # Run only against a host you own or are authorized to test, on the lab net.
    hydra_bin: str = "hydra"            # path to the hydra binary, or a name on PATH
    hydra_enabled: bool = False
    hydra_target: str = ""              # authorized lab host/IP, e.g. 192.168.56.20
    hydra_service: str = "ssh"          # hydra service module (ssh, ftp, rdp, …)
    hydra_userlist_path: str = ""       # operator-provided username list (one per line)
    hydra_passlist_path: str = ""       # operator-provided password list (one per line)
    hydra_max_tasks: int = 4            # hard cap on parallel connects (hydra -t)
    hydra_max_attempts: int = 500       # hard cap on users×passwords the list pair may hold
    hydra_max_run_seconds: int = 120    # hard cap on wall-clock run time

    # vervet signed adversary-emulation CLI (Rust binary). Path or name on PATH.
    vervet_bin: str = "vervet"
    # Ed25519 seed (64 hex chars) the backend uses to sign scope manifests for the
    # GUI "run scan" action. The authority public key is derived from it. Override
    # in .env for a real engagement; this dev default keeps the lab self-contained.
    vervet_scope_seed: str = "1111111111111111111111111111111111111111111111111111111111111111"
    # Techniques the GUI is allowed to fire. Kept to non-destructive discovery
    # (T1046 = connect-scan). Credential/exploitation techniques stay CLI-only.
    vervet_gui_techniques: str = "T1046"

    @property
    def vervet_gui_technique_list(self) -> list[str]:
        return [t.strip() for t in self.vervet_gui_techniques.split(",") if t.strip()]

    # PentestGPT agent. Console-script name (from its pyproject) or a full path.
    pentestgpt_cmd: str = "pentestgpt-agent"

    def api_key_for(self, kind: str) -> str:
        """The OpenRouter key for a module, falling back to the shared key."""
        per_kind = {
            "ddos": self.openrouter_api_key_ddos,
            "bruteforce": self.openrouter_api_key_bruteforce,
            "ratuba": self.openrouter_api_key_ratuba,
        }.get(kind, "")
        return per_kind or self.openrouter_api_key

    @property
    def fallback_models(self) -> list[str]:
        return [m.strip() for m in self.openrouter_fallback_models.split(",") if m.strip()]


settings = Settings()
