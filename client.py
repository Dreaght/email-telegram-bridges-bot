from email_bridge.client.config import load_client_config
from email_bridge.client.flow import run_client
from email_bridge.obfuscation.factory import create_obfuscation_layer


def main():
    config = load_client_config()
    obfuscation = create_obfuscation_layer(config.obfuscation_layer)
    obfuscation.prepare_runtime()
    run_client(config, obfuscation)


if __name__ == "__main__":
    main()
