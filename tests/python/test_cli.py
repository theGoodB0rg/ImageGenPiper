import os
import tempfile
import pytest
from typer.testing import CliRunner
from cli.main import app

runner = CliRunner()


def test_cli_version():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "ImageGenPiper" in result.stdout
    assert "0.1.0" in result.stdout


def test_cli_run_missing_args():
    result = runner.invoke(app, ["run"])
    assert result.exit_code == 1
    assert "You must provide either --prompt or --prompts-file" in result.stdout


def test_cli_run_nonexistent_file():
    result = runner.invoke(app, ["run", "--prompts-file", "nonexistent_file_12345.txt"])
    assert result.exit_code == 1
    assert "Prompts file not found" in result.stdout
