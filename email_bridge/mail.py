import email
from email.utils import parseaddr


def parse_email(raw_bytes: bytes):
    return email.message_from_bytes(raw_bytes)


def extract_body(msg) -> bytes | None:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                return part.get_payload(decode=True)
        return None

    return msg.get_payload(decode=True)


def normalized_address(value: str) -> str:
    return parseaddr(value or "")[1].strip().lower()

