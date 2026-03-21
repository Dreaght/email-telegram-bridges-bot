import asyncio
import logging
from datetime import datetime, timezone, timedelta

from settings import load_settings
from client_factory import create_client

logging.basicConfig(level=logging.WARNING)


def extract_target(messages, match: str):
    """
    Find first message containing the match string.
    Returns the message object, not text.
    """
    match = match.lower()

    for msg in messages:
        text = msg.text or msg.raw_text
        if text and match in text.lower():
            return msg

    return None


async def request_bridges(client, settings):
    """
    Sends command to bot and waits for responses.
    Stops early if matching message is found.
    """
    async with client.conversation(
        settings.bot_username,
        timeout=settings.response_timeout_seconds
    ) as conv:

        logging.info(f"Requesting bridges from @{settings.bot_username}...")
        await conv.send_message(settings.request_command)

        responses = []

        for _ in range(settings.max_response_messages):
            try:
                msg = await conv.get_response()
                responses.append(msg)

                if extract_target([msg], settings.response_match):
                    break

            except asyncio.TimeoutError:
                logging.warning("Timeout while waiting for bot response.")
                break

        target = extract_target(responses, settings.response_match)
        return target.text.strip("`") if target and target.text else None


async def main():
    settings = load_settings()

    async with create_client(settings) as client:
        messages = await client.get_messages(
            settings.bot_username,
            limit=settings.max_response_messages
        )

        target_msg = extract_target(messages, settings.response_match)

        now = datetime.now(timezone.utc)

        should_send = (
            not target_msg or
            (now - target_msg.date) >
            timedelta(hours=settings.messaging_cooldown_hours)
        )

        if should_send:
            bridges = await request_bridges(client, settings)

            if bridges:
                print(bridges)
            else:
                print("No bridges received.")
        else:
            logging.info("Using cached bridges message.")

            text = target_msg.text or target_msg.raw_text
            if text:
                print(text.strip("`"))
            else:
                print("Cached message has no text.")


if __name__ == "__main__":
    asyncio.run(main())
