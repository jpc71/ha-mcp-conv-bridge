# MCP Conversation Bridge

This add-on exposes an OpenAI-compatible endpoint for Home Assistant conversation integrations and executes tool calls through a Home Assistant MCP endpoint.

## Requirements

- Home Assistant OS or Home Assistant Supervised
- Reachable MCP endpoint URL
- Upstream LLM provider with OpenAI-compatible Chat Completions API

## Configuration

- `mcp_url`: Full MCP endpoint URL
- `mcp_auth_header`: Optional auth header name for MCP
- `mcp_auth_token`: Optional token for MCP auth header
- `upstream_base_url`: OpenAI-compatible base URL ending with `/v1`
- `upstream_api_key`: Optional upstream API key
- `upstream_model`: Upstream model id
- `upstream_timeout_seconds`: Upstream timeout seconds
- `upstream_default_max_tokens`: Default max tokens sent upstream
- `max_exposed_tools`: Max number of tools exposed to LLM
- `max_tool_description_chars`: Max chars per tool description
- `max_message_history`: Max retained messages before trimming
- `debug_errors`: Return structured 500 payloads when true
- `tool_allowlist`: Optional list of MCP tool names to permit

## Endpoint Exposed by Add-on

- `http://homeassistant.local:8099/v1/chat/completions`
- `http://homeassistant.local:8099/v1/models`
- `http://homeassistant.local:8099/health`
- `http://homeassistant.local:8099/health/deps`
- `http://homeassistant.local:8099/version`

## Version Check

```bash
curl -sS http://HOME_ASSISTANT_IP:8099/health
curl -sS http://HOME_ASSISTANT_IP:8099/health/deps
curl -sS http://HOME_ASSISTANT_IP:8099/version
```

Expected:

```json
{"status":"ok","version":"0.1.5"}
```

## Security

- Keep MCP URL/token private.
- Keep `tool_allowlist` minimal.
- Do not expose add-on port outside trusted LAN.
