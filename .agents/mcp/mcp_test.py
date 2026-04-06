import sys
import os
import json
import subprocess
import time
import requests
from typing import Dict, Any, Optional

def test_http_server(url: str, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Test connectivity to an MCP HTTP server."""
    start_time = time.time()
    try:
        # MCP spec: listTools is a common GET/POST endpoint to test connectivity
        # We'll try POST to 'listTools' first as it's common in MCP implementations
        # or just GET the base URL if it's a discovery endpoint.
        # But per MCP spec, it should be a JSON-RPC 2.0 request.
        
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "listTools",
            "params": {}
        }
        
        response = requests.post(
            url,
            json=payload,
            headers=headers or {},
            timeout=10
        )
        
        duration = time.time() - start_time
        
        if response.status_code != 200:
            return {
                "status": "error",
                "message": f"HTTP {response.status_code}",
                "detail": response.text[:200],
                "duration": duration
            }
            
        data = response.json()
        if "error" in data:
            return {
                "status": "error",
                "message": f"MCP Error: {data['error'].get('message', 'Unknown error')}",
                "detail": json.dumps(data["error"]),
                "duration": duration
            }
            
        result = data.get("result", {})
        tools = result.get("tools", [])
        
        return {
            "status": "connected",
            "version": "unknown", # HTTP MCP doesn't always show version in listTools
            "tools_count": len(tools),
            "duration": duration
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "duration": time.time() - start_time
        }

def test_stdio_server(command: str, args: list[str], env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Test connectivity to an MCP stdio server."""
    start_time = time.time()
    process = None
    try:
        # Spawn the process
        full_env = os.environ.copy()
        if env:
            full_env.update(env)
            
        process = subprocess.Popen(
            [command] + args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=full_env,
            text=True,
            bufsize=1
        )
        
        # MCP Initialize request
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "ostwin-tester",
                    "version": "0.1.0"
                }
            }
        }
        
        # Send initialize request
        process.stdin.write(json.dumps(init_request) + "\n")
        process.stdin.flush()
        
        # Read response (with timeout)
        import select
        
        # Wait up to 30 seconds for stdout (some servers like memory need time to load models)
        ready, _, _ = select.select([process.stdout], [], [], 30)
        
        if not ready:
            # Check if process died
            if process.poll() is not None:
                stderr = process.stderr.read()
                return {
                    "status": "error",
                    "message": "Process exited unexpectedly",
                    "detail": stderr[:200],
                    "duration": time.time() - start_time
                }
            return {
                "status": "error",
                "message": "Timeout waiting for response",
                "duration": time.time() - start_time
            }
            
        response_line = process.stdout.readline()
        if not response_line:
            return {
                "status": "error",
                "message": "Empty response from server",
                "duration": time.time() - start_time
            }
            
        data = json.loads(response_line)
        if "error" in data:
            return {
                "status": "error",
                "message": f"MCP Error: {data['error'].get('message', 'Unknown error')}",
                "detail": json.dumps(data["error"]),
                "duration": time.time() - start_time
            }
            
        result = data.get("result", {})
        server_info = result.get("serverInfo", {})
        
        # Send initialized notification (required by MCP protocol before any requests)
        initialized_notification = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }
        process.stdin.write(json.dumps(initialized_notification) + "\n")
        process.stdin.flush()

        # Now list tools
        list_tools_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        process.stdin.write(json.dumps(list_tools_request) + "\n")
        process.stdin.flush()
        
        ready, _, _ = select.select([process.stdout], [], [], 5)
        if ready:
            response_line = process.stdout.readline()
            data = json.loads(response_line)
            tools = data.get("result", {}).get("tools", [])
            tools_count = len(tools)
        else:
            tools_count = 0
            
        return {
            "status": "connected",
            "name": server_info.get("name", "unknown"),
            "version": server_info.get("version", "unknown"),
            "tools_count": tools_count,
            "duration": time.time() - start_time
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "duration": time.time() - start_time
        }
    finally:
        if process:
            process.terminate()
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                process.kill()

if __name__ == "__main__":
    # Simple CLI for the module itself to test it
    if len(sys.argv) < 2:
        print(json.dumps({"status": "error", "message": "Missing arguments"}))
        sys.exit(1)
        
    cmd_type = sys.argv[1]
    if cmd_type == "http":
        url = sys.argv[2]
        headers = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
        print(json.dumps(test_http_server(url, headers)))
    elif cmd_type == "stdio":
        command = sys.argv[2]
        args = sys.argv[3:]
        print(json.dumps(test_stdio_server(command, args)))
    else:
        print(json.dumps({"status": "error", "message": f"Unknown type: {cmd_type}"}))
