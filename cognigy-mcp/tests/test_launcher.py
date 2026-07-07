import sys
from unittest.mock import patch, MagicMock


def test_launcher_calls_orchestrator_main():
    """Launcher must delegate to orchestrator.main()."""
    mock_orchestrator = MagicMock()
    with patch.dict("sys.modules", {
        "truststore": MagicMock(),
        "cognigy_mcp.orchestrator": mock_orchestrator,
    }):
        # Force reimport so patched modules are used
        import importlib
        import cognigy_mcp.launcher as launcher_mod
        importlib.reload(launcher_mod)
        launcher_mod.main()
        mock_orchestrator.main.assert_called_once()


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
    mock_orchestrator = MagicMock()
    with patch.dict("sys.modules", {
        "truststore": MagicMock(),
        "cognigy_mcp.orchestrator": mock_orchestrator,
    }):
        import importlib
        import cognigy_mcp.launcher as launcher_mod
        importlib.reload(launcher_mod)
        launcher_mod.main()
    captured = capsys.readouterr()
    assert captured.out == ""  # nothing on stdout
    assert "cognigy-vibe-launch" in captured.err
