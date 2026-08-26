from __future__ import annotations

from typing import Any


class DomainError(Exception):
    def __init__(
        self, code: str, message: str, *, evidence: Any = None, next_action: str | None = None
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.evidence = evidence
        self.next_action = next_action

    def to_dict(self):
        from marketing_mcp.security.redaction import redact_secrets

        raw = {
            "error": {
                "code": self.code,
                "message": self.message,
                "evidence": self.evidence,
                "next_action": self.next_action,
            }
        }
        return redact_secrets(raw)
