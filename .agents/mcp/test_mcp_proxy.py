#!/usr/bin/env python3
"""Unit tests for mcp-proxy.py — MCP stdio logging proxy."""

import fcntl
import json
import os
import signal
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest

PROXY_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mcp-proxy.py")
PYTHON = sys.executable
LOG_FILENAME = "mcp-tools.jsonl"


def _make_jsonrpc_request(id, method, params=None):
    msg = {"jsonrpc": "2.0", "id": id, "method": method}
    if params is not None:
        msg["params"] = params
    return json.dumps(msg) + "\n"


def _make_jsonrpc_response(id, result=None, error=None):
    msg = {"jsonrpc": "2.0", "id": id}
    if error is not None:
        msg["error"] = error
    else:
        msg["result"] = result
    return json.dumps(msg) + "\n"


def _make_tools_call_request(id, tool_name, arguments=None):
    return _make_jsonrpc_request(id, "tools/call", {
        "name": tool_name,
        "arguments": arguments or {},
    })


def _make_tools_call_response(id, text_content="ok"):
    return _make_jsonrpc_response(id, result={
        "content": [{"type": "text", "text": text_content}],
    })


def _echo_server_script():
    """Python script that acts as a trivial MCP echo server.

    Reads JSON-RPC lines from stdin.  For tools/call requests it replies with
    the tool name echoed back.  For everything else it echoes the input.
    """
    return textwrap.dedent("""\
        import sys, json
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                sys.stdout.write(line + "\\n")
                sys.stdout.flush()
                continue
            if msg.get("method") == "tools/call":
                tool = msg["params"]["name"]
                args = msg["params"].get("arguments", {})
                resp = {
                    "jsonrpc": "2.0",
                    "id": msg["id"],
                    "result": {
                        "content": [{"type": "text", "text": f"echo:{tool}:{json.dumps(args)}"}]
                    }
                }
                sys.stdout.write(json.dumps(resp) + "\\n")
                sys.stdout.flush()
            elif "id" in msg:
                resp = {"jsonrpc": "2.0", "id": msg["id"], "result": {"ok": True}}
                sys.stdout.write(json.dumps(resp) + "\\n")
                sys.stdout.flush()
            # notifications (no id) are silently consumed
    """)


