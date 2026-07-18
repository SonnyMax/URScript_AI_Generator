"""New URScript validator — parallel rewrite of `urscript_app.validator`.

Public API mirrors the old validator so the app can swap over later:
`validate(source: str) -> ValidationResult`.
"""
from urscript_app.validator_new.result import Diagnostic, Severity, ValidationResult
from urscript_app.validator_new.validate import validate

__all__ = ["Diagnostic", "Severity", "ValidationResult", "validate"]
