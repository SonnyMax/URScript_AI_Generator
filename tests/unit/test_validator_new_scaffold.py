"""Stage 0 scaffold tests: package import, result types, CLI, golden corpus."""
from __future__ import annotations

import io
import json
import re
import subprocess
import sys
from collections.abc import Iterator
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any

import pytest

from urscript_app.validator_new import Diagnostic, Severity, ValidationResult, validate
from urscript_app.validator_new.cli import (
    EXIT_INVALID,
    EXIT_IO_ERROR,
    EXIT_VALID,
    main,
    resolve_exit_code,
)
from urscript_app.validator_new.config_bridge import FALLBACK_LIMITS, get_motion_limits
from urscript_app.validator_new.robot_profiles import (
    DEFAULT_ROBOT,
    available_robots,
    get_profile,
)

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "urscript"
MANIFEST_PATH = FIXTURES_DIR / "manifest.json"

VALID_SNIPPET = (
    "def program():\n"
    "  movej([0.0, -1.5708, 0.0, -1.5708, 0.0, 0.0], a=0.5, v=0.5)\n"
    "end\n"
)

OUTCOME_PATTERN = re.compile(r"^(valid|error:E-[A-Z]+|warning:W-[A-Z]+)$")

# Stage in which each diagnostic code becomes detectable; drives the xfail
# marks that later stages flip to passing.
STAGE_BY_CODE = {
    "E-ARITY": 2,
    "E-WORKSPACE": 4,
    "W-GRIPPER": 4,
}


def _load_manifest() -> dict[str, str]:
    raw = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    return {str(k): str(v) for k, v in raw.items()}


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


def test_validate_returns_valid_result() -> None:
    result = validate(VALID_SNIPPET)
    assert isinstance(result, ValidationResult)
    assert result.valid is True
    assert result.errors == []
    assert result.warnings == []


def test_severity_values() -> None:
    assert Severity.ERROR.value == "error"
    assert Severity.WARNING.value == "warning"
    assert Severity.INFO.value == "info"


def test_diagnostic_is_frozen() -> None:
    diag = Diagnostic(level=Severity.ERROR.value, message="boom", line=3)
    with pytest.raises(FrozenInstanceError):
        diag.message = "changed"  # type: ignore[misc]


def test_diagnostic_to_dict_keys() -> None:
    diag = Diagnostic(
        level=Severity.ERROR.value, message="boom", line=3, column=7, code="E-SYNTAX"
    )
    payload = diag.to_dict()
    assert payload == {
        "level": "error",
        "code": "E-SYNTAX",
        "message": "boom",
        "line": 3,
        "column": 7,
    }


def test_validation_result_to_dict_round_trips() -> None:
    result = ValidationResult(
        valid=False,
        errors=[Diagnostic(level="error", message="bad", line=1, code="E-SYNTAX")],
        warnings=[Diagnostic(level="warning", message="meh", line=2, code="W-GRIPPER")],
    )
    payload = json.loads(json.dumps(result.to_dict()))
    assert set(payload) == {"valid", "errors", "warnings"}
    assert payload["valid"] is False
    assert payload["errors"][0]["code"] == "E-SYNTAX"
    assert payload["warnings"][0]["line"] == 2


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_cli_valid_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    script = tmp_path / "ok.urscript"
    script.write_text(VALID_SNIPPET, encoding="utf-8")
    exit_code = main([str(script)])
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == EXIT_VALID
    assert set(payload) == {"valid", "errors", "warnings"}
    assert payload["valid"] is True


def test_cli_reads_stdin(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO(VALID_SNIPPET))
    exit_code = main(["-"])
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == EXIT_VALID
    assert payload["valid"] is True


def test_cli_missing_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main([str(tmp_path / "does_not_exist.urscript")])
    captured = capsys.readouterr()
    assert exit_code == EXIT_IO_ERROR
    assert captured.out == ""
    assert "cannot read" in captured.err


def test_cli_quiet_suppresses_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    script = tmp_path / "ok.urscript"
    script.write_text(VALID_SNIPPET, encoding="utf-8")
    exit_code = main([str(script), "--quiet"])
    assert exit_code == EXIT_VALID
    assert capsys.readouterr().out == ""


