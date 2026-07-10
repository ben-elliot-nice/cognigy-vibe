def test_safe_move_moves_when_dest_absent(tmp_path):
    from cognigy_mcp.migrate import safe_move
    src = tmp_path / "src"
    src.mkdir()
    (src / "marker").write_text("data")
    dest = tmp_path / "dest"

    safe_move(src, dest)

    assert not src.exists()
    assert (dest / "marker").read_text() == "data"


def test_safe_move_noop_when_dest_exists(tmp_path):
    from cognigy_mcp.migrate import safe_move
    src = tmp_path / "src"
    src.mkdir()
    (src / "marker").write_text("old")
    dest = tmp_path / "dest"
    dest.mkdir()
    (dest / "marker").write_text("new")

    safe_move(src, dest)

    assert src.exists()  # untouched — destination already existed
    assert (dest / "marker").read_text() == "new"


def test_safe_move_swallows_race_where_src_vanishes(tmp_path, monkeypatch):
    """Simulates another process winning the race: dest.exists() is False when
    checked, but src is gone by the time shutil.move actually runs."""
    from cognigy_mcp import migrate

    src = tmp_path / "src"
    src.mkdir()
    dest = tmp_path / "dest"

    def fake_move(s, d):
        raise FileNotFoundError(s)

    monkeypatch.setattr("shutil.move", fake_move)

    migrate.safe_move(src, dest)  # must not raise


def test_safe_move_propagates_other_os_errors(tmp_path, monkeypatch):
    from cognigy_mcp import migrate

    src = tmp_path / "src"
    src.mkdir()
    dest = tmp_path / "dest"

    def fake_move(s, d):
        raise PermissionError("denied")

    monkeypatch.setattr("shutil.move", fake_move)

    import pytest
    with pytest.raises(PermissionError):
        migrate.safe_move(src, dest)
