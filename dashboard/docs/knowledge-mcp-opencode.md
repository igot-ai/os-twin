# Connecting opencode to the Ostwin Knowledge MCP server

The dashboard exposes a streamable-HTTP MCP server at **`/mcp/`** (note
the trailing slash) that provides 7 tools for graph-RAG knowledge
management. opencode (and any other MCP-compatible client) can connect
and call them as native tools.

## 1) Configuration

Add this block to `~/.config/opencode/opencode.json` (or to your project's
`.opencode/opencode.json`):

```json
{
  "mcp": {
    "ostwin-knowledge": {
      "type": "remote",
      "url": "http://localhost:3366/mcp/",
      "headers": {
        "Authorization": "Bearer ${env:OSTWIN_API_KEY}"
      }
    }
  }
}
```

> The trailing slash is required — `http://localhost:3366/mcp` (no slash)
> returns a 404 because the FastAPI mount point is `/mcp/...`.

Then in your shell:

```bash
export OSTWIN_API_KEY="your-key-from-~/.ostwin/.env"
opencode mcp list   # should list ostwin-knowledge with 7 tools
```

If the dashboard is in **dev mode** (`OSTWIN_DEV_MODE=1`) OR if
`OSTWIN_API_KEY` is unset on the dashboard side, the `Authorization`
header is not enforced — you can omit the `headers` block entirely.

## 2) Available tools

| Tool | Purpose |
|------|---------|
| `knowledge_list_namespaces` | List every namespace + its stats |
| `knowledge_create_namespace` | Create a new namespace (also auto-created on import) |
| `knowledge_delete_namespace` | Permanently delete a namespace and its data |
| `knowledge_import_folder` | Background-import an absolute folder path into a namespace |
| `knowledge_get_import_status` | Poll a job by `job_id` to track ingestion progress |
| `knowledge_query` | Query a namespace (`raw` / `graph` / `summarized` modes) |
| `knowledge_get_graph` | Get the entity-relation graph for visualisation |

Every tool returns a JSON object. On failure the response is
`{"error": "<message>", "code": "<ERROR_CODE>"}` — never an exception or
HTTP 5xx. Codes you may see:

| Code | When |
|------|------|
| `INVALID_NAMESPACE_ID` | Namespace name doesn't match `^[a-z0-9][a-z0-9_-]{0,63}$` |
| `NAMESPACE_EXISTS` | Trying to create a namespace that already exists |
| `NAMESPACE_NOT_FOUND` | Querying / get_graph against an unknown namespace |
| `INVALID_FOLDER_PATH` | `folder_path` is relative |
| `FOLDER_NOT_FOUND` | `folder_path` doesn't exist on disk |
| `NOT_A_DIRECTORY` | `folder_path` exists but is a file |
| `JOB_NOT_FOUND` | `job_id` doesn't match any submitted job |
| `BAD_REQUEST` | Invalid `mode` for `knowledge_query` (must be `raw`/`graph`/`summarized`) |
| `INTERNAL_ERROR` | Anything else — check dashboard logs |

## 3) Usage notes

- **Image files** (PNG / JPG / GIF / BMP / TIFF / WEBP) are walked as
  part of `knowledge_import_folder` but require `ANTHROPIC_API_KEY` in
  the dashboard environment for vision-based OCR. Without the key,
  images are skipped silently (one warning per file in the dashboard log).
- **Imports are background jobs** — `knowledge_import_folder` returns a
  `job_id` immediately; poll `knowledge_get_import_status` until
  `state` is `completed` (or `failed` / `cancelled` / `interrupted`).
- **`knowledge_query` mode `summarized`** requires `ANTHROPIC_API_KEY`.
  Without it the response includes `warnings: ["llm_unavailable"]` and
  `answer: null` — chunks are still returned, no exception is raised.
- **`folder_path` MUST be absolute**. Relative paths are rejected with
  code `INVALID_FOLDER_PATH`.

## 4) Verifying the connection

After configuring `opencode.json`, run:

```bash
opencode mcp list
# expected output: ostwin-knowledge   7 tools   http://localhost:3366/mcp/
```

Or hand-poke the endpoint to confirm it's reachable:

```bash
# Real MCP handshake — should return HTTP 200 with a JSON-RPC result body.
curl -i -X POST http://localhost:3366/mcp/ \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"curl","version":"0.1"}}}'
```

## 5) Example: end-to-end import + query (via opencode)

Once registered, opencode (or any MCP client) can chain calls like:

```text
1. knowledge_create_namespace(name="my_docs", language="English")
2. knowledge_import_folder(namespace="my_docs", folder_path="/Users/me/docs")
3. knowledge_get_import_status(namespace="my_docs", job_id="<uuid>")  # poll
4. knowledge_query(namespace="my_docs", query="how do I deploy?", mode="summarized")
```

The `summarized` answer comes back with citations pointing to the
original files, so the LLM client can present a sourced response.
