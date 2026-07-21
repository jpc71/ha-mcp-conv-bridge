# MCP Conversation Bridge

This add-on exposes an OpenAI-compatible endpoint for Home Assistant conversation integrations and executes tool calls through a Home Assistant MCP endpoint.

## Requirements

- Home Assistant OS or Home Assistant Supervised
- Reachable MCP endpoint URL
- Upstream LLM provider with OpenAI-compatible Chat Completions API (cloud or local)

## Configuration

- mcp_url: Full MCP endpoint URL
- mcp_auth_header: Optional custom auth header name for MCP
- mcp_auth_token: Optional token value for MCP auth header
- upstream_base_url: OpenAI-compatible base URL ending with /v1
- upstream_api_key: Optional upstream API key
- upstream_model: Upstream model id
- upstream_timeout_seconds: Upstream LLM read timeout in seconds (default 120)
- upstream_default_max_tokens: Default `max_tokens` sent upstream when caller does not provide one (default 300)
- debug_errors: Return structured 500 payloads with exception text and traceback
- tool_allowlist: Optional list of MCP tool names to permit

## Local-only setup example (Ollama on Docker host)

- upstream_base_url: `http://192.168.1.12:11434/v1`
- upstream_api_key: empty
- upstream_model: `qwen2.5:3b`
- HA mcp_url: `http://192.168.1.11:9583/private_slugslugslugslug`

## Endpoint exposed by add-on

- [http://homeassistant.local:8099/v1/chat/completions](http://homeassistant.local:8099/v1/chat/completions)
- [http://homeassistant.local:8099/v1/models](http://homeassistant.local:8099/v1/models)
- [http://homeassistant.local:8099/health](http://homeassistant.local:8099/health)
- [http://homeassistant.local:8099/health/deps](http://homeassistant.local:8099/health/deps)
- [http://homeassistant.local:8099/version](http://homeassistant.local:8099/version)

## Version check

Use these to confirm correct deployment after restart:

```bash
curl -sS http://HOME_ASSISTANT_IP:8099/health
curl -sS http://HOME_ASSISTANT_IP:8099/health/deps
curl -sS http://HOME_ASSISTANT_IP:8099/version
```

Expected payload:

```json
{"status":"ok","version":"0.1.8"}
```

`/health/deps` returns MCP and upstream LLM dependency status with latency and error details:

```json
{
  "status": "ok",
  "version": "0.1.8",
  "dependencies": {
    "mcp": {"ok": true, "latency_ms": 54.2, "tool_count": 34},
    "llm": {"ok": true, "latency_ms": 22.8, "model_count": 3}
  }
}
```

If either dependency fails, `status` is `degraded` and `error` is included per dependency.

## Debug mode

Set `debug_errors: true` temporarily when diagnosing failures.

When enabled, unexpected server errors return structured JSON:

```json
{
  "error": "internal_server_error",
  "exception_type": "ConnectError",
  "message": "...",
  "traceback": "...",
  "version": "0.1.8"
}
```

Set back to `false` after debugging.

## Reliability tuning

- If chat intermittently fails with `ReadTimeout`, increase `upstream_timeout_seconds`.
- Start with `120`, then raise to `180` if needed.
- For constrained hosts, prefer `upstream_model=qwen2.5:3b`.
- Set `upstream_default_max_tokens` to `200-300` on constrained hosts.
- Keep `tool_allowlist` narrow to reduce prompt/tool overhead.

## Versioning rule

- Update `BRIDGE_VERSION` in `app/main.py` for each release.
- Health and version endpoints must match that value.
- Keep add-on deploys and docs in sync.

## Connect in Home Assistant

1. Install and start add-on.
2. In add-on configuration, set mcp_url to your private MCP URL.
3. Set upstream provider fields.
4. Save and restart add-on.
5. Configure your conversation integration to use add-on URL as OpenAI-compatible endpoint.
6. Select this conversation agent in Assist pipeline.

## Security

- Keep mcp_url private token secret.
- Keep tool_allowlist minimal.
- Do not expose add-on port outside trusted LAN.
