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

def load_settings() -> Settings:
    raw = {
        **dotenv_values(".env.shared"),
        **dotenv_values(".env.secret"),
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
    )