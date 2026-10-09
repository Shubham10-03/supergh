"""Tests for the `sgh app` CLI command group."""

from unittest.mock import patch

import pytest
from click.testing import CliRunner

from supergh.auth.app_registry import AppRegistry
from supergh.commands import app as app_mod


@pytest.fixture
def tmp_registry(tmp_path):
    reg = AppRegistry(apps_dir=tmp_path / "apps")
    pem = tmp_path / "k.pem"
    pem.write_text("-----BEGIN KEY-----\nx\n-----END KEY-----\n")
    reg.register(name="captwo", app_id="1228618", pem_source=pem, org="BritishAirways-Ent")
    return reg


def test_app_list_shows_registered(tmp_registry):
    runner = CliRunner()
    with patch.object(app_mod, "get_registry", return_value=tmp_registry):
        result = runner.invoke(app_mod.app_cmd, ["list"])
    assert result.exit_code == 0
    assert "captwo" in result.output
    assert "1228618" in result.output
    assert "BritishAirways-Ent" in result.output


def test_app_list_empty(tmp_path):
    empty = AppRegistry(apps_dir=tmp_path / "apps")
    runner = CliRunner()
    with patch.object(app_mod, "get_registry", return_value=empty):
        result = runner.invoke(app_mod.app_cmd, ["list"])
    assert result.exit_code == 0
    assert "No apps registered" in result.output


def test_app_remove_confirmed(tmp_registry):
    runner = CliRunner()
    with patch.object(app_mod, "get_registry", return_value=tmp_registry):
        result = runner.invoke(app_mod.app_cmd, ["remove", "captwo"], input="y\n")
    assert result.exit_code == 0
    assert "Removed app 'captwo'" in result.output
    assert not tmp_registry.exists("captwo")


def test_app_remove_unknown(tmp_registry):
    runner = CliRunner()
    with patch.object(app_mod, "get_registry", return_value=tmp_registry):
        result = runner.invoke(app_mod.app_cmd, ["remove", "ghost"], input="y\n")
    assert result.exit_code != 0
    assert "not registered" in result.output
