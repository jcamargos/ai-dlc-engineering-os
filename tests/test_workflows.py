"""Public workflow discovery, isolation and CLI error contracts."""
import json

import pytest

from ai_dlc_mcp import cli, workflows


def test_catalog_and_each_packaged_phase_are_available(capsys):
    with pytest.raises(SystemExit) as result:
        cli.main(["workflow", "list"])
    assert result.value.code == 0
    catalog = json.loads(capsys.readouterr().out)
    assert {item["name"] for item in catalog} == {"discover", "plan", "implement", "debug", "review", "finish"}
    for item in catalog:
        with pytest.raises(SystemExit) as result:
            cli.main(["workflow", "show", item["name"]])
        assert result.value.code == 0
        assert capsys.readouterr().out.strip() == workflows.load(item["name"]).strip()


@pytest.mark.parametrize("name", ["../agents/backend", "", "DISCOVER", "unknown", "/etc/passwd"])
def test_workflow_names_cannot_select_arbitrary_files(name):
    with pytest.raises(ValueError, match="Unknown workflow"):
        workflows.load(name)


def test_invalid_cli_phase_fails_without_output(capsys):
    with pytest.raises(SystemExit) as result:
        cli.main(["workflow", "show", "unknown"])
    assert result.value.code == 2
    assert capsys.readouterr().out == ""