def _start_proxy(server_script_path, room_dir, server_name="test-server", extra_env=None):
    """Start the proxy wrapping a child server script. Returns the Popen handle."""
    env = os.environ.copy()
    env["AGENT_OS_ROOM_DIR"] = room_dir
    if extra_env:
        env.update(extra_env)
    proc = subprocess.Popen(
        [PYTHON, PROXY_SCRIPT, "--server-name", server_name, "--",
         PYTHON, server_script_path],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    return proc


def _send_and_recv(proc, message, timeout=5):
    """Send a line to the proxy and read one response line."""
    proc.stdin.write(message.encode() if isinstance(message, str) else message)
    proc.stdin.flush()
    import select
    ready, _, _ = select.select([proc.stdout], [], [], timeout)
    if not ready:
        return None
    line = proc.stdout.readline()
    return line.decode() if line else None


def _read_log(room_dir):
    """Read and parse all entries from mcp-tools.jsonl."""
    path = os.path.join(room_dir, LOG_FILENAME)
    if not os.path.exists(path):
        return []
    entries = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


class TestArgParsing(unittest.TestCase):
    """Test that the proxy parses CLI arguments correctly."""

    def test_server_name_and_command(self):
        """--server-name NAME -- command args..."""
        proc = subprocess.run(
            [PYTHON, PROXY_SCRIPT, "--server-name", "myserver", "--", "echo", "hello"],
            capture_output=True, timeout=5,
        )
        # echo exits immediately, proxy should exit with 0
        self.assertEqual(proc.returncode, 0)

    def test_default_server_name(self):
        """Without --server-name, derive from command basename."""
        tmpdir = tempfile.mkdtemp()
        server_script = os.path.join(tmpdir, "echo_server.py")
        with open(server_script, "w") as f:
            f.write(_echo_server_script())

        env = os.environ.copy()
        env["AGENT_OS_ROOM_DIR"] = tmpdir
        proc = subprocess.Popen(
            [PYTHON, PROXY_SCRIPT, "--", PYTHON, server_script],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=env,
        )
        # Send a tools/call so a log entry is created with the server name
        req = _make_tools_call_request(1, "test_tool")
        resp = _send_and_recv(proc, req)
        self.assertIsNotNone(resp)

        proc.stdin.close()
        proc.wait(timeout=5)

        entries = _read_log(tmpdir)
        self.assertEqual(len(entries), 1)
        # Default server name should be derived from command (python)
        self.assertIn(entries[0]["server"], [os.path.basename(PYTHON), "python", "python3"])

    def test_missing_separator(self):
        """Proxy should fail if -- separator is missing."""
        proc = subprocess.run(
            [PYTHON, PROXY_SCRIPT, "echo", "hello"],
            capture_output=True, timeout=5,
        )
        self.assertNotEqual(proc.returncode, 0)


class TestToolCallLogging(unittest.TestCase):
    """Test that tools/call requests are intercepted and logged."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.server_script = os.path.join(self.tmpdir, "echo_server.py")
        with open(self.server_script, "w") as f:
            f.write(_echo_server_script())

    def test_basic_tool_call_logged(self):
        """A tools/call request+response pair produces a log entry."""
        proc = _start_proxy(self.server_script, self.tmpdir)
        req = _make_tools_call_request(1, "read_file", {"path": "/tmp/foo.txt"})
        resp = _send_and_recv(proc, req)
        self.assertIsNotNone(resp)

        # Verify the response was forwarded correctly
        resp_data = json.loads(resp)
        self.assertEqual(resp_data["id"], 1)
        self.assertIn("result", resp_data)

        proc.stdin.close()
        proc.wait(timeout=5)

        entries = _read_log(self.tmpdir)
        self.assertEqual(len(entries), 1)

        entry = entries[0]
        self.assertEqual(entry["server"], "test-server")
        self.assertEqual(entry["tool"], "read_file")
        self.assertEqual(entry["args"], {"path": "/tmp/foo.txt"})
        self.assertTrue(entry["ok"])
        self.assertIn("ts", entry)
        self.assertIn("elapsed_ms", entry)
        self.assertIn("result", entry)

    def test_multiple_tool_calls(self):
        """Multiple sequential tool calls are all logged."""
        proc = _start_proxy(self.server_script, self.tmpdir)

        for i in range(1, 4):
            req = _make_tools_call_request(i, f"tool_{i}", {"n": i})
            resp = _send_and_recv(proc, req)
            self.assertIsNotNone(resp)

        proc.stdin.close()
        proc.wait(timeout=5)

        entries = _read_log(self.tmpdir)
        self.assertEqual(len(entries), 3)
        for i, entry in enumerate(entries, 1):
            self.assertEqual(entry["tool"], f"tool_{i}")
            self.assertEqual(entry["args"], {"n": i})

    def test_interleaved_non_tool_messages(self):
        """Non-tool messages between tool calls don't break logging."""
        proc = _start_proxy(self.server_script, self.tmpdir)

        # Send initialize
        init = _make_jsonrpc_request(100, "initialize", {"protocolVersion": "2024-11-05"})
        resp = _send_and_recv(proc, init)
        self.assertIsNotNone(resp)

        # Send tool call
        req = _make_tools_call_request(1, "my_tool")
        resp = _send_and_recv(proc, req)
        self.assertIsNotNone(resp)

        proc.stdin.close()
        proc.wait(timeout=5)

        entries = _read_log(self.tmpdir)
        # Only the tool call should be logged, not initialize
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["tool"], "my_tool")


