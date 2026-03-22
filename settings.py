import os
from dataclasses import dataclass
from dotenv import dotenv_values

@dataclass(frozen=True)
class Settings:
    api_id: int
    api_hash: str
    session: str | None
    proxy: str | None
    mtproxy: str | None

    bot_username: str
    request_command: str
    response_match: str

    messaging_cooldown_hours: int
    response_timeout_seconds: int
    max_response_messages: int

    email_address: str
    email_password: str

    imap_host: str
    imap_port: int
    smtp_host: str
    smtp_port: int

    trusted_fingerprints: set[str]
    obfuscation_layer: str

def load_settings() -> Settings:
    raw = {
        **dotenv_values(".env.shared"),
        **dotenv_values(".env.secret"),
        **os.environ,
    }

    return Settings(
        api_id=int(raw["API_ID"]),
        api_hash=raw["API_HASH"],
        session=raw.get("SESSION"),
        proxy=raw.get("PROXY"),
        mtproxy=raw.get("MTPROXY"),

        bot_username=raw["TOR_BRIDGES_BOT_USERNAME"],
        request_command=raw["REQUEST_COMMAND"],
        response_match=raw["RESPONSE_MATCH"],

        messaging_cooldown_hours=int(raw["MESSAGING_COOLDOWN_HOURS"]),
        response_timeout_seconds=int(raw["RESPONSE_TIMEOUT_SECONDS"]),
        max_response_messages=int(raw["MAX_RESPONSE_MESSAGES"]),

        email_address=raw["EMAIL_ADDRESS"],
        email_password=raw["EMAIL_PASSWORD"],

        imap_host=raw["IMAP_HOST"],
        imap_port=int(raw["IMAP_PORT"]),
        smtp_host=raw["SMTP_HOST"],
        smtp_port=int(raw["SMTP_PORT"]),

        trusted_fingerprints={
            value.strip().upper()
            for value in raw["TRUSTED_FINGERPRINTS"].split(",")
            if value.strip()
        },
        obfuscation_layer=raw.get("OBFUSCATION_LAYER", "pgp").strip().lower(),
    )
