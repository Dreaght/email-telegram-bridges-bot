from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

from email_bridge.client.config import ClientConfig
from email_bridge.client.flow import get_request_datetime, parse_utc_iso


class DummyObfuscation:
    def prepare_runtime(self) -> None:
        return

    def looks_like_request(self, data: bytes) -> bool:
        return data.startswith(b"REQ")

    def looks_like_response(self, data: bytes) -> bool:
        return data.startswith(b"RES")

    def verify_request(self, data: bytes):
        raise NotImplementedError

    def sign_request(self, payload: str) -> str:
        return payload

    def encrypt_for_signer(self, signer_id: str, text: str) -> str:
        return text

    def decrypt_response(self, data: bytes) -> str:
        return data.decode()


def test_parse_utc_iso_supports_z_suffix():
    parsed = parse_utc_iso("2026-03-22T10:30:00Z")
    assert parsed == datetime(2026, 3, 22, 10, 30, tzinfo=timezone.utc)


def test_get_request_datetime_uses_obfuscation_layer_detection():
    config = ClientConfig(
        email_address="client@example.com",
        email_password="secret",
        bot_email="bot@example.com",
        imap_host="imap.example.com",
        imap_port=993,
        smtp_host="smtp.example.com",
        smtp_port=465,
        request_min_interval_minutes=30,
        reply_timeout_seconds=30,
        poll_interval_seconds=5,
        state_file=Path(".state"),
        obfuscation_layer="pgp",
    )
    msg = EmailMessage()
    msg["From"] = "client@example.com"
    msg["To"] = "bot@example.com"
    msg["Date"] = "Sun, 22 Mar 2026 12:00:00 +0000"

    sent_at = get_request_datetime(config, msg, b"REQ payload", DummyObfuscation())
    assert sent_at == datetime(2026, 3, 22, 12, 0, tzinfo=timezone.utc)

    rejected = get_request_datetime(config, msg, b"NOT_REQUEST", DummyObfuscation())
    assert rejected is None
