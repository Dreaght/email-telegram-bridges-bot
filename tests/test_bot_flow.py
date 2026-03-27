from email.message import EmailMessage
from types import SimpleNamespace
from unittest.mock import patch

from email_bridge.bot.flow import process_email, run_telegram_parser
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


def test_run_telegram_parser_masks_output_in_github_actions():
    proc = SimpleNamespace(returncode=0, stdout="bridge-1\nbridge-2\n", stderr="")

    with (
        patch("email_bridge.bot.flow.subprocess.run", return_value=proc),
        patch("email_bridge.bot.flow.print") as print_mock,
        patch.dict("os.environ", {"GITHUB_ACTIONS": "true"}, clear=False),
    ):
        out = run_telegram_parser()

    assert out == "bridge-1\nbridge-2"
    assert print_mock.call_count == 2
    print_mock.assert_any_call("::add-mask::bridge-1")
    print_mock.assert_any_call("::add-mask::bridge-2")


def test_run_telegram_parser_does_not_log_parser_stdout_or_stderr_contents():
    proc = SimpleNamespace(returncode=0, stdout="secret-bridge", stderr="secret-error")

    with (
        patch("email_bridge.bot.flow.subprocess.run", return_value=proc),
        patch("email_bridge.bot.flow.logging.warning") as warn_mock,
    ):
        run_telegram_parser()

    logged_text = "\n".join(str(call.args) for call in warn_mock.call_args_list)
    assert "secret-bridge" not in logged_text
    assert "secret-error" not in logged_text
