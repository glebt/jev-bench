"""Regression tests for schema validation command error handling."""

from pathlib import Path

import pytest
import typer

from eval import validate_schema


def test_validate_schema_reports_invalid_utf8_as_a_command_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    schema_path = tmp_path / "invalid-✓.json"
    schema_path.write_bytes(b"{\"title\": \"\xff\"}")

    with pytest.raises(typer.Exit) as exc_info:
        validate_schema(schema_path)

    assert exc_info.value.exit_code == 1
    assert "Error:" in capsys.readouterr().out
