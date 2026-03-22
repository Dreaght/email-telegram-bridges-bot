import imaplib
import smtplib
import email
import subprocess
import time
import json
from email.message import EmailMessage
from datetime import datetime, timezone
from email.utils import parseaddr, parsedate_to_datetime
from pathlib import Path
from dotenv import dotenv_values


cfg = {
    **dotenv_values(".env.shared"),
    **dotenv_values(".env.email.secret"),
}

REQUEST_MIN_INTERVAL_MINUTES = int(cfg.get("REQUEST_MIN_INTERVAL_MINUTES", 30))
STATE_FILE = Path(".client_state.json")


def normalized_address(value: str) -> str:
    return parseaddr(value or "")[1].strip().lower()


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


def load_last_sent_request_time():
    if not STATE_FILE.exists():
        return None

    try:
        state = json.loads(STATE_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return None

    return parse_utc_iso(state.get("last_request_sent_at"))


def save_last_sent_request_time(sent_at: datetime):
    payload = {"last_request_sent_at": sent_at.astimezone(timezone.utc).isoformat()}
    STATE_FILE.write_text(json.dumps(payload))


def create_signed_request():
    proc = subprocess.run(
        ["gpg", "--clearsign"],
        input="",
        capture_output=True,
        text=True
    )
    return proc.stdout


def send_email(body: str):
    msg = EmailMessage()
    msg["Subject"] = "req"
    msg["From"] = cfg["EMAIL_ADDRESS"]
    msg["To"] = cfg["BOT_EMAIL"]
    msg.set_content(body)

    with smtplib.SMTP_SSL(cfg["SMTP_HOST"], int(cfg["SMTP_PORT"])) as smtp:
        smtp.login(cfg["EMAIL_ADDRESS"], cfg["EMAIL_PASSWORD"])
        smtp.send_message(msg)

    save_last_sent_request_time(datetime.now(timezone.utc))


def extract_body(msg):
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                return part.get_payload(decode=True)
        return None

    return msg.get_payload(decode=True)


def read_unseen_bot_reply(imap):
    bot_address = normalized_address(cfg["BOT_EMAIL"])

    status, messages = imap.search(None, "UNSEEN")
    ids = messages[0].split()

    for msg_id in ids:
        _, data = imap.fetch(msg_id, "(RFC822)")
        raw = data[0][1]
        msg = email.message_from_bytes(raw)

        from_addr = normalized_address(msg.get("From", ""))
        if from_addr != bot_address:
            continue

        body = extract_body(msg)
        if body and b"BEGIN PGP MESSAGE" in body:
            imap.store(msg_id, "+FLAGS", "\\Seen")
            return body

    return None


def get_existing_unseen_reply():
    imap = imaplib.IMAP4_SSL(cfg["IMAP_HOST"], int(cfg["IMAP_PORT"]))
    imap.login(cfg["EMAIL_ADDRESS"], cfg["EMAIL_PASSWORD"])
    imap.select("INBOX")

    encrypted = read_unseen_bot_reply(imap)

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

    # Preserve order and uniqueness.
    return list(dict.fromkeys(sent_boxes))


def get_request_datetime(msg, body):
    from_addr = normalized_address(msg.get("From", ""))
    to_addr = normalized_address(msg.get("To", ""))
    if from_addr != normalized_address(cfg["EMAIL_ADDRESS"]):
        return None
    if to_addr != normalized_address(cfg["BOT_EMAIL"]):
        return None
    if not body or b"BEGIN PGP SIGNED MESSAGE" not in body:
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


def get_last_request_age_minutes():
    imap = imaplib.IMAP4_SSL(cfg["IMAP_HOST"], int(cfg["IMAP_PORT"]))
    imap.login(cfg["EMAIL_ADDRESS"], cfg["EMAIL_PASSWORD"])

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
            sent_at = get_request_datetime(msg, body)
            if sent_at and (newest is None or sent_at > newest):
                newest = sent_at

    imap.logout()

    state_time = load_last_sent_request_time()
    if state_time and (newest is None or state_time > newest):
        newest = state_time

    if newest is None:
        return None

    age_minutes = (datetime.now(timezone.utc) - newest).total_seconds() / 60.0
    return max(age_minutes, 0.0)


def wait_for_reply():
    timeout = int(cfg.get("REPLY_TIMEOUT_SECONDS", 60))
    interval = int(cfg.get("POLL_INTERVAL_SECONDS", 5))

    imap = imaplib.IMAP4_SSL(cfg["IMAP_HOST"], int(cfg["IMAP_PORT"]))
    imap.login(cfg["EMAIL_ADDRESS"], cfg["EMAIL_PASSWORD"])
    imap.select("INBOX")

    start = time.time()

    while time.time() - start < timeout:
        body = read_unseen_bot_reply(imap)
        if body:
            imap.logout()
            return body

        time.sleep(interval)

    imap.logout()
    return None


def decrypt_message(data: bytes):
    proc = subprocess.run(
        ["gpg", "--decrypt"],
        input=data,
        capture_output=True
    )
    return proc.stdout.decode()


def main():
    print("Checking for unread bot reply...")

    encrypted = get_existing_unseen_reply()

    if not encrypted:
        request_age_minutes = get_last_request_age_minutes()

        if request_age_minutes is not None and request_age_minutes <= REQUEST_MIN_INTERVAL_MINUTES:
            print(
                f"Recent request detected ({request_age_minutes:.1f} minutes ago); "
                "won't send a new one"
            )
            print("Waiting for reply...")
            encrypted = wait_for_reply()
        else:
            print("Sending request...")

            signed = create_signed_request()
            send_email(signed)

            print("Waiting for reply...")

            encrypted = wait_for_reply()
    else:
        print("Unread reply found, skipping new request")

    if not encrypted:
        print("No reply received")
        return

    print("Decrypting...")

    result = decrypt_message(encrypted)
    print(result)


if __name__ == "__main__":
    main()
