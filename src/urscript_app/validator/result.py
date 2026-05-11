from dataclasses import dataclass, field


@dataclass
class Diagnostic:
    level: str  # "error" | "warning"
    message: str
    line: int | None = None


@dataclass
class ValidationResult:
    valid: bool
    errors: list[Diagnostic] = field(default_factory=list)
    warnings: list[Diagnostic] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "errors": [{"level": d.level, "message": d.message, "line": d.line} for d in self.errors],
            "warnings": [{"level": d.level, "message": d.message, "line": d.line} for d in self.warnings],
        }
