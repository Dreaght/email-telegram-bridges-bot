from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values


@dataclass(frozen=True)
class ClientConfig:
    email_address: str
    email_password: str
    bot_email: str

    imap_host: str
    imap_port: int
    smtp_host: str
    smtp_port: int

    request_min_interval_minutes: int
    reply_timeout_seconds: int
    poll_interval_seconds: int
    state_file: Path
    obfuscation_layer: str


def load_client_config() -> ClientConfig:
    raw = {
        **dotenv_values(".env.shared"),
        **dotenv_values(".env.email.secret"),
    }

    return ClientConfig(
        email_address=raw["EMAIL_ADDRESS"],
        email_password=raw["EMAIL_PASSWORD"],
        bot_email=raw["BOT_EMAIL"],
        imap_host=raw["IMAP_HOST"],
        imap_port=int(raw["IMAP_PORT"]),
        smtp_host=raw["SMTP_HOST"],
        smtp_port=int(raw["SMTP_PORT"]),
        request_min_interval_minutes=int(raw.get("REQUEST_MIN_INTERVAL_MINUTES", 30)),
        reply_timeout_seconds=int(raw.get("REPLY_TIMEOUT_SECONDS", 60)),
        poll_interval_seconds=int(raw.get("POLL_INTERVAL_SECONDS", 5)),
        state_file=Path(raw.get("CLIENT_STATE_FILE", ".client_state.json")),
        obfuscation_layer=raw.get("OBFUSCATION_LAYER", "pgp").strip().lower(),
    )

