"""CLI smoke tests for OmniSpatial."""

from typer.testing import CliRunner

from omnispatial.cli import app


def test_cli_help() -> None:
    """Ensure the CLI help screen renders without error."""
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Usage" in result.stdout
