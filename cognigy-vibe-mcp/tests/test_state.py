import json
import time
import pytest
from pathlib import Path
from cognigy_mcp.state import ProjectState


@pytest.fixture
def config_base(tmp_path):
    return tmp_path / "cognigy-mcp"


@pytest.fixture
def state(config_base, monkeypatch):
    monkeypatch.setattr("cognigy_mcp.state.CONFIG_BASE", config_base)
    return ProjectState(project_id="proj-123", resync_hours=4.0)


def test_config_dir_created(state, config_base):
    assert (config_base / "cache" / "proj-123").is_dir()


def test_seed_values_available(config_base, monkeypatch):
    monkeypatch.setattr("cognigy_mcp.state.CONFIG_BASE", config_base)
    proj_dir = config_base / "cache" / "proj-123"
    proj_dir.mkdir(parents=True)
    seed = {"flows": {"Main Flow": {"id": "seed-flow-id"}}}
    (proj_dir / ".state-seed.json").write_text(json.dumps(seed))
    s = ProjectState("proj-123")
    assert s.get("flows", "Main Flow", "id") == "seed-flow-id"


def test_runtime_overrides_seed(config_base, monkeypatch):
    monkeypatch.setattr("cognigy_mcp.state.CONFIG_BASE", config_base)
    proj_dir = config_base / "cache" / "proj-123"
    proj_dir.mkdir(parents=True)
    (proj_dir / ".state-seed.json").write_text(json.dumps({"x": "seed"}))
    (proj_dir / ".state.json").write_text(json.dumps({"x": "runtime"}))
    s = ProjectState("proj-123")
    assert s.get("x") == "runtime"


def test_needs_resync_when_no_timestamp(state):
    assert state.needs_resync()


def test_no_resync_after_touch(state):
    state.touch_interaction()
    assert not state.needs_resync()


def test_needs_resync_after_threshold(config_base, monkeypatch):
    monkeypatch.setattr("cognigy_mcp.state.CONFIG_BASE", config_base)
    s = ProjectState("proj-123", resync_hours=0.0)
    s.touch_interaction()
    assert s.needs_resync()


def test_set_and_save_and_reload(config_base, monkeypatch):
    monkeypatch.setattr("cognigy_mcp.state.CONFIG_BASE", config_base)
    s = ProjectState("proj-123")
    s.set("flows", "My Flow", value={"id": "flow-xyz"})
    # set() auto-saves — no explicit save() needed
    s2 = ProjectState("proj-123")
    assert s2.get("flows", "My Flow", "id") == "flow-xyz"


def test_get_missing_key_returns_none(state):
    assert state.get("nonexistent", "key") is None


def test_config_dir_property(state, config_base):
    assert state.config_dir == config_base / "cache" / "proj-123"


def test_load_handles_corrupt_state_file(config_base, monkeypatch):
    monkeypatch.setattr("cognigy_mcp.state.CONFIG_BASE", config_base)
    proj_dir = config_base / "cache" / "proj-123"
    proj_dir.mkdir(parents=True)
    (proj_dir / ".state.json").write_text("")  # corrupt — empty JSON
    s = ProjectState("proj-123")
    assert s.get("anything") is None  # should not raise


def test_needs_resync_handles_corrupt_timestamp(config_base, monkeypatch):
    monkeypatch.setattr("cognigy_mcp.state.CONFIG_BASE", config_base)
    s = ProjectState("proj-123")
    s._interaction_path.write_text("not-a-float")  # corrupt
    assert s.needs_resync()  # should return True, not raise


def test_as_dict_returns_copy(state):
    state.set("flows", "Main", value={"id": "flow-1"})
    d = state.as_dict()
    assert d["flows"]["Main"]["id"] == "flow-1"
    # Mutating the returned dict should not affect state
    d["flows"]["Main"]["id"] = "mutated"
    assert state.get("flows", "Main", "id") == "flow-1"


def test_none_project_id_uses_unscoped_dir(config_base, monkeypatch):
    """ProjectState with project_id=None must not raise and must use .unscoped dir."""
    monkeypatch.setattr("cognigy_mcp.state.CONFIG_BASE", config_base)
    s = ProjectState(project_id=None)
    assert s.config_dir == config_base / "cache" / ".unscoped"
    assert s.project_id is None


def test_bind_project_rescopes_state(config_base, monkeypatch):
    """bind_project() must update project_id, config_dir, and reload state from new dir."""
    monkeypatch.setattr("cognigy_mcp.state.CONFIG_BASE", config_base)
    s = ProjectState(project_id=None)
    s.set("flows", "Old", value={"id": "old-id"})  # written to .unscoped

    s.bind_project("proj-456")

    assert s.project_id == "proj-456"
    assert s.config_dir == config_base / "cache" / "proj-456"
    # .unscoped data must NOT bleed into the project-scoped state
    assert s.get("flows", "Old") is None


