"""Tests for #408: the sidecar (bundled Python process, D52 protocol) and its
host-side restart policy (locks 3/4/12).

The sidecar must speak the *same* JSON-RPC-over-stdio contract as a command
plugin (d52_proof) so the host has one process protocol; these tests pin the
wire shape and the restart-policy state machine.
"""

from __future__ import annotations

import json

from tool import WorkspaceStore
from tool.sidecar import RestartDecision, SidecarRestartPolicy, SidecarServer


def _server(tmp_path) -> SidecarServer:
    return SidecarServer(WorkspaceStore(root=tmp_path))


class TestSidecarProtocol:
    def test_initialize_handshake(self, tmp_path):
        resp = json.loads(_server(tmp_path).handle('{"jsonrpc":"2.0","id":1,"method":"initialize"}'))
        assert resp["id"] == 1
        result = resp["result"]
        assert result["protocolVersion"] == "1"
        assert result["serverInfo"]["name"] == "devtool-sidecar"
        assert result["capabilities"]["artifacts"] is True

    def test_list_artifacts_serves_python_plugins(self, tmp_path):
        resp = json.loads(_server(tmp_path).handle('{"jsonrpc":"2.0","id":2,"method":"list_artifacts"}'))
        assert resp["id"] == 2
        artifacts = resp["result"]["artifacts"]
        assert isinstance(artifacts, list)
        for artifact in artifacts:
            assert {"kind", "name", "path", "meta"} <= set(artifact)

    def test_ping(self, tmp_path):
        resp = json.loads(_server(tmp_path).handle('{"jsonrpc":"2.0","id":3,"method":"ping"}'))
        assert resp["result"] == {}

    def test_unknown_method(self, tmp_path):
        resp = json.loads(_server(tmp_path).handle('{"jsonrpc":"2.0","id":4,"method":"nope"}'))
        assert resp["error"]["code"] == -32601

    def test_parse_error_id_null(self, tmp_path):
        resp = json.loads(_server(tmp_path).handle("{not json"))
        assert resp["id"] is None
        assert resp["error"]["code"] == -32700

    def test_notification_no_response(self, tmp_path):
        assert _server(tmp_path).handle('{"jsonrpc":"2.0","method":"ping"}') is None

    def test_serve_stdio_end_to_end(self, tmp_path):
        import io

        stdin = io.StringIO(
            '{"jsonrpc":"2.0","id":1,"method":"initialize"}\n'
            '{"jsonrpc":"2.0","id":2,"method":"ping"}\n'
        )
        stdout = io.StringIO()
        _server(tmp_path).serve_stdio(stdin=stdin, stdout=stdout)
        lines = [json.loads(l) for l in stdout.getvalue().strip().splitlines()]
        assert [l["id"] for l in lines] == [1, 2]

    def test_visual_and_world_state_rpc_methods(self, tmp_path):
        server = _server(tmp_path)

        # 1. get_meta_graph
        resp = json.loads(server.handle('{"jsonrpc":"2.0","id":10,"method":"get_meta_graph"}'))
        assert resp["id"] == 10
        assert "graph" in resp["result"]
        assert len(resp["result"]["graph"]["nodes"]) >= 3
        assert len(resp["result"]["nexus_nodes"]) >= 1

        # 2. get_flame_graph
        resp = json.loads(server.handle('{"jsonrpc":"2.0","id":11,"method":"get_flame_graph"}'))
        assert resp["id"] == 11
        assert "tree" in resp["result"]
        assert resp["result"]["total_time_ms"] > 0

        # 3. get_metrics_timeline
        resp = json.loads(server.handle('{"jsonrpc":"2.0","id":12,"method":"get_metrics_timeline"}'))
        assert resp["id"] == 12
        assert "rss_memory" in resp["result"]
        assert len(resp["result"]["rss_memory"]["points"]) > 0

        # 4. get_pipeline_scrubber
        resp = json.loads(server.handle('{"jsonrpc":"2.0","id":13,"method":"get_pipeline_scrubber","params":{"t_ms":150.0}}'))
        assert resp["id"] == 13
        assert "session" in resp["result"]
        assert "evaluation" in resp["result"]
        assert resp["result"]["evaluation"]["timestamp_ms"] == 150.0

        # 5. get_world_state & save_world_state
        resp = json.loads(server.handle('{"jsonrpc":"2.0","id":14,"method":"get_world_state"}'))
        assert resp["id"] == 14
        world_state = resp["result"]
        world_state["camera"]["label"] = "Custom Front Vantage"

        resp_save = json.loads(server.handle(json.dumps({
            "jsonrpc": "2.0",
            "id": 15,
            "method": "save_world_state",
            "params": {"world_state": world_state},
        })))
        assert resp_save["id"] == 15
        assert resp_save["result"]["saved"] is True

        resp_reload = json.loads(server.handle('{"jsonrpc":"2.0","id":16,"method":"get_world_state"}'))
        assert resp_reload["result"]["camera"]["label"] == "Custom Front Vantage"


class TestRestartPolicy:
    def test_crash_before_initialize_is_hard_fail(self):
        policy = SidecarRestartPolicy()
        decision = policy.on_exit(clean=False)
        assert isinstance(decision, RestartDecision)
        assert decision.restart is False

    def test_initialize_success_then_crash_restarts_once(self):
        policy = SidecarRestartPolicy()
        policy.on_initialize_success()
        decision = policy.on_exit(clean=False)
        assert decision.restart is True
        assert policy.restarts_used == 1

    def test_no_loop_after_one_restart(self):
        policy = SidecarRestartPolicy()
        policy.on_initialize_success()
        assert policy.on_exit(clean=False).restart is True
        policy.on_initialize_success()  # restart succeeded, initialized again
        assert policy.on_exit(clean=False).restart is False  # hard fail, no loop

    def test_clean_exit_never_restarts(self):
        policy = SidecarRestartPolicy()
        policy.on_initialize_success()
        assert policy.on_exit(clean=True).restart is False
        assert policy.restarts_used == 0

    def test_initialize_failure_then_crash_no_restart(self):
        policy = SidecarRestartPolicy()
        policy.on_initialize_failure()
        assert policy.on_exit(clean=False).restart is False

    def test_cli_exports_policy(self):
        from tool.cli.parser import COMMANDS
        from tool.sidecar import MAX_AUTO_RESTARTS

        assert "sidecar" in COMMANDS
        assert MAX_AUTO_RESTARTS == 1
