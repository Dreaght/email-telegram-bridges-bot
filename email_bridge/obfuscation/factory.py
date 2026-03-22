from email_bridge.obfuscation.base import ObfuscationLayer
from email_bridge.obfuscation.pgp import PgpObfuscationLayer


def create_obfuscation_layer(name: str) -> ObfuscationLayer:
    normalized = (name or "pgp").strip().lower()
    if normalized == "pgp":
        return PgpObfuscationLayer()

    raise ValueError(f"Unsupported obfuscation layer: {name}")

