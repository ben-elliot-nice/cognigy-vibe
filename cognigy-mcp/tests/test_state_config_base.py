from pathlib import Path
from cognigy_mcp.state import ProjectState


def test_config_base_override(tmp_path):
    custom_base = tmp_path / "custom"
    state = ProjectState(project_id="proj-1", config_base=custom_base)
    assert state.config_dir == custom_base / "proj-1"
    assert state.config_dir.exists()


def test_config_base_default(tmp_path, monkeypatch):
    monkeypatch.setattr("cognigy_mcp.state.CONFIG_BASE", tmp_path / "default")
    state = ProjectState(project_id="proj-2")
    assert state.config_dir == tmp_path / "default" / "proj-2"
