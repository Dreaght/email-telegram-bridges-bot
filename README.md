# email-telegram-bridges-bot

Userbot that fetches Tor bridges from @GetBridgesBot and delivers them via secure email workflow.

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

---

## Email Integration

Bot can work as an email responder:

- Reads incoming emails via IMAP
- Verifies PGP-signed requests (identity check)
- Fetches bridges from Telegram
- Sends encrypted response via SMTP

The obfuscation/verification layer is modular. `OBFUSCATION_LAYER=pgp` is the built-in
implementation; additional layers can be added under `email_bridge/obfuscation/`.

### Additional setup

Add to `.env.secret`:

- EMAIL_ADDRESS
- EMAIL_PASSWORD
- TRUSTED_FINGERPRINTS (comma-separated list of allowed PGP fingerprints)

Optional for CI when `OBFUSCATION_LAYER=pgp`:
- GPG_PUBLIC_KEYS (ASCII-armored public keys to import at runtime)

Mail servers are configured in `.env.shared`:
- IMAP_HOST / IMAP_PORT
- SMTP_HOST / SMTP_PORT

Run:

`python email_bot.py`

---

## Client (Optional)

A simple CLI client is provided to automate requests without using webmail.

Setup:

Copy:
`cp .env.email.secret.example .env.email.secret`

Fill:
- EMAIL_ADDRESS
- EMAIL_PASSWORD
- BOT_EMAIL

Run:

`python client.py`

Client will:
- send signed request
- wait for reply (polling)
- decrypt bridges locally

---

## Tests

Run locally (same command used in CI):

`pytest -q`

---

## Files

- `.env.secret` → sensitive data (DO NOT COMMIT)
- `.env.shared` → shared config (safe to commit)
- `.env.secret.example` → template
- `.env.email.secret` → client email config (DO NOT COMMIT)
- `.env.email.secret.example` → client template

## Security

- SESSION grants full access to your Telegram account
- Never commit `.env.secret` or `.env.email.secret`
- For CI (GitHub Actions), store values in secrets
- Email requests are authenticated via PGP signatures
- Responses are encrypted with user's public key

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
- Email workflow is asynchronous → responses may be delayed
- Client uses polling (no webhooks)
