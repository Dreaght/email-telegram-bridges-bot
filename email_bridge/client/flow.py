import email
import imaplib
import json
import smtplib
import time
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import parsedate_to_datetime

from email_bridge.client.config import ClientConfig
from email_bridge.mail import extract_body, normalized_address
from email_bridge.obfuscation.base import ObfuscationLayer
from email_bridge.subject import random_subject


def parse_utc_iso(value: str | None):
    if not value:
        return None

    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def load_last_sent_request_time(config: ClientConfig):
    if not config.state_file.exists():
        return None

    try:
        state = json.loads(config.state_file.read_text())
    except (json.JSONDecodeError, OSError):
        return None

    return parse_utc_iso(state.get("last_request_sent_at"))


def save_last_sent_request_time(config: ClientConfig, sent_at: datetime):
    payload = {"last_request_sent_at": sent_at.astimezone(timezone.utc).isoformat()}
    config.state_file.write_text(json.dumps(payload))


def send_email(config: ClientConfig, body: str):
    msg = EmailMessage()
    msg["Subject"] = random_subject()
    msg["From"] = config.email_address
    msg["To"] = config.bot_email
    msg.set_content(body)

    with smtplib.SMTP_SSL(config.smtp_host, config.smtp_port) as smtp:
        smtp.login(config.email_address, config.email_password)
        smtp.send_message(msg)

    save_last_sent_request_time(config, datetime.now(timezone.utc))


def read_unseen_bot_reply(config: ClientConfig, imap, obfuscation: ObfuscationLayer):
    bot_address = normalized_address(config.bot_email)

    status, messages = imap.search(None, "UNSEEN")
    if status != "OK":
        return None

    ids = messages[0].split()

    for msg_id in ids:
        _, data = imap.fetch(msg_id, "(RFC822)")
        raw = data[0][1]
        msg = email.message_from_bytes(raw)

        from_addr = normalized_address(msg.get("From", ""))
        if from_addr != bot_address:
            continue

        body = extract_body(msg)
        if body and obfuscation.looks_like_response(body):
            imap.store(msg_id, "+FLAGS", "\\Seen")
            return body

    return None


def get_existing_unseen_reply(config: ClientConfig, obfuscation: ObfuscationLayer):
    imap = imaplib.IMAP4_SSL(config.imap_host, config.imap_port)
    imap.login(config.email_address, config.email_password)
    imap.select("INBOX")

    encrypted = read_unseen_bot_reply(config, imap, obfuscation)

    imap.logout()
    return encrypted


def list_sent_mailboxes(imap):
    status, raw_boxes = imap.list()
    if status != "OK" or not raw_boxes:
        return ["Sent"]

    sent_boxes = []

    for entry in raw_boxes:
        line = entry.decode(errors="ignore")
        parts = line.split(' "')
        mailbox = parts[-1].strip('"') if parts else line

        if "\\Sent" in line or mailbox.lower() in {
            "sent",
            "sent messages",
            "sent items",
            "inbox.sent",
            "отправленные",
        }:
            sent_boxes.append(mailbox)

    if not sent_boxes:
        sent_boxes.append("Sent")

    return list(dict.fromkeys(sent_boxes))


def get_request_datetime(config: ClientConfig, msg, body: bytes | None, obfuscation: ObfuscationLayer):
    from_addr = normalized_address(msg.get("From", ""))
    to_addr = normalized_address(msg.get("To", ""))
    if from_addr != normalized_address(config.email_address):
        return None
    if to_addr != normalized_address(config.bot_email):
        return None
    if not body or not obfuscation.looks_like_request(body):
        return None

    date_header = msg.get("Date")
    if not date_header:
        return None

    try:
        dt = parsedate_to_datetime(date_header)
    except (TypeError, ValueError):
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(timezone.utc)


def get_last_request_age_minutes(config: ClientConfig, obfuscation: ObfuscationLayer):
    imap = imaplib.IMAP4_SSL(config.imap_host, config.imap_port)
    imap.login(config.email_address, config.email_password)

    newest = None

    for mailbox in list_sent_mailboxes(imap):
        status, _ = imap.select(mailbox, readonly=True)
        if status != "OK":
            continue

        status, messages = imap.search(None, "ALL")
        if status != "OK":
            continue

        ids = messages[0].split()
        for msg_id in ids[-25:]:
            _, data = imap.fetch(msg_id, "(RFC822)")
            raw = data[0][1]
            msg = email.message_from_bytes(raw)
            body = extract_body(msg)
            sent_at = get_request_datetime(config, msg, body, obfuscation)
            if sent_at and (newest is None or sent_at > newest):
                newest = sent_at

    imap.logout()

    state_time = load_last_sent_request_time(config)
    if state_time and (newest is None or state_time > newest):
        newest = state_time

    if newest is None:
        return None

    age_minutes = (datetime.now(timezone.utc) - newest).total_seconds() / 60.0
    return max(age_minutes, 0.0)


def wait_for_reply(config: ClientConfig, obfuscation: ObfuscationLayer):
    imap = imaplib.IMAP4_SSL(config.imap_host, config.imap_port)
    imap.login(config.email_address, config.email_password)
    imap.select("INBOX")

    start = time.time()

    while time.time() - start < config.reply_timeout_seconds:
        body = read_unseen_bot_reply(config, imap, obfuscation)
        if body:
            imap.logout()
            return body

        time.sleep(config.poll_interval_seconds)

    imap.logout()
    return None


def run_client(config: ClientConfig, obfuscation: ObfuscationLayer):
    print("Checking for unread bot reply...")

    encrypted = get_existing_unseen_reply(config, obfuscation)

    if not encrypted:
        request_age_minutes = get_last_request_age_minutes(config, obfuscation)

        if (
            request_age_minutes is not None
            and request_age_minutes <= config.request_min_interval_minutes
        ):
            print(
                f"Recent request detected ({request_age_minutes:.1f} minutes ago); "
                "won't send a new one"
            )
            print("Waiting for reply...")
            encrypted = wait_for_reply(config, obfuscation)
        else:
            print("Sending request...")

            signed = obfuscation.sign_request("")
            send_email(config, signed)

            print("Waiting for reply...")

            encrypted = wait_for_reply(config, obfuscation)
    else:
        print("Unread reply found, skipping new request")

    if not encrypted:
        print("No reply received")
        return

    print("Decrypting...")
    result = obfuscation.decrypt_response(encrypted)
    print(result)
