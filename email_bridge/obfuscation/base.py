from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class VerificationResult:
    valid: bool
    signer_id: str | None


class ObfuscationLayer(Protocol):
    def prepare_runtime(self) -> None:
        ...

    def looks_like_request(self, data: bytes) -> bool:
        ...

    def looks_like_response(self, data: bytes) -> bool:
        ...

    def verify_request(self, data: bytes) -> VerificationResult:
        ...

    def sign_request(self, payload: str) -> str:
        ...

    def encrypt_for_signer(self, signer_id: str, text: str) -> str:
        ...

    def decrypt_response(self, data: bytes) -> str:
        ...
