from telethon import TelegramClient, connection
from telethon.sessions import StringSession
from urllib.parse import urlparse

def build_proxy(settings):
    if settings.mtproxy:
        u = urlparse(settings.mtproxy)
        return connection.ConnectionTcpFull, (u.hostname, u.port, u.password)

    if settings.proxy:
        u = urlparse(settings.proxy)
        return connection.ConnectionTcpFull, {
            "proxy_type": u.scheme,
            "addr": u.hostname,
            "port": u.port,
            "username": u.username,
            "password": u.password,
            "rdns": True,
        }

    return connection.ConnectionTcpFull, None


def create_client(settings, new_session=False):
    conn, proxy = build_proxy(settings)

    session = StringSession() if new_session else StringSession(settings.session)

    return TelegramClient(
        session,
        settings.api_id,
        settings.api_hash,
        connection=conn,
        proxy=proxy
    )