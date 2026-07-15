from pathlib import Path
from cognigy_mcp.discovery import find_nearest_ancestor, resolve_env_layers


def test_find_nearest_ancestor_in_start_dir(tmp_path):
    (tmp_path / ".env").write_text("X=1\n")
    result = find_nearest_ancestor(".env", tmp_path, tmp_path.parent)
    assert result == tmp_path / ".env"


def test_find_nearest_ancestor_in_parent(tmp_path):
    (tmp_path / ".env").write_text("X=1\n")
    child = tmp_path / "child"
    child.mkdir()
    result = find_nearest_ancestor(".env", child, tmp_path.parent)
    assert result == tmp_path / ".env"


def test_find_nearest_ancestor_stops_at_boundary(tmp_path):
    child = tmp_path / "child"
    child.mkdir()
    result = find_nearest_ancestor(".env", child, tmp_path)  # stop at tmp_path, not its parent
    assert result is None


def test_find_nearest_ancestor_not_found(tmp_path):
    child = tmp_path / "child"
    child.mkdir()
    result = find_nearest_ancestor(".env", child, tmp_path)
    assert result is None


def test_find_nearest_ancestor_grandparent(tmp_path):
    (tmp_path / ".env").write_text("X=1\n")
    grandchild = tmp_path / "child" / "grandchild"
    grandchild.mkdir(parents=True)
    result = find_nearest_ancestor(".env", grandchild, tmp_path.parent)
    assert result == tmp_path / ".env"


def test_resolve_env_layers_project_only(tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / ".env").write_text("COGNIGY_BASE_URL=https://project.example.com\n")
    user_env = tmp_path / "user" / ".env"  # does not exist

    result = resolve_env_layers(project_dir, tmp_path, user_env)

    assert result.values == {"COGNIGY_BASE_URL": "https://project.example.com"}
    assert result.sources["COGNIGY_BASE_URL"] == project_dir / ".env"
    assert result.project_env_path == project_dir / ".env"
    assert result.user_env_path == user_env


def test_resolve_env_layers_user_only(tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    user_env = tmp_path / "user" / ".env"
    user_env.parent.mkdir()
    user_env.write_text("COGNIGY_BASE_URL=https://user.example.com\nCOGNIGY_API_KEY=userkey\n")

    result = resolve_env_layers(project_dir, tmp_path, user_env)

    assert result.values == {
        "COGNIGY_BASE_URL": "https://user.example.com",
        "COGNIGY_API_KEY": "userkey",
    }
    assert result.sources["COGNIGY_API_KEY"] == user_env
    assert result.project_env_path is None


def test_resolve_env_layers_merges_nearest_wins_per_key(tmp_path):
    """This is the #255 regression case: project .env has only the project id,
    user .env has the credentials — both must end up in the merged result."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / ".env").write_text("COGNIGY_PROJECT_ID=proj-123\n")
    user_env = tmp_path / "user" / ".env"
    user_env.parent.mkdir()
    user_env.write_text(
        "COGNIGY_BASE_URL=https://user.example.com\n"
        "COGNIGY_API_KEY=userkey\n"
        "COGNIGY_PROJECT_ID=should-be-overridden\n"
    )

    result = resolve_env_layers(project_dir, tmp_path, user_env)

    assert result.values == {
        "COGNIGY_PROJECT_ID": "proj-123",
        "COGNIGY_BASE_URL": "https://user.example.com",
        "COGNIGY_API_KEY": "userkey",
    }
    assert result.sources["COGNIGY_PROJECT_ID"] == project_dir / ".env"
    assert result.sources["COGNIGY_BASE_URL"] == user_env


def test_resolve_env_layers_neither_exists(tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    user_env = tmp_path / "user" / ".env"

    result = resolve_env_layers(project_dir, tmp_path, user_env)

    assert result.values == {}
    assert result.sources == {}
    assert result.project_env_path is None
    assert result.user_env_path == user_env