def test_exit_code_resolution() -> None:
    error = Diagnostic(level="error", message="bad")
    warning = Diagnostic(level="warning", message="meh")
    clean = ValidationResult(valid=True)
    warned = ValidationResult(valid=True, warnings=[warning])
    failed = ValidationResult(valid=False, errors=[error])

    assert resolve_exit_code(clean, warnings_as_errors=False) == EXIT_VALID
    assert resolve_exit_code(warned, warnings_as_errors=False) == EXIT_VALID
    assert resolve_exit_code(warned, warnings_as_errors=True) == EXIT_INVALID
    assert resolve_exit_code(failed, warnings_as_errors=False) == EXIT_INVALID


def test_cli_module_entrypoint_smoke(tmp_path: Path) -> None:
    script = tmp_path / "ok.urscript"
    script.write_text(VALID_SNIPPET, encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "-m", "urscript_app.validator_new", str(script)],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert proc.returncode == EXIT_VALID, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["valid"] is True


# ---------------------------------------------------------------------------
# Config bridge and robot profiles
# ---------------------------------------------------------------------------


def test_motion_limits_match_app_settings() -> None:
    from urscript_app.config import get_settings

    limits = get_motion_limits()
    settings = get_settings()
    assert limits.max_joint_velocity == settings.max_joint_velocity
    assert limits.max_joint_accel == settings.max_joint_accel
    assert limits.max_tcp_velocity == settings.max_tcp_velocity
    assert limits.max_tcp_accel == settings.max_tcp_accel


def test_motion_limits_fall_back_when_config_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom() -> None:
        raise RuntimeError("settings unavailable")

    monkeypatch.setattr("urscript_app.config.get_settings", boom)
    assert get_motion_limits() == FALLBACK_LIMITS


def test_default_robot_profile() -> None:
    profile = get_profile()
    assert DEFAULT_ROBOT == "UR5e"
    assert profile.name == "UR5e"
    assert profile.reach_m == pytest.approx(0.850)


def test_all_documented_robots_present() -> None:
    assert available_robots() == ("UR10e", "UR16e", "UR20", "UR30", "UR3e", "UR5e")
    assert get_profile("UR20").reach_m == pytest.approx(1.750)


def test_unknown_robot_raises() -> None:
    with pytest.raises(ValueError, match="Unknown robot profile"):
        get_profile("UR9000")


def test_robot_profile_is_frozen() -> None:
    profile = get_profile("UR3e")
    with pytest.raises(FrozenInstanceError):
        profile.reach_m = 2.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Golden corpus
# ---------------------------------------------------------------------------


def test_manifest_and_fixture_files_agree() -> None:
    manifest = _load_manifest()
    files = {path.name for path in FIXTURES_DIR.glob("*.urscript")}
    assert files == set(manifest), "manifest entries and fixture files must match 1:1"
    for name, expected in manifest.items():
        assert OUTCOME_PATTERN.match(expected), f"bad outcome for {name}: {expected!r}"


def _corpus_params() -> Iterator[Any]:
    for name, expected in sorted(_load_manifest().items()):
        marks: list[pytest.MarkDecorator] = []
        if expected != "valid":
            code = expected.split(":", 1)[1]
            stage = STAGE_BY_CODE[code]
            marks.append(pytest.mark.xfail(reason=f"stage {stage}", strict=True))
        yield pytest.param(name, expected, marks=marks, id=name)


@pytest.mark.parametrize(("name", "expected"), _corpus_params())
def test_corpus_matches_manifest(name: str, expected: str) -> None:
    source = (FIXTURES_DIR / name).read_text(encoding="utf-8")
    result = validate(source)
    if expected == "valid":
        assert result.valid, [d.message for d in result.errors]
        assert result.errors == []
        return
    kind, _, code = expected.partition(":")
    if kind == "error":
        assert not result.valid
        assert any(d.code == code for d in result.errors)
    else:
        assert result.valid
        assert any(d.code == code for d in result.warnings)
