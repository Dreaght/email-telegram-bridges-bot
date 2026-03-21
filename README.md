# email-telegram-bridges-bot

Userbot that fetches Tor bridges from @GetBridgesBot and sends them via email.

## Setup

1. Create a virtual environment and install dependencies  
   https://docs.telethon.dev/en/stable/basic/installation.html

2. Obtain Telegram API credentials  
   https://my.telegram.org/apps

3. Prepare environment files

   Copy:
   `cp .env.secret.example .env.secret`

   Then edit `.env.secret` and fill:
   - API_ID
   - API_HASH

4. Generate session

   Run:
   `python generate_session.py`

   You will be prompted for:
   - phone number
   - login code (from Telegram)
   - possibly 2FA password

5. Save session

   Paste generated string into:
   `SESSION=` in `.env.secret`

6. Run the bot

   `python main.py`


## Files

- `.env.secret` → sensitive data (DO NOT COMMIT)
- `.env.shared` → shared config (safe to commit)
- `.env.secret.example` → template

## Security

- SESSION grants full access to your Telegram account
- Never commit `.env.secret`
- For CI (GitHub Actions), store values in secrets

## Proxy (optional)

Use if Telegram is blocked or for obfuscation.

Examples (do not paste blindly):

- Local SOCKS5 (common case):
  `socks5://127.0.0.1:1080`

- Authenticated proxy:
  `socks5://user:pass@host:port`

- MTProto proxy:
  `mtproto://SECRET@HOST:PORT`

If both PROXY and MTPROXY are set, MTPROXY is used.

## Notes

- GitHub Actions is ephemeral → StringSession is required
- Do NOT use file-based sessions in CI