def test_bind_project_loads_existing_state(config_base, monkeypatch):
    """bind_project() must load persisted state if the project dir already has one."""
    monkeypatch.setattr("cognigy_mcp.state.CONFIG_BASE", config_base)
    # Pre-create a project dir with existing state
    proj_dir = config_base / "cache" / "proj-789"
    proj_dir.mkdir(parents=True)
    (proj_dir / ".state.json").write_text('{"flows": {"Main": {"id": "existing-id"}}}')

    s = ProjectState(project_id=None)
    s.bind_project("proj-789")

    assert s.get("flows", "Main", "id") == "existing-id"


def test_bind_project_noop_when_already_bound(config_base, monkeypatch):
    """bind_project() with the same project_id must not reload state."""
    monkeypatch.setattr("cognigy_mcp.state.CONFIG_BASE", config_base)
    s = ProjectState(project_id="proj-123")
    s.set("flows", "Canary", value={"id": "canary"})

    s.bind_project("proj-123")  # same id — must be no-op

    assert s.get("flows", "Canary", "id") == "canary"


def test_migrate_flat_layout_moves_stray_project_dir(tmp_path):
    from cognigy_mcp.state import _migrate_flat_layout
    config_base = tmp_path / "cognigy-vibe"
    proj_dir = config_base / "proj-123"
    proj_dir.mkdir(parents=True)
    (proj_dir / ".state.json").write_text('{"x": 1}')

    _migrate_flat_layout(config_base)

    assert not proj_dir.exists()
    assert (config_base / "cache" / "proj-123" / ".state.json").read_text() == '{"x": 1}'


def test_migrate_flat_layout_skips_logs_and_cache_dirs(tmp_path):
    from cognigy_mcp.state import _migrate_flat_layout
    config_base = tmp_path / "cognigy-vibe"
    (config_base / "logs").mkdir(parents=True)
    (config_base / "logs" / "some.log").write_text("log")
    (config_base / "cache" / "existing-proj").mkdir(parents=True)

    _migrate_flat_layout(config_base)

    assert (config_base / "logs" / "some.log").exists()
    assert (config_base / "cache" / "existing-proj").is_dir()
    # nothing extra created under cache/
    assert sorted(p.name for p in (config_base / "cache").iterdir()) == ["existing-proj"]


def test_migrate_flat_layout_noop_if_destination_exists(tmp_path):
    from cognigy_mcp.state import _migrate_flat_layout
    config_base = tmp_path / "cognigy-vibe"
    proj_dir = config_base / "proj-123"
    proj_dir.mkdir(parents=True)
    (proj_dir / "marker").write_text("old")
    dest = config_base / "cache" / "proj-123"
    dest.mkdir(parents=True)
    (dest / "marker").write_text("new")

    _migrate_flat_layout(config_base)

    assert proj_dir.exists()  # untouched — destination already existed
    assert (proj_dir / "marker").read_text() == "old"
    assert (dest / "marker").read_text() == "new"


def test_migrate_flat_layout_noop_if_config_base_missing(tmp_path):
    from cognigy_mcp.state import _migrate_flat_layout
    config_base = tmp_path / "does-not-exist"

    _migrate_flat_layout(config_base)  # must not raise

    assert not config_base.exists()


def test_migrate_flat_layout_survives_concurrent_migration_race(tmp_path, monkeypatch):
    """Simulates a second process winning the race: dest.exists() is False
    when this process checks it, but the entry vanishes before the move
    actually runs (the other process already relocated it)."""
    from cognigy_mcp import state

    config_base = tmp_path / "cognigy-vibe"
    proj_dir = config_base / "proj-123"
    proj_dir.mkdir(parents=True)

    def fake_move(s, d):
        raise FileNotFoundError(s)

    monkeypatch.setattr("shutil.move", fake_move)

    state._migrate_flat_layout(config_base)  # must not raise


def test_migrate_flat_layout_ignores_files_at_root(tmp_path):
    from cognigy_mcp.state import _migrate_flat_layout
    config_base = tmp_path / "cognigy-vibe"
    config_base.mkdir(parents=True)
    (config_base / "config.json").write_text("{}")
    (config_base / ".env").write_text("KEY=1")

    _migrate_flat_layout(config_base)

    assert (config_base / "config.json").exists()
    assert (config_base / ".env").exists()