class TestPassthrough(unittest.TestCase):
    """Test that non-tool messages are forwarded without modification."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.server_script = os.path.join(self.tmpdir, "echo_server.py")
        with open(self.server_script, "w") as f:
            f.write(_echo_server_script())

    def test_initialize_forwarded(self):
        """An initialize request is forwarded and response returned."""
        proc = _start_proxy(self.server_script, self.tmpdir)

        req = _make_jsonrpc_request(1, "initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "0.1"},
        })
        resp = _send_and_recv(proc, req)
        self.assertIsNotNone(resp)
        resp_data = json.loads(resp)
        self.assertEqual(resp_data["id"], 1)
        self.assertIn("result", resp_data)

        proc.stdin.close()
        proc.wait(timeout=5)

        # No log entries for non-tool messages
        entries = _read_log(self.tmpdir)
        self.assertEqual(len(entries), 0)

    def test_notification_forwarded_no_log(self):
        """JSON-RPC notifications (no id) are forwarded, not logged."""
        proc = _start_proxy(self.server_script, self.tmpdir)

        # Notifications have no "id" — server consumes them silently
        notification = json.dumps({
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        }) + "\n"
        proc.stdin.write(notification.encode())
        proc.stdin.flush()

        # Send a tool call to verify proxy is still working
        req = _make_tools_call_request(1, "check")
        resp = _send_and_recv(proc, req)
        self.assertIsNotNone(resp)

        proc.stdin.close()
        proc.wait(timeout=5)

        entries = _read_log(self.tmpdir)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["tool"], "check")


class TestMalformedInput(unittest.TestCase):
    """Test handling of malformed or non-JSON lines."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.server_script = os.path.join(self.tmpdir, "echo_server.py")
        with open(self.server_script, "w") as f:
            f.write(_echo_server_script())

    def test_non_json_line_forwarded(self):
        """Non-JSON lines are forwarded without crashing."""
        proc = _start_proxy(self.server_script, self.tmpdir)

        # Send garbage, then a valid tool call
        proc.stdin.write(b"this is not json\n")
        proc.stdin.flush()

        req = _make_tools_call_request(1, "after_garbage")
        # The echo server echoes back the garbage line first, then the tool response.
        # Read until we get the JSON-RPC response for our tool call.
        proc.stdin.write(req.encode())
        proc.stdin.flush()

        import select
        lines = []
        tool_resp = None
        for _ in range(10):  # read up to 10 lines
            ready, _, _ = select.select([proc.stdout], [], [], 5)
            if not ready:
                break
            line = proc.stdout.readline().decode()
            if not line:
                break
            lines.append(line)
            try:
                data = json.loads(line)
                if data.get("id") == 1:
                    tool_resp = data
                    break
            except json.JSONDecodeError:
                continue  # garbage echo — skip

        self.assertIsNotNone(tool_resp, f"Never got tool response. Lines received: {lines}")
        self.assertEqual(tool_resp["id"], 1)

        proc.stdin.close()
        proc.wait(timeout=5)

        entries = _read_log(self.tmpdir)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["tool"], "after_garbage")

    def test_empty_lines_ignored(self):
        """Empty lines don't crash the proxy."""
        proc = _start_proxy(self.server_script, self.tmpdir)

        proc.stdin.write(b"\n\n\n")
        proc.stdin.flush()

        req = _make_tools_call_request(1, "still_works")
        resp = _send_and_recv(proc, req)
        self.assertIsNotNone(resp)

        proc.stdin.close()
        proc.wait(timeout=5)


