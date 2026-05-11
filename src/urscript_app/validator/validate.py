"""Public API: validate URScript source."""
from urscript_app.validator.parser import parse
from urscript_app.validator.semantics import check_semantics
from urscript_app.validator.result import Diagnostic, ValidationResult


def validate(source: str) -> ValidationResult:
    diags: list[Diagnostic] = []
    diags.extend(parse(source))
    diags.extend(check_semantics(source))

    errors = [d for d in diags if d.level == "error"]
    warnings = [d for d in diags if d.level == "warning"]
    return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)
