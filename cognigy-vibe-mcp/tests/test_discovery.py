from pathlib import Path
from cognigy_mcp.discovery import find_nearest_ancestor, resolve_env_layers


def test_resolve_env_layers_does_not_escape_home_boundary(tmp_path):
    """PR #266 CI review finding: when `home` isn't actually an ancestor of project_root
    (CI checkout, /tmp, mounted volume), resolve_env_layers must not climb past project_root
    onto unrelated ancestors looking for a stray .env — mirrors server.py's
    test_find_config_file_does_not_escape_home_boundary, which this exact scenario could
    silently disagree with (orchestrator sees a stray file server.py correctly ignores)."""
    outside_home = tmp_path / "not-home"
    child = outside_home / "acme-demo"
    child.mkdir(parents=True)
    fake_home = tmp_path / "home-dir"
    fake_home.mkdir()
    (outside_home / ".env").write_text("COGNIGY_BASE_URL=https://stray.example.com\n")

    result = resolve_env_layers(child, fake_home, tmp_path / "user" / ".env")

    assert result.project_env_path is None
    assert result.values == {}


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


def test_resolve_env_layers_survives_non_utf8_user_env(tmp_path):
    """PR #266 CI review Critical finding: a non-UTF-8 .env (e.g. saved as UTF-16 by
    Notepad) must not crash resolve_env_layers — this is a wider blast radius than
    before #255, since both layers are now always read unconditionally (the old
    if/elif code often never touched the second file at all)."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / ".env").write_text("COGNIGY_PROJECT_ID=proj-123\n")
    user_env = tmp_path / "user" / ".env"
    user_env.parent.mkdir()
    user_env.write_bytes("COGNIGY_BASE_URL=https://user.example.com\n".encode("utf-16"))

    result = resolve_env_layers(project_dir, tmp_path, user_env)

    # The corrupted user-global layer contributes nothing, but the valid project
    # layer must still come through — a bad user-global .env shouldn't take down
    # the whole session, nor mask an otherwise-working project .env.
    assert result.values == {"COGNIGY_PROJECT_ID": "proj-123"}


def test_resolve_env_layers_survives_non_utf8_project_env(tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / ".env").write_bytes("COGNIGY_BASE_URL=https://project.example.com\n".encode("utf-16"))
    user_env = tmp_path / "user" / ".env"
    user_env.parent.mkdir()
    user_env.write_text("COGNIGY_API_KEY=userkey\n")

    result = resolve_env_layers(project_dir, tmp_path, user_env)

    assert result.values == {"COGNIGY_API_KEY": "userkey"}


def test_resolve_env_layers_neither_exists(tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    user_env = tmp_path / "user" / ".env"

    result = resolve_env_layers(project_dir, tmp_path, user_env)

    assert result.values == {}
    assert result.sources == {}
    assert result.project_env_path is None
    assert result.user_env_path == user_env


import json
from cognigy_mcp.discovery import resolve_config_layers


def _json_loader(path):
    return json.loads(path.read_text())


def test_resolve_config_layers_project_only(tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "config.json").write_text(json.dumps({"region": "au1"}))
    user_config = tmp_path / "user" / "config.json"

    result = resolve_config_layers("config.json", project_dir, tmp_path, user_config, _json_loader)

    assert result.values == {"region": "au1"}
    assert result.sources["region"] == project_dir / "config.json"
    assert result.project_config_path == project_dir / "config.json"


def test_resolve_config_layers_shallow_merge_nearest_wins(tmp_path):
    """Nested objects are NOT deep-merged — nearest file's top-level key wins wholesale."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "config.json").write_text(json.dumps({"connection": {"region": "na1"}}))
    user_config = tmp_path / "user" / "config.json"
    user_config.parent.mkdir()
    user_config.write_text(json.dumps({
        "connection": {"region": "au1", "timeout": 30},
        "logging": {"level": "debug"},
    }))

    result = resolve_config_layers("config.json", project_dir, tmp_path, user_config, _json_loader)

    # project's "connection" wins wholesale — user's "timeout" field is NOT merged in
    assert result.values == {
        "connection": {"region": "na1"},
        "logging": {"level": "debug"},
    }
    assert result.sources["connection"] == project_dir / "config.json"
    assert result.sources["logging"] == user_config


