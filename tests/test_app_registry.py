"""Tests for the GitHub App registry (~/.supergh/apps/)."""

import json
import os
import stat

import pytest

from supergh.auth.app_registry import AppRegistry, AppEntry


@pytest.fixture
def pem_file(tmp_path):
    p = tmp_path / "source_key.pem"
    p.write_text("-----BEGIN RSA PRIVATE KEY-----\nFAKEKEYDATA\n-----END RSA PRIVATE KEY-----\n")
    return p


@pytest.fixture
def registry(tmp_path):
    return AppRegistry(apps_dir=tmp_path / "apps")


def test_apps_dir_created_with_secure_perms(tmp_path):
    reg = AppRegistry(apps_dir=tmp_path / "apps")
    assert reg.apps_dir.is_dir()
    mode = stat.S_IMODE(os.stat(reg.apps_dir).st_mode)
    assert mode == 0o700


def test_register_copies_pem_in_with_600(registry, pem_file):
    entry = registry.register(name="captwo", app_id="123", pem_source=pem_file, org="MyOrg")
    dest = registry.pem_path(entry)

    assert dest.is_file()
    assert dest.name == "captwo.pem"
    # Copied, not referencing the original location.
    assert dest.parent == registry.apps_dir
    assert dest.read_text() == pem_file.read_text()
    mode = stat.S_IMODE(os.stat(dest).st_mode)
    assert mode == 0o600


def test_registry_json_has_mapping_and_no_secrets(registry, pem_file):
    registry.register(name="captwo", app_id="123", pem_source=pem_file, org="MyOrg")
    data = json.loads(registry.registry_file.read_text())

    assert "captwo" in data["apps"]
    entry = data["apps"]["captwo"]
    assert entry["app_id"] == "123"
    assert entry["pem_file"] == "captwo.pem"
    assert entry["org"] == "MyOrg"
    # The private key text must never be written into the JSON manifest.
    assert "BEGIN" not in registry.registry_file.read_text()


def test_get_and_list_and_exists(registry, pem_file):
    registry.register(name="a", app_id="1", pem_source=pem_file)
    registry.register(name="b", app_id="2", pem_source=pem_file)

    assert registry.exists("a")
    assert registry.exists("b")
    assert not registry.exists("c")
    assert set(registry.list_apps().keys()) == {"a", "b"}

    a = registry.get("a")
    assert isinstance(a, AppEntry)
    assert a.app_id == "1"
    assert a.name == "a"


def test_register_duplicate_without_overwrite_raises(registry, pem_file):
    registry.register(name="dup", app_id="1", pem_source=pem_file)
    with pytest.raises(ValueError):
        registry.register(name="dup", app_id="9", pem_source=pem_file)
    # With overwrite it succeeds and updates the app_id.
    registry.register(name="dup", app_id="9", pem_source=pem_file, overwrite=True)
    assert registry.get("dup").app_id == "9"


def test_register_missing_pem_raises(registry, tmp_path):
    with pytest.raises(FileNotFoundError):
        registry.register(name="x", app_id="1", pem_source=tmp_path / "nope.pem")


def test_pem_present_detects_missing_key(registry, pem_file):
    entry = registry.register(name="gone", app_id="1", pem_source=pem_file)
    assert registry.pem_present(entry)
    registry.pem_path(entry).unlink()
    assert not registry.pem_present(entry)


def test_set_org_updates_entry(registry, pem_file):
    registry.register(name="a", app_id="1", pem_source=pem_file)
    registry.set_org("a", "ResolvedOrg")
    assert registry.get("a").org == "ResolvedOrg"


def test_remove_deletes_pem_by_default(registry, pem_file):
    entry = registry.register(name="a", app_id="1", pem_source=pem_file)
    dest = registry.pem_path(entry)
    assert dest.is_file()

    assert registry.remove("a") is True
    assert not registry.exists("a")
    assert not dest.is_file()


def test_remove_keep_pem(registry, pem_file):
    entry = registry.register(name="a", app_id="1", pem_source=pem_file)
    dest = registry.pem_path(entry)
    registry.remove("a", delete_pem=False)
    assert not registry.exists("a")
    assert dest.is_file()  # kept


def test_remove_unknown_returns_false(registry):
    assert registry.remove("nonexistent") is False


def test_register_in_place_when_source_already_in_apps_dir(registry):
    # Dropping a key directly into apps dir then registering it should not fail.
    in_dir = registry.apps_dir / "captwo.pem"
    registry.apps_dir.mkdir(parents=True, exist_ok=True)
    in_dir.write_text("-----BEGIN KEY-----\nx\n-----END KEY-----\n")
    entry = registry.register(name="captwo", app_id="1", pem_source=in_dir)
    assert registry.pem_present(entry)
    assert registry.pem_path(entry).read_text().startswith("-----BEGIN")
