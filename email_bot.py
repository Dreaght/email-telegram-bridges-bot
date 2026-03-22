import logging

from email_bridge.bot.flow import run_bot
from email_bridge.obfuscation.factory import create_obfuscation_layer
from settings import load_settings

logging.basicConfig(level=logging.INFO)


def main():
    settings = load_settings()
    obfuscation = create_obfuscation_layer(settings.obfuscation_layer)
    obfuscation.prepare_runtime()
    run_bot(settings, obfuscation)


if __name__ == "__main__":
    main()
