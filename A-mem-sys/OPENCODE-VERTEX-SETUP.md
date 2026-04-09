# Setup Guide: OpenCode with Vertex AI Partner Models (e.g. `zai-org/glm-5-maas`)

This guide explains how to configure OpenCode to use Vertex AI partner models such as `zai-org/glm-5-maas`.

## Prerequisites

1. Google Cloud project with Vertex AI API enabled
2. Application Default Credentials (ADC) — user credentials, **not** a service account key

## Step 1: Authenticate with ADC

```bash
gcloud auth application-default login --project igot-studio
```

This creates `~/.config/gcloud/application_default_credentials.json` with `authorized_user` type credentials using a refresh token.

Do **not** use `GOOGLE_APPLICATION_CREDENTIALS` pointing to a service account key. OpenCode's partner model auth has a bug where it creates `GoogleAuth` without OAuth scopes, which breaks the JWT assertion flow used by service accounts.

## Step 2: Set the ADC quota project

```bash
gcloud auth application-default set-quota-project igot-studio
```

## Step 3: Export environment variables

Add to `~/.zshrc`:

```bash
export GOOGLE_CLOUD_PROJECT=igot-studio
export GOOGLE_VERTEX_LOCATION=global
```

* `GOOGLE_CLOUD_PROJECT` - tells OpenCode which GCP project to use
* `GOOGLE_VERTEX_LOCATION=global` - critical - partner models (MaaS) are only available in the `global` region; OpenCode defaults to `us-central1`, which fails with `FAILED_PRECONDITION`

## Step 4: Make sure these are **not** set

```bash
# Do NOT export these:
# GOOGLE_APPLICATION_CREDENTIALS  → causes invalid_scope error
# VERTEX_ACCESS_TOKEN             → not needed, OpenCode handles tokens via ADC
# GOOGLE_CLOUD_LOCATION           → conflicts; use GOOGLE_VERTEX_LOCATION instead
```

## Verify

```bash
opencode run "say hello"
```

## Key Takeaways

| Issue | Cause | Fix |
|-------|-------|-----|
| `invalid_scope` | Service account key + no OAuth scopes in OpenCode's partner model auth | Use ADC (`authorized_user`) instead of service account key |
| `not available in region us-central1` | Default region is wrong for MaaS models | Set `GOOGLE_VERTEX_LOCATION=global` |
| `Failed to convert project number` | Cloud Resource Manager API not enabled | Non-fatal warning; can ignore or enable CRM API on the project |

## Project-Specific Notes

### Memory MCP with OpenCode

After setup, the memory MCP server runs through opencode automatically because the merged `mcp-builtin.json` and `mcp-config.json` now point to:

```
{env:HOME}/.ostwin/A-mem-sys/mcp_server.py
```

with environment:
```json
{
  "AGENT_OS_ROOT": "{env:AGENT_OS_PROJECT_DIR}",
  "MEMORY_PERSIST_DIR": "./.memory",
  "GOOGLE_API_KEY": "{env:GOOGLE_API_KEY}"
}
```

OpenCode resolves `{env:VAR}` syntax natively. After running `ostwin init` in a project, the project's `.agents/mcp/config.json` will contain the resolved memory server pointing to the user's `.ostwin/A-mem-sys/mcp_server.py`.

### Note on the deepagents-cli patch

If you're switching fully to opencode, the `~/os-twin/A-mem-sys/patches/patch-deepagents-mcp.sh` patch is no longer needed. It only fixes a bug in deepagents-cli's MCP session handling, which doesn't affect opencode.

Keep the patch script around in case you need to fall back to deepagents-cli for compatibility testing.
