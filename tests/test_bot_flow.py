from email.message import EmailMessage
from types import SimpleNamespace

from email_bridge.bot.flow import process_email
from email_bridge.obfuscation.base import VerificationResult


class DummyObfuscation:
    def prepare_runtime(self) -> None:
        return

    def looks_like_request(self, data: bytes) -> bool:
        return data.startswith(b"REQ")

    def looks_like_response(self, data: bytes) -> bool:
        return data.startswith(b"RES")

    def verify_request(self, data: bytes) -> VerificationResult:
        return VerificationResult(valid=True, signer_id="ABCD1234")

    def sign_request(self, payload: str) -> str:
        return f"REQ::{payload}"

    def encrypt_for_signer(self, signer_id: str, text: str) -> str:
        return f"RES::{signer_id}::{text}"

    def decrypt_response(self, data: bytes) -> str:
        return data.decode()


class ImapStub:
    def __init__(self):
        self.stored = []

    def store(self, msg_id, mode, flag):
        self.stored.append((msg_id, mode, flag))


def build_raw_email(body: str) -> bytes:
    msg = EmailMessage()
    msg["From"] = "sender@example.com"
    msg["To"] = "bot@example.com"
    msg["Subject"] = "req"
    msg.set_content(body)
    return msg.as_bytes()


def test_process_email_sends_obfuscated_response_for_trusted_signer():
    settings = SimpleNamespace(
        trusted_fingerprints={"ABCD1234"},
        email_address="bot@example.com",
    )
    imap = ImapStub()
    calls = {}

    def parser():
        return "bridge-line"

    def send_mail(_settings, to_addr, body):
        calls["to_addr"] = to_addr
        calls["body"] = body

    process_email(
        settings=settings,
        obfuscation=DummyObfuscation(),
        imap=imap,
        msg_id=b"1",
        raw=build_raw_email("REQ payload"),
        parser=parser,
        send_mail=send_mail,
    )

    assert calls["to_addr"] == "sender@example.com"
    assert calls["body"] == "RES::ABCD1234::bridge-line"
    assert imap.stored == [(b"1", "+FLAGS", "\\Seen")]


def test_process_email_skips_untrusted_signer():
    settings = SimpleNamespace(
        trusted_fingerprints={"FFFF"},
        email_address="bot@example.com",
    )
    imap = ImapStub()
    sent = {"called": False}

    def send_mail(_settings, _to_addr, _body):
        sent["called"] = True

    process_email(
        settings=settings,
        obfuscation=DummyObfuscation(),
        imap=imap,
        msg_id=b"1",
        raw=build_raw_email("REQ payload"),
        parser=lambda: "bridge-line",
        send_mail=send_mail,
    )

    assert sent["called"] is False
    assert imap.stored == []
