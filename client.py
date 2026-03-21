import imaplib
import smtplib
import email
import subprocess
import time
from email.message import EmailMessage
from dotenv import dotenv_values


cfg = {
    **dotenv_values(".env.shared"),
    **dotenv_values(".env.email.secret"),
}


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


def wait_for_reply():
    timeout = int(cfg.get("REPLY_TIMEOUT_SECONDS", 60))
    interval = int(cfg.get("POLL_INTERVAL_SECONDS", 5))

    imap = imaplib.IMAP4_SSL(cfg["IMAP_HOST"], int(cfg["IMAP_PORT"]))
    imap.login(cfg["EMAIL_ADDRESS"], cfg["EMAIL_PASSWORD"])
    imap.select("INBOX")

    start = time.time()

    while time.time() - start < timeout:
        status, messages = imap.search(None, "UNSEEN")
        ids = messages[0].split()

        for msg_id in ids:
            _, data = imap.fetch(msg_id, "(RFC822)")
            raw = data[0][1]

            msg = email.message_from_bytes(raw)

            body = None
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True)
                        break
            else:
                body = msg.get_payload(decode=True)

            if body and b"BEGIN PGP MESSAGE" in body:
                imap.store(msg_id, "+FLAGS", "\\Seen")
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
    print("Sending request...")

    signed = create_signed_request()
    send_email(signed)

    print("Waiting for reply...")

    encrypted = wait_for_reply()

    if not encrypted:
        print("No reply received")
        return

    print("Decrypting...")

    result = decrypt_message(encrypted)
    print(result)


if __name__ == "__main__":
    main()