class TestResultTruncation(unittest.TestCase):
    """Test that large results are truncated in the log."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        # Server that returns a large result
        self.server_script = os.path.join(self.tmpdir, "big_server.py")
        with open(self.server_script, "w") as f:
            f.write(textwrap.dedent("""\
                import sys, json
                for line in sys.stdin:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        msg = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if msg.get("method") == "tools/call":
                        big_text = "X" * 10000
                        resp = {
                            "jsonrpc": "2.0",
                            "id": msg["id"],
                            "result": {
                                "content": [{"type": "text", "text": big_text}]
                            }
                        }
                        sys.stdout.write(json.dumps(resp) + "\\n")
                        sys.stdout.flush()
            """))

    def test_result_truncated_in_log(self):
        """Results larger than 4096 chars are truncated in the log file."""
        proc = _start_proxy(self.server_script, self.tmpdir)

        req = _make_tools_call_request(1, "big_tool")
        resp = _send_and_recv(proc, req)
        self.assertIsNotNone(resp)

        # The RESPONSE to the client should NOT be truncated
        resp_data = json.loads(resp)
        result_text = resp_data["result"]["content"][0]["text"]
        self.assertEqual(len(result_text), 10000)

        proc.stdin.close()
        proc.wait(timeout=5)

        entries = _read_log(self.tmpdir)
        self.assertEqual(len(entries), 1)
        # Log entry result should be truncated
        self.assertLessEqual(len(entries[0]["result"]), 4096 + 10)  # some slack for "…"


class TestErrorResponses(unittest.TestCase):
    """Test logging of JSON-RPC error responses."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.server_script = os.path.join(self.tmpdir, "error_server.py")
        with open(self.server_script, "w") as f:
            f.write(textwrap.dedent("""\
                import sys, json
                for line in sys.stdin:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        msg = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if msg.get("method") == "tools/call":
                        resp = {
                            "jsonrpc": "2.0",
                            "id": msg["id"],
                            "error": {
                                "code": -32000,
                                "message": "Tool execution failed: file not found"
                            }
                        }
                        sys.stdout.write(json.dumps(resp) + "\\n")
                        sys.stdout.flush()
            """))

    def test_error_response_logged(self):
        """Error responses are logged with ok=false and error field."""
        proc = _start_proxy(self.server_script, self.tmpdir)

        req = _make_tools_call_request(1, "failing_tool", {"path": "/missing"})
        resp = _send_and_recv(proc, req)
        self.assertIsNotNone(resp)

        # Error should be forwarded to client
        resp_data = json.loads(resp)
        self.assertIn("error", resp_data)

        proc.stdin.close()
        proc.wait(timeout=5)

        entries = _read_log(self.tmpdir)
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertFalse(entry["ok"])
        self.assertIn("error", entry)
        self.assertIn("file not found", entry["error"])
        self.assertEqual(entry["tool"], "failing_tool")


class TestMissingRoomDir(unittest.TestCase):
    """Test behavior when AGENT_OS_ROOM_DIR is not set."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.server_script = os.path.join(self.tmpdir, "echo_server.py")
        with open(self.server_script, "w") as f:
            f.write(_echo_server_script())

    def test_no_room_dir_still_forwards(self):
        """Without AGENT_OS_ROOM_DIR, proxy still forwards traffic — just no logging."""
        env = os.environ.copy()
        env.pop("AGENT_OS_ROOM_DIR", None)
        proc = subprocess.Popen(
            [PYTHON, PROXY_SCRIPT, "--server-name", "test", "--",
             PYTHON, self.server_script],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=env,
        )

        req = _make_tools_call_request(1, "test_tool")
        resp = _send_and_recv(proc, req)
        self.assertIsNotNone(resp)
        resp_data = json.loads(resp)
        self.assertEqual(resp_data["id"], 1)

        proc.stdin.close()
        proc.wait(timeout=5)

        # No log file should be created
        self.assertFalse(os.path.exists(os.path.join(self.tmpdir, LOG_FILENAME)))


class TestChildExitCode(unittest.TestCase):
    """Test that the proxy exits with the child's exit code."""

    def test_child_exits_zero(self):
        """Proxy exits 0 when child exits 0."""
        proc = subprocess.run(
            [PYTHON, PROXY_SCRIPT, "--", PYTHON, "-c", "pass"],
            capture_output=True, timeout=5,
        )
        self.assertEqual(proc.returncode, 0)

    def test_child_exits_nonzero(self):
        """Proxy exits with same code when child exits non-zero."""
        proc = subprocess.run(
            [PYTHON, PROXY_SCRIPT, "--", PYTHON, "-c", "import sys; sys.exit(42)"],
            capture_output=True, timeout=5,
        )
        self.assertEqual(proc.returncode, 42)


