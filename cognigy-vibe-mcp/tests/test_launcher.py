from unittest.mock import patch


def test_launcher_calls_orchestrator_main():
    """Launcher must delegate to orchestrator.main()."""
    import cognigy_mcp.launcher as launcher_mod

    with patch("cognigy_mcp.orchestrator.main") as mock_main:
        launcher_mod.main()
        mock_main.assert_called_once()


def test_launcher_reads_version():
    """Launcher must be able to read its own installed version."""
    from importlib.metadata import version
    ver = version("cognigy-vibe-mcp")
    assert ver
    # Version is a non-empty string like "1.7.0"
    assert len(ver) > 0
    assert "." in ver


def test_launcher_logs_version_to_stderr(capsys):
    """Launcher must print version info to stderr, not stdout."""
    import cognigy_mcp.launcher as launcher_mod

    with patch("cognigy_mcp.orchestrator.main"):
        launcher_mod.main()
    captured = capsys.readouterr()
    assert captured.out == ""  # nothing on stdout
    assert "cognigy-vibe-launch" in captured.err
