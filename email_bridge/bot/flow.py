import imaplib
import logging
import smtplib
import subprocess
import sys
from email.message import EmailMessage

from email_bridge.mail import extract_body, parse_email
from email_bridge.obfuscation.base import ObfuscationLayer
from email_bridge.obfuscation.pgp import normalize_signer_id
from settings import load_settings


def fetch_unseen(settings):
    imap = imaplib.IMAP4_SSL(settings.imap_host, settings.imap_port)
    imap.login(settings.email_address, settings.email_password)
    imap.select("INBOX")

    status, messages = imap.search(None, "UNSEEN")
    if status != "OK":
        imap.close()
        imap.logout()
        return

    ids = messages[0].split()

    for msg_id in ids:
        _, data = imap.fetch(msg_id, "(RFC822)")
        raw = data[0][1]
        yield imap, msg_id, raw

    imap.close()
    imap.logout()


def run_telegram_parser() -> str:
    proc = subprocess.run(
        [sys.executable, "main.py"],
        capture_output=True,
        text=True,
    )

    logging.info("Telegram stdout:")
    logging.info(proc.stdout)

    logging.info("Telegram stderr:")
    logging.info(proc.stderr)

    return proc.stdout.strip()


def send_email(settings, to_addr: str, body: str):
    msg = EmailMessage()
    msg["Subject"] = "Re: bridges"
    msg["From"] = settings.email_address
    msg["To"] = to_addr
    msg.set_content(body)

    with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port) as smtp:
        smtp.login(settings.email_address, settings.email_password)
        smtp.send_message(msg)


def process_email(
    settings,
    obfuscation: ObfuscationLayer,
    imap,
    msg_id,
    raw: bytes,
    parser=run_telegram_parser,
    send_mail=send_email,
):
    msg = parse_email(raw)

    logging.info("Processing new email")

    body = extract_body(msg)
    if not body:
        logging.info("No body found")
        return

    logging.info("Body length: %d", len(body))

    if len(body) > 100_000:
        logging.info("Body too large")
        return

    if not obfuscation.looks_like_request(body):
        logging.info("Request format mismatch")
        return

    verification = obfuscation.verify_request(body)

    logging.info("Verify result: valid=%s signer_id=%s", verification.valid, verification.signer_id)

    if not verification.valid:
        logging.info("Signature invalid")
        return

    normalized_signer = normalize_signer_id(verification.signer_id or "")
    if normalized_signer not in settings.trusted_fingerprints:
        logging.info("Signer not trusted: %s", verification.signer_id)
        return

    bridges = parser()
    logging.info("Bridges output: %r", bridges)

    if not bridges:
        logging.info("No bridges returned")
        return

    encrypted = obfuscation.encrypt_for_signer(normalized_signer, bridges)
    logging.info("Encrypted output length: %d", len(encrypted))

    if not encrypted.strip():
        logging.info("Encryption failed or empty output")
        return

    send_mail(settings, msg.get("From"), encrypted)
    logging.info("Email sent")

    imap.store(msg_id, "+FLAGS", "\\Seen")


def run_bot(settings, obfuscation: ObfuscationLayer):
    for imap, msg_id, raw in fetch_unseen(settings):
        process_email(settings, obfuscation, imap, msg_id, raw)


def main(obfuscation: ObfuscationLayer):
    settings = load_settings()
    run_bot(settings, obfuscation)

