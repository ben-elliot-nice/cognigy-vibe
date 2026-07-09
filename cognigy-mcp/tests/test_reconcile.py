# cognigy-mcp/tests/test_reconcile.py
from cognigy_mcp.reconcile import SetupState, DriftIssue


def test_setup_state_holds_all_five_surfaces():
    state = SetupState(
        package_version="1.7.0",
        marketplace_ref="v1.7.0",
        plugin_version="1.7.0",
        plugin_scope="user",
        desktop_pin="1.7.0",
        layout_schema_version=1,
    )
    assert state.package_version == "1.7.0"
    assert state.layout_schema_version == 1


def test_drift_issue_has_surface_current_expected_kind():
    issue = DriftIssue(surface="plugin_version", current="1.6.0", expected="1.7.0", kind="drift")
    assert issue.kind == "drift"
    assert issue.current == "1.6.0"
