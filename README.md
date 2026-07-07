# HA MCP Conversation Bridge Add-on Repository

This repository is a Home Assistant add-on repository containing:

- `mcp_conversation_bridge`

The add-on exposes an OpenAI-compatible API endpoint and forwards tool calls to a Home Assistant MCP endpoint.

## Add to Home Assistant Add-on Store

1. Push this repository to GitHub.
2. In Home Assistant: **Settings -> Add-ons -> Add-on Store**.
3. Open the menu (top-right) -> **Repositories**.
4. Add your repository URL:
   - `https://github.com/<your-user>/ha-mcp-conv-bridge`
5. Refresh Add-on Store.
6. Install **MCP Conversation Bridge**.

## Security Notes

- Do not commit private MCP URLs or tokens.
- Keep `mcp_auth_token` and `upstream_api_key` set in HA add-on options only.
- Keep debug mode disabled in normal operation.
