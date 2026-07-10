import pytest
from unittest.mock import MagicMock
from cognigy_mcp.cache import Cache
from cognigy_mcp.state import ProjectState


@pytest.fixture
def mock_client():
    return MagicMock()


@pytest.fixture
def cache(tmp_path):
    return Cache(cache_dir=tmp_path / "cache", ttl=60)


@pytest.fixture
def state(tmp_path, monkeypatch):
    monkeypatch.setattr("cognigy_mcp.state.CONFIG_BASE", tmp_path / "config")
    return ProjectState(project_id="test-proj")
