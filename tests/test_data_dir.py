"""Memory location: neutral default, legacy installs keep working, explicit override wins."""
import sqlite3

import pytest

from ai_dlc_mcp.config import default_data_dir


@pytest.fixture(autouse=True)
def _no_override(monkeypatch):
    monkeypatch.delenv("AI_DLC_DATA_DIR", raising=False)


def _make_db(directory):
    directory.mkdir(parents=True)
    sqlite3.connect(directory / "memory.db").close()


def test_fresh_install_uses_neutral_location(tmp_path):
    assert default_data_dir(tmp_path) == tmp_path / ".ai-dlc" / "memory"


def test_existing_legacy_database_is_kept(tmp_path):
    _make_db(tmp_path / ".codex" / "ai-dlc-memory")
    assert default_data_dir(tmp_path) == tmp_path / ".codex" / "ai-dlc-memory"


def test_new_location_wins_once_it_holds_a_database(tmp_path):
    _make_db(tmp_path / ".codex" / "ai-dlc-memory")
    _make_db(tmp_path / ".ai-dlc" / "memory")
    assert default_data_dir(tmp_path) == tmp_path / ".ai-dlc" / "memory"


def test_empty_legacy_directory_is_ignored(tmp_path):
    (tmp_path / ".codex" / "ai-dlc-memory").mkdir(parents=True)
    assert default_data_dir(tmp_path) == tmp_path / ".ai-dlc" / "memory"


def test_explicit_override_wins(tmp_path, monkeypatch):
    _make_db(tmp_path / ".codex" / "ai-dlc-memory")
    monkeypatch.setenv("AI_DLC_DATA_DIR", str(tmp_path / "custom"))
    assert default_data_dir(tmp_path) == (tmp_path / "custom").resolve()
