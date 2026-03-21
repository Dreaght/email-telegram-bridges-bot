import asyncio
import logging

from settings import load_settings
from client_factory import create_client

logging.basicConfig(level=logging.INFO)

async def main():
    settings = load_settings()

    async with create_client(settings, new_session=True) as client:
        print(client.session.save())

if __name__ == "__main__":
    asyncio.run(main())