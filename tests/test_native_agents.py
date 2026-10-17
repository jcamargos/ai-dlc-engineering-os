"""Native format validity, ownership, lifecycle and bootstrap boundaries."""
import json
import sys

import pytest

from ai_dlc_mcp import agents, installer, native_agents, setup

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib


@pytest.mark.parametrize("host", native_agents.HOSTS)
def test_rendered_agents_share_contract_and_memory_protocol(host):
    rendered = native_agents.files(host)
    assert len(rendered) == 26
    for spec in agents.all_specs():
        text = rendered[f"ai-dlc-{spec.name}{native_agents.SUFFIX[host]}"]
        if host == "codex":
            meta = tomllib.loads(text)
            body = meta['developer_instructions']
        else:
            _, frontmatter, body = text.split('---', 2)
            # All generated YAML scalars are plain names, JSON strings or booleans.
            meta = dict(line.split(': ', 1) for line in frontmatter.strip().splitlines())
            assert json.loads(meta['description']).endswith(spec.description)
        assert meta['name'] == f'ai-dlc-{spec.name}'
        assert spec.body.strip() in body
        assert "get_agent_context" in body
        assert "only when authorized" in body
        assert "model" not in meta
        assert "sandbox_mode" not in meta


@pytest.mark.parametrize("host", native_agents.HOSTS)
def test_native_lifecycle_preserves_users_and_backs_up_changes(tmp_path, host):
    target = native_agents.directory(tmp_path, host)
    target.mkdir(parents=True)
    owned = target / f'personal{native_agents.SUFFIX[host]}'
    owned.write_text('user content')
    inst = installer.Installer(tmp_path, sys.executable, installer.Plan(), use_cli=False)
    inst._sync_native_agents(host)
    before = {p.name: p.read_bytes() for p in target.iterdir()}
    inst._sync_native_agents(host)
    assert before == {p.name: p.read_bytes() for p in target.iterdir()}
    sample = target / next(iter(native_agents.files(host)))
    sample.write_text(sample.read_text(encoding='utf-8') + '\nuser customization\n', encoding='utf-8')
    inst._sync_native_agents(host)
    assert any('user customization' in p.read_text(encoding='utf-8') for p in target.glob('*.backup.*'))
    inst._sync_native_agents(host, remove_all=True)
    assert owned.read_text() == 'user content'
    assert not any((target/n).exists() for n in native_agents.files(host))
    assert list(target.glob('*.backup.*'))


@pytest.mark.parametrize("host", native_agents.HOSTS)
def test_conflicting_unmanaged_agent_aborts_before_host_config(tmp_path, host):
    target = native_agents.directory(tmp_path, host)
    target.mkdir(parents=True)
    path = target / next(iter(native_agents.files(host)))
    path.write_text('user owned')
    before = {p: p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    with pytest.raises(ValueError, match='User-owned'):
        setup.register(tmp_path, tmp_path/'python', [host], dry_run=False)
    assert before == {p: p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    installer.Installer(tmp_path, sys.executable, installer.Plan())._sync_native_agents(host, remove_all=True)
    assert path.read_text() == 'user owned'


def test_all_hosts_preflight_before_any_changes(tmp_path):
    target = native_agents.directory(tmp_path, 'cursor')
    target.mkdir(parents=True)
    (target/'ai-dlc-backend.md').write_text('user owned')
    with pytest.raises(ValueError, match='User-owned'):
        setup.register(tmp_path, tmp_path/'python', ['codex', 'cursor'], False)
    assert not (tmp_path/'.codex').exists()


def _link_directory(link, target):
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f'Directory symlinks unavailable: {exc}')


def test_selected_home_alias_is_accepted(tmp_path):
    home = tmp_path/'real-home'
    home.mkdir()
    alias = tmp_path/'alias-home'
    _link_directory(alias, home)
    inst = installer.Installer(alias, sys.executable, installer.Plan(), use_cli=False)
    inst.install_codex()
    inst.install_codex()
    assert len(list((home/'.codex/agents').glob('ai-dlc-*.toml'))) == 26


@pytest.mark.parametrize('redirect', ['.codex', '.codex/agents'])
def test_agent_directory_redirection_remains_blocked(tmp_path, redirect):
    home = tmp_path/'home'
    outside = tmp_path/'outside'
    home.mkdir()
    outside.mkdir()
    link = home/redirect
    link.parent.mkdir(parents=True, exist_ok=True)
    _link_directory(link, outside)
    inst = installer.Installer(home, sys.executable, installer.Plan(), use_cli=False)
    with pytest.raises(ValueError, match='must not be redirected'):
        inst.install_codex()
    assert not list(outside.iterdir())
    assert not (home/'.codex/config.toml').exists()


def test_cursor_preserves_mcp_servers_and_dry_run(tmp_path):
    path = tmp_path/'.cursor/mcp.json'
    path.parent.mkdir()
    path.write_text(json.dumps({'mcpServers': {'other': {'command': 'example'}}, 'custom': True}))
    old = path.read_bytes()
    setup.register(tmp_path, tmp_path/'python', ['cursor'], True)
    assert path.read_bytes() == old
    assert not (path.parent/'agents').exists()
    inst = installer.Installer(tmp_path, sys.executable, installer.Plan())
    inst.install_cursor()
    data = json.loads(path.read_text())
    assert data['custom'] and data['mcpServers']['other']['command'] == 'example'
    assert data['mcpServers']['ai_dlc_os']['command'] == sys.executable
    inst.uninstall_cursor()
    assert json.loads(path.read_text()) == json.loads(old)


def test_cursor_invalid_json_is_not_overwritten(tmp_path):
    path = tmp_path/'.cursor/mcp.json'
    path.parent.mkdir()
    path.write_text('{ invalid')
    with pytest.raises(json.JSONDecodeError):
        setup.register(tmp_path, tmp_path/'python', ['cursor'], False)
    assert path.read_text() == '{ invalid'
    assert not (path.parent/'agents').exists()


def test_doctor_detects_missing_or_stale_agent(tmp_path, monkeypatch, capsys):
    from ai_dlc_mcp import config
    monkeypatch.setattr(config, 'DB_PATH', tmp_path/'memory.db')
    monkeypatch.setattr(installer.asyncio, 'run', lambda coro: (coro.close(), 40)[1])
    inst = installer.Installer(tmp_path, sys.executable, installer.Plan())
    inst.install_cursor()
    assert installer.doctor(tmp_path, sys.executable, ['cursor']) == 0
    (tmp_path/'.cursor/agents/ai-dlc-backend.md').write_text('stale')
    assert installer.doctor(tmp_path, sys.executable, ['cursor']) == 1
    assert '25/26' in capsys.readouterr().out
