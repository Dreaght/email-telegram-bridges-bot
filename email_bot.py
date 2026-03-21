import logging
logging.basicConfig(level=logging.INFO)

import sys
import imaplib
import smtplib
import email
import subprocess
from email.message import EmailMessage
import re

from settings import load_settings

PGP_SIGNED_RE = re.compile(
    rb"-----BEGIN PGP SIGNED MESSAGE-----.*?-----BEGIN PGP SIGNATURE-----.*?-----END PGP SIGNATURE-----",
    re.DOTALL
)

PGP_ENCRYPTED_RE = re.compile(
    rb"-----BEGIN PGP MESSAGE-----.*?-----END PGP MESSAGE-----",
    re.DOTALL
)

def fetch_unseen(settings):
    imap = imaplib.IMAP4_SSL(settings.imap_host, settings.imap_port)
    imap.login(settings.email_address, settings.email_password)
    imap.select("INBOX")

    status, messages = imap.search(None, "UNSEEN")
    ids = messages[0].split()

    for msg_id in ids:
        _, data = imap.fetch(msg_id, "(RFC822)")
        raw = data[0][1]

        yield imap, msg_id, raw

    imap.close()
    imap.logout()


def parse_email(raw_bytes):
    return email.message_from_bytes(raw_bytes)


def extract_body(msg):
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                return part.get_payload(decode=True)
    else:
        return msg.get_payload(decode=True)

    return None


def verify_signature(data: bytes):
    import tempfile

    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(data)
        path = f.name

    proc = subprocess.run(
        ["gpg", "--status-fd=1", "--verify", path],
        capture_output=True,
        text=True
    )

    logging.info("GPG stdout:")
    logging.info(proc.stdout)

    logging.info("GPG stderr:")
    logging.info(proc.stderr)

    fingerprint = None
    valid = False

    for line in proc.stdout.splitlines():
        if line.startswith("[GNUPG:] VALIDSIG"):
            fingerprint = line.split()[2]
            valid = True

        if line.startswith("[GNUPG:] BADSIG"):
            return False, None

    return valid, fingerprint


def encrypt_output(fingerprint: str, text: str):
    proc = subprocess.run(
        [
            "gpg",
            "--batch",
            "--yes",
            "--trust-model", "always",
            "--encrypt",
            "--armor",
            "-r", fingerprint
        ],
        input=text,
        capture_output=True,
        text=True
    )

    if proc.returncode != 0:
        logging.error(f"GPG encryption failed for {fingerprint}")
        logging.error(f"GPG STDOUT: {proc.stdout}")
        logging.error(f"GPG Stderr: {proc.stderr}")
        return ""

    return proc.stdout


def run_telegram_parser():
    proc = subprocess.run(
        [sys.executable, "main.py"],
        capture_output=True,
        text=True
    )

    logging.info("Telegram stdout:")
    logging.info(proc.stdout)

    logging.info("Telegram stderr:")
    logging.info(proc.stderr)

    return proc.stdout.strip()


def send_email(settings, to_addr, body):
    msg = EmailMessage()
    msg["Subject"] = "Re: bridges"
    msg["From"] = settings.email_address
    msg["To"] = to_addr
    msg.set_content(body)

    with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port) as smtp:
        smtp.login(settings.email_address, settings.email_password)
        smtp.send_message(msg)


def looks_like_pgp(data: bytes) -> bool:
    return bool(
        PGP_SIGNED_RE.search(data) or
        PGP_ENCRYPTED_RE.search(data)
    )


def process_email(settings, imap, msg_id, raw):
    msg = parse_email(raw)

    logging.info("Processing new email")

    body = extract_body(msg)
    if not body:
        logging.info("No body found")
        return

    logging.info(f"Body length: {len(body)}")

    if len(body) > 100_000:
        logging.info("Body too large")
        return

    if not looks_like_pgp(body):
        logging.info("Not PGP format")
        return

    logging.info("PGP format detected")

    valid, fingerprint = verify_signature(body)

    logging.info(f"GPG result: valid={valid}, fingerprint={fingerprint}")

    if not valid:
        logging.info("Signature invalid")
        return

    if fingerprint not in settings.trusted_fingerprints:
        logging.info(f"Fingerprint not trusted: {fingerprint}")
        return

    bridges = run_telegram_parser()
    logging.info(f"Bridges output: {bridges!r}")

    if not bridges:
        logging.info("No bridges returned")
        return

    encrypted = encrypt_output(fingerprint, bridges)
    logging.info(f"Encrypted output length: {len(encrypted)}")

    if not encrypted.strip():
        logging.info("Encryption failed or empty output")
        return

    send_email(settings, msg.get("From"), encrypted)
    logging.info("Email sent")

    imap.store(msg_id, "+FLAGS", "\\Seen")


def main():
    settings = load_settings()

    for imap, msg_id, raw in fetch_unseen(settings):
        process_email(settings, imap, msg_id, raw)


if __name__ == "__main__":
    main()