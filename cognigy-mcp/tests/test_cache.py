import json
import time
import pytest
from pathlib import Path
from cognigy_mcp.cache import Cache


@pytest.fixture
def cache(tmp_path):
    return Cache(cache_dir=tmp_path / "cache", ttl=60)


def test_miss_returns_none_not_fresh(cache):
    data, fresh = cache.get("flows", "123")
    assert data is None
    assert not fresh


def test_set_then_get_fresh(cache):
    cache.set("flows", "123", {"_id": "123", "name": "My Flow"})
    data, fresh = cache.get("flows", "123")
    assert data["_id"] == "123"
    assert fresh


def test_expired_entry_returns_stale(tmp_path):
    c = Cache(cache_dir=tmp_path / "cache", ttl=0)
    c.set("flows", "abc", {"_id": "abc"})
    _, fresh = c.get("flows", "abc")
    assert not fresh


def test_set_creates_parent_dirs(cache):
    cache.set("aiagents", "agent-1", {"_id": "agent-1"})
    assert (cache.cache_dir / "aiagents" / "agent-1.json").exists()


def test_invalidate_removes_entry(cache):
    cache.set("flows", "123", {"_id": "123"})
    cache.invalidate("flows", "123")
    data, _ = cache.get("flows", "123")
    assert data is None


def test_invalidate_all_wipes_everything(cache):
    cache.set("flows", "123", {"_id": "123"})
    cache.set("aiagents", "agent-1", {"_id": "agent-1"})
    cache.invalidate_all()
    assert not any(cache.cache_dir.rglob("*.json"))


def test_node_snapshot_roundtrip(cache):
    cache.set_node_snapshot("node-abc", "const x = 1;")
    assert cache.get_node_snapshot("node-abc") == "const x = 1;"


def test_node_snapshot_returns_none_when_missing(cache):
    assert cache.get_node_snapshot("no-such-node") is None


def test_node_snapshot_update(cache):
    cache.set_node_snapshot("node-abc", "old content")
    cache.set_node_snapshot("node-abc", "new content")
    assert cache.get_node_snapshot("node-abc") == "new content"
