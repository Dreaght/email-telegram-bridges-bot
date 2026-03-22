import logging
import os
import re
import subprocess
import tempfile

from email_bridge.obfuscation.base import ObfuscationLayer, VerificationResult


PGP_SIGNED_RE = re.compile(
    rb"-----BEGIN PGP SIGNED MESSAGE-----.*?-----BEGIN PGP SIGNATURE-----.*?-----END PGP SIGNATURE-----",
    re.DOTALL,
)

PGP_ENCRYPTED_RE = re.compile(
    rb"-----BEGIN PGP MESSAGE-----.*?-----END PGP MESSAGE-----",
    re.DOTALL,
)


def normalize_signer_id(signer_id: str) -> str:
    return re.sub(r"[^0-9A-Fa-f]", "", signer_id).upper()


def resolve_primary_fingerprint(signer_id: str) -> str:
    normalized = normalize_signer_id(signer_id)
    if not normalized:
        return ""

    proc = subprocess.run(
        ["gpg", "--batch", "--with-colons", "--fingerprint", "--list-keys", normalized],
        capture_output=True,
        text=True,
    )

    if proc.returncode != 0:
        logging.warning("Failed to resolve primary fingerprint for %s", normalized)
        return normalized

    saw_pub = False
    for line in proc.stdout.splitlines():
        if not line:
            continue

        parts = line.split(":")
        record_type = parts[0]
        if record_type == "pub":
            saw_pub = True
            continue

        if saw_pub and record_type == "fpr":
            return parts[9].upper()

    return normalized


class PgpObfuscationLayer(ObfuscationLayer):
    def prepare_runtime(self) -> None:
        public_keys = (os.environ.get("GPG_PUBLIC_KEYS") or "").strip()
        if not public_keys:
            return

        proc = subprocess.run(
            ["gpg", "--import"],
            input=public_keys,
            capture_output=True,
            text=True,
        )

        if proc.returncode != 0:
            logging.error("Failed to import GPG public keys")
            logging.error("GPG STDOUT: %s", proc.stdout)
            logging.error("GPG stderr: %s", proc.stderr)
            raise RuntimeError("Unable to import GPG public keys")

        logging.info("GPG public keys imported for PGP obfuscation layer")

    def looks_like_request(self, data: bytes) -> bool:
        return bool(PGP_SIGNED_RE.search(data) or PGP_ENCRYPTED_RE.search(data))

    def looks_like_response(self, data: bytes) -> bool:
        return bool(PGP_ENCRYPTED_RE.search(data))

    def verify_request(self, data: bytes) -> VerificationResult:
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(data)
            path = temp_file.name

        proc = subprocess.run(
            ["gpg", "--status-fd=1", "--verify", path],
            capture_output=True,
            text=True,
        )

        logging.info("GPG stdout:")
        logging.info(proc.stdout)

        logging.info("GPG stderr:")
        logging.info(proc.stderr)

        signer_id = None
        valid = False

        for line in proc.stdout.splitlines():
            if line.startswith("[GNUPG:] VALIDSIG"):
                signer_id = line.split()[2]
                valid = True

            if line.startswith("[GNUPG:] BADSIG"):
                return VerificationResult(valid=False, signer_id=None)

        return VerificationResult(valid=valid, signer_id=signer_id)

    def sign_request(self, payload: str) -> str:
        proc = subprocess.run(
            ["gpg", "--clearsign"],
            input=payload,
            capture_output=True,
            text=True,
        )
        return proc.stdout

    def encrypt_for_signer(self, signer_id: str, text: str) -> str:
        recipient = resolve_primary_fingerprint(signer_id)

        proc = subprocess.run(
            [
                "gpg",
                "--batch",
                "--no-tty",
                "--yes",
                "--trust-model",
                "always",
                "--encrypt",
                "--armor",
                "--output",
                "-",
                "-r",
                recipient,
            ],
            input=text,
            capture_output=True,
            text=True,
        )

        if proc.returncode != 0:
            logging.error("GPG encryption failed for %s", recipient)
            logging.error("GPG STDOUT: %s", proc.stdout)
            logging.error("GPG stderr: %s", proc.stderr)
            return ""

        if not proc.stdout.strip():
            logging.error("GPG encryption returned empty output for %s", recipient)
            logging.error("GPG STDOUT: %s", proc.stdout)
            logging.error("GPG stderr: %s", proc.stderr)
            return ""

        return proc.stdout

    def decrypt_response(self, data: bytes) -> str:
        proc = subprocess.run(
            ["gpg", "--decrypt"],
            input=data,
            capture_output=True,
        )
        return proc.stdout.decode()
