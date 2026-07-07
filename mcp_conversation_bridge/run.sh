#!/usr/bin/with-contenv bashio
set -euo pipefail

export MCP_URL="$(bashio::config 'mcp_url')"
export MCP_AUTH_HEADER="$(bashio::config 'mcp_auth_header')"
export MCP_AUTH_TOKEN="$(bashio::config 'mcp_auth_token')"
export UPSTREAM_BASE_URL="$(bashio::config 'upstream_base_url')"
export UPSTREAM_API_KEY="$(bashio::config 'upstream_api_key')"
export UPSTREAM_MODEL="$(bashio::config 'upstream_model')"
export UPSTREAM_TIMEOUT_SECONDS="$(bashio::config 'upstream_timeout_seconds')"
export UPSTREAM_DEFAULT_MAX_TOKENS="$(bashio::config 'upstream_default_max_tokens')"
export UPSTREAM_NUM_CTX="$(bashio::config 'upstream_num_ctx')"
export MAX_EXPOSED_TOOLS="$(bashio::config 'max_exposed_tools')"
export MAX_TOOL_DESCRIPTION_CHARS="$(bashio::config 'max_tool_description_chars')"
export MAX_MESSAGE_HISTORY="$(bashio::config 'max_message_history')"
export DEBUG_ERRORS="$(bashio::config 'debug_errors')"
export TOOL_ALLOWLIST_JSON="$(bashio::config 'tool_allowlist')"
export BRIDGE_VERSION="0.1.7"

bashio::log.info "Starting MCP Conversation Bridge v${BRIDGE_VERSION} on 0.0.0.0:8099"
exec uvicorn app.main:app --host 0.0.0.0 --port 8099
