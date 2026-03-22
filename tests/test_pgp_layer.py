from types import SimpleNamespace
from unittest.mock import patch

from email_bridge.obfuscation.pgp import PgpObfuscationLayer, normalize_signer_id


def test_normalize_signer_id_strips_non_hex():
    assert normalize_signer_id("ab cd-12:34") == "ABCD1234"


def test_verify_request_extracts_valid_signer():
    layer = PgpObfuscationLayer()

    with patch("email_bridge.obfuscation.pgp.subprocess.run") as run_mock:
        run_mock.return_value = SimpleNamespace(
            stdout="[GNUPG:] VALIDSIG AAAABBBBCCCCDDDD\n",
            stderr="",
        )
        result = layer.verify_request(b"signed payload")

    assert result.valid is True
    assert result.signer_id == "AAAABBBBCCCCDDDD"


def test_verify_request_rejects_bad_signature():
    layer = PgpObfuscationLayer()

    with patch("email_bridge.obfuscation.pgp.subprocess.run") as run_mock:
        run_mock.return_value = SimpleNamespace(
            stdout="[GNUPG:] BADSIG bad\n",
            stderr="",
        )
        result = layer.verify_request(b"signed payload")

    assert result.valid is False
    assert result.signer_id is None


def test_prepare_runtime_imports_keys_when_present():
    layer = PgpObfuscationLayer()

    with (
        patch.dict("os.environ", {"GPG_PUBLIC_KEYS": "PUBLIC KEY DATA"}, clear=False),
        patch("email_bridge.obfuscation.pgp.subprocess.run") as run_mock,
    ):
        run_mock.return_value = SimpleNamespace(returncode=0, stdout="ok", stderr="")
        layer.prepare_runtime()

    run_mock.assert_called_once()


def test_prepare_runtime_skips_when_no_keys():
    layer = PgpObfuscationLayer()

    with (
        patch.dict("os.environ", {}, clear=True),
        patch("email_bridge.obfuscation.pgp.subprocess.run") as run_mock,
    ):
        layer.prepare_runtime()

    run_mock.assert_not_called()
