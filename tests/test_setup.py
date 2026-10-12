"""Bootstrap consent and persistence boundaries, without touching the real home."""
import json
import sqlite3
import subprocess
from unittest.mock import Mock

import pytest

from ai_dlc_mcp import setup
from ai_dlc_mcp import installer


@pytest.fixture
def bootstrap(monkeypatch, tmp_path):
    monkeypatch.setattr(setup.shutil, "which", lambda _: "uv")
    monkeypatch.setattr(setup.sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr(setup, "package_source", lambda: f"ai-dlc-engineering-os=={setup.__version__}")
    output = Mock(side_effect=[str(tmp_path / "tools"), setup.__version__])
    monkeypatch.setattr(setup.subprocess, "check_output", output)
    run = Mock()
    monkeypatch.setattr(setup.subprocess, "run", run)
    monkeypatch.delenv("AI_DLC_DB_PATH", raising=False)
    monkeypatch.delenv("AI_DLC_DATA_DIR", raising=False)
    return tmp_path / "home", run


def test_dry_run_makes_no_changes(bootstrap):
    home, run = bootstrap
    assert setup.main(["setup", "--home", str(home), "--editors", "codex,claude", "--dry-run"]) == 0
    assert not home.exists()
    run.assert_not_called()


def test_noninteractive_requires_explicit_consent(bootstrap):
    home, run = bootstrap
    assert setup.main(["setup", "--home", str(home), "--editors", "codex"]) == 1
    assert not home.exists()
    run.assert_not_called()


def test_declining_interactive_plan_makes_no_changes(bootstrap, monkeypatch):
    home, run = bootstrap
    monkeypatch.setattr(setup.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _: "n")
    assert setup.main(["setup", "--home", str(home), "--editors", "codex"]) == 0
    assert not home.exists()
    run.assert_not_called()


def test_install_failure_preserves_configuration(bootstrap):
    home, run = bootstrap
    home.mkdir()
    cfg = home / ".claude.json"
    cfg.write_text('{"custom": true}')
    run.side_effect = subprocess.CalledProcessError(1, "uv")
    assert setup.main(["setup", "--home", str(home), "--editors", "claude", "--yes"]) == 1
    assert cfg.read_text() == '{"custom": true}'
    assert not (home / ".claude").exists()


def test_persistent_interpreter_selected_hosts_and_backup(bootstrap):
    home, run = bootstrap
    home.mkdir()
    cfg = home / ".claude.json"
    cfg.write_text('{"custom": true}')
    assert setup.main(["setup", "--home", str(home), "--editors", "claude", "--yes"]) == 0
    data = json.loads(cfg.read_text())
    assert data["custom"] is True
    python = data["mcpServers"]["ai_dlc_os"]["command"]
    assert str(home.parent / "tools" / "ai-dlc-engineering-os") in python
    assert python != setup.sys.executable
    assert not (home / ".codex").exists()
    assert not (home / ".claude" / "settings.json").exists()
    assert len(list(home.glob(".claude.json.backup.*"))) == 1
    doctor = run.call_args_list[-1].args[0]
    assert doctor[0] == python
    assert doctor[doctor.index("--only") + 1] == "claude"


def test_database_backup_preserves_existing_rows(tmp_path, monkeypatch):
    db = tmp_path / "memory.db"
    with sqlite3.connect(db) as conn:
        conn.execute("create table evidence (value text)")
        conn.execute("insert into evidence values ('preserve')")
    monkeypatch.setenv("AI_DLC_DB_PATH", str(db))
    setup.backup_memory(tmp_path)
    backups = list((tmp_path / "backups").glob("*.db"))
    assert len(backups) == 1
    with sqlite3.connect(backups[0]) as conn:
        assert conn.execute("select value from evidence").fetchone() == ("preserve",)


def test_source_preserves_resolved_git_commit(monkeypatch):
    dist = Mock()
    dist.read_text.return_value = json.dumps({"url": "https://github.com/example/project", "vcs_info": {
        "vcs": "git", "commit_id": "abc123", "requested_revision": "main"}})
    monkeypatch.setattr(setup, "distribution", lambda _: dist)
    assert setup.package_source() == "git+https://github.com/example/project@abc123"


def test_doctor_only_checks_selected_editor(tmp_path, monkeypatch, capsys):
    # The selected editor is missing; checks for unselected editors must not run.
    monkeypatch.setattr(installer.asyncio, "run", lambda coro: (coro.close(), 40)[1])
    from ai_dlc_mcp import config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "doctor.db")
    assert installer.doctor(tmp_path, setup.sys.executable, ["codex"]) == 1
    out = capsys.readouterr().out
    assert "Codex" in out
    assert "Claude" not in out
    assert "VS Code" not in out