class TestTiming(unittest.TestCase):
    """Test that elapsed_ms is approximately correct."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        # Server that sleeps before responding
        self.server_script = os.path.join(self.tmpdir, "slow_server.py")
        with open(self.server_script, "w") as f:
            f.write(textwrap.dedent("""\
                import sys, json, time
                for line in sys.stdin:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        msg = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if msg.get("method") == "tools/call":
                        time.sleep(0.15)
                        resp = {
                            "jsonrpc": "2.0",
                            "id": msg["id"],
                            "result": {"content": [{"type": "text", "text": "done"}]}
                        }
                        sys.stdout.write(json.dumps(resp) + "\\n")
                        sys.stdout.flush()
            """))

    def test_elapsed_ms_approximate(self):
        """elapsed_ms should be roughly the time between request and response."""
        proc = _start_proxy(self.server_script, self.tmpdir)

        req = _make_tools_call_request(1, "slow_tool")
        resp = _send_and_recv(proc, req, timeout=10)
        self.assertIsNotNone(resp)

        proc.stdin.close()
        proc.wait(timeout=5)

        entries = _read_log(self.tmpdir)
        self.assertEqual(len(entries), 1)
        elapsed = entries[0]["elapsed_ms"]
        # Should be at least 100ms (server sleeps 150ms, allow some slack)
        self.assertGreater(elapsed, 100)
        # Should be less than 5000ms (generous upper bound)
        self.assertLess(elapsed, 5000)


class TestConcurrentWrites(unittest.TestCase):
    """Test that concurrent proxy instances don't corrupt the log file."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.server_script = os.path.join(self.tmpdir, "echo_server.py")
        with open(self.server_script, "w") as f:
            f.write(_echo_server_script())

    def test_two_proxies_same_log(self):
        """Two proxy processes writing to the same log produce valid JSONL."""
        proc1 = _start_proxy(self.server_script, self.tmpdir, server_name="srv1")
        proc2 = _start_proxy(self.server_script, self.tmpdir, server_name="srv2")

        n_calls = 5
        for i in range(n_calls):
            req1 = _make_tools_call_request(i + 1, f"tool_a_{i}")
            req2 = _make_tools_call_request(i + 1, f"tool_b_{i}")
            resp1 = _send_and_recv(proc1, req1)
            resp2 = _send_and_recv(proc2, req2)
            self.assertIsNotNone(resp1)
            self.assertIsNotNone(resp2)

        proc1.stdin.close()
        proc2.stdin.close()
        proc1.wait(timeout=5)
        proc2.wait(timeout=5)

        entries = _read_log(self.tmpdir)
        self.assertEqual(len(entries), n_calls * 2)

        # Verify each line is valid JSON (no corruption from interleaving)
        log_path = os.path.join(self.tmpdir, LOG_FILENAME)
        with open(log_path) as f:
            for lineno, line in enumerate(f, 1):
                try:
                    json.loads(line)
                except json.JSONDecodeError:
                    self.fail(f"Corrupted JSON at line {lineno}: {line!r}")

        # Both servers should be represented
        servers = {e["server"] for e in entries}
        self.assertEqual(servers, {"srv1", "srv2"})


class TestSignalForwarding(unittest.TestCase):
    """Test that SIGTERM is forwarded to the child process."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.server_script = os.path.join(self.tmpdir, "long_server.py")
        with open(self.server_script, "w") as f:
            f.write(textwrap.dedent("""\
                import sys, time, signal
                signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
                while True:
                    time.sleep(0.1)
            """))

    def test_sigterm_kills_proxy_and_child(self):
        """Sending SIGTERM to the proxy should terminate both proxy and child."""
        proc = _start_proxy(self.server_script, self.tmpdir)
        time.sleep(0.3)  # Let the child start

        # Send SIGTERM
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            self.fail("Proxy did not exit after SIGTERM")

        # Proxy should have exited
        self.assertIsNotNone(proc.returncode)


if __name__ == "__main__":
    unittest.main()