def test_resolve_config_layers_loader_returning_none_is_skipped(tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "config.json").write_text("not valid json")
    user_config = tmp_path / "user" / "config.json"
    user_config.parent.mkdir()
    user_config.write_text(json.dumps({"region": "jp1"}))

    def _loader_that_rejects_malformed(path):
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            return None

    result = resolve_config_layers(
        "config.json", project_dir, tmp_path, user_config, _loader_that_rejects_malformed
    )

    assert result.values == {"region": "jp1"}
    assert result.sources["region"] == user_config


def test_resolve_config_layers_skips_malformed_ancestor_to_find_valid_grandparent(tmp_path):
    """PR #266 CI review finding: the old server.py _find_config_file() loop kept
    climbing past a malformed nearest-ancestor config to find a valid one further up.
    resolve_config_layers must preserve that — not silently treat a malformed nearest
    file as "no project config" while a valid ancestor config sits one level up."""
    grandparent = tmp_path / "grandparent"
    grandparent.mkdir()
    (grandparent / "config.json").write_text(json.dumps({"region": "valid-grandparent"}))
    project_dir = grandparent / "project"
    project_dir.mkdir()
    (project_dir / "config.json").write_text("not valid json")
    user_config = tmp_path / "user" / "config.json"

    def _loader_that_rejects_malformed(path):
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            return None

    result = resolve_config_layers(
        "config.json", project_dir, tmp_path, user_config, _loader_that_rejects_malformed
    )

    assert result.values == {"region": "valid-grandparent"}
    assert result.project_config_path == grandparent / "config.json"


def test_resolve_config_layers_neither_exists(tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    user_config = tmp_path / "user" / "config.json"

    result = resolve_config_layers("config.json", project_dir, tmp_path, user_config, _json_loader)

    assert result.values == {}
    assert result.project_config_path is None


from cognigy_mcp.discovery import missing_env_keys, build_env_guidance, EnvResolution


def test_missing_env_keys_reports_only_absent_keys():
    resolution = EnvResolution(values={"COGNIGY_BASE_URL": "https://x.example.com"})
    assert missing_env_keys(resolution) == ["COGNIGY_API_KEY"]


def test_missing_env_keys_empty_when_all_present():
    resolution = EnvResolution(values={
        "COGNIGY_BASE_URL": "https://x.example.com",
        "COGNIGY_API_KEY": "key",
    })
    assert missing_env_keys(resolution) == []


def test_build_env_guidance_lists_missing_key_and_both_paths(tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    project_env = project_dir / ".env"
    project_env.write_text("COGNIGY_PROJECT_ID=proj-123\n")
    user_env = tmp_path / "user" / ".env"  # not found

    resolution = EnvResolution(
        values={"COGNIGY_PROJECT_ID": "proj-123"},
        sources={"COGNIGY_PROJECT_ID": project_env},
        project_env_path=project_env,
        user_env_path=user_env,
    )

    text = build_env_guidance(resolution, project_dir)

    assert "COGNIGY_API_KEY" in text
    assert "COGNIGY_BASE_URL" in text
    assert str(project_env) in text
    assert str(user_env) in text
    assert "found" in text  # project file's found-state is shown
    assert "not found" in text  # user file's not-found-state is shown


def test_build_env_guidance_points_to_candidate_path_when_project_env_absent(tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    user_env = tmp_path / "user" / ".env"

    resolution = EnvResolution(
        values={},
        sources={},
        project_env_path=None,
        user_env_path=user_env,
    )

    text = build_env_guidance(resolution, project_dir)

    # No project .env exists yet — guidance must still show where one would be created
    assert str(project_dir / ".env") in text


def test_build_env_guidance_no_trailing_blank_when_nothing_missing(tmp_path):
    """PR #266 CI review suggestion: build_env_guidance shouldn't render a bare
    'Still missing: ' with nothing after the colon if ever called with a fully
    resolved EnvResolution (currently unreachable via the real call sites, but the
    function should degrade sensibly rather than emit a blank)."""
    project_dir = tmp_path / "project"
    user_env = tmp_path / "user" / ".env"
    resolution = EnvResolution(
        values={"COGNIGY_BASE_URL": "https://x.example.com", "COGNIGY_API_KEY": "key"},
        user_env_path=user_env,
    )

    text = build_env_guidance(resolution, project_dir)

    assert "Still missing: \n" not in text
