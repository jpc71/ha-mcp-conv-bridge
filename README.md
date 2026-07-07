# HA MCP Conversation Bridge Add-on

This repository contains a custom Home Assistant add-on that exposes an OpenAI-compatible chat endpoint and executes MCP tools through a Home Assistant MCP URL.

## Supports

- Home Assistant OS
- Home Assistant Supervised

## Does not support

- Home Assistant Container (no add-on store)
- Home Assistant Core in venv

## Add-on folder

- mcp_conversation_bridge

## What it does

- Receives chat completion requests from Home Assistant conversation integration.
- Uses upstream LLM provider (cloud or local OpenAI-compatible endpoint).
- Pulls available tools from MCP endpoint.
- Executes selected tool calls through MCP.
- Returns final assistant answer.

## Local-only recommendation

- Run this add-on in Home Assistant Supervised.
- Run Ollama in Docker on robust LAN host.
- Point add-on `upstream_base_url` to `http://<host-ip>:11434/v1`.
- Keep `upstream_api_key` empty for Ollama.
