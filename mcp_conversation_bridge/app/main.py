import json
import os
import time
import traceback
import uuid
from typing import Any, Dict, List, Optional

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse



BRIDGE_VERSION = os.getenv("BRIDGE_VERSION", "0.1.7")
DEBUG_ERRORS = os.getenv("DEBUG_ERRORS", "false").strip().lower() in {"1", "true", "yes", "on"}

app = FastAPI(title="ha-mcp-bridge", version=BRIDGE_VERSION)


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip().lower()
    if raw in {"", "null", "none"}:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip().lower()
    if raw in {"", "null", "none"}:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _allowlist() -> Optional[set[str]]:
    raw = os.getenv("TOOL_ALLOWLIST_JSON", "[]").strip()
    if not raw:
        return None
    try:
        values = json.loads(raw)
        if not isinstance(values, list):
            return None
        clean = {str(x).strip() for x in values if str(x).strip()}
        return clean if clean else None
    except json.JSONDecodeError:
        return None


MCP_URL = _required_env("MCP_URL")
UPSTREAM_BASE_URL = _required_env("UPSTREAM_BASE_URL").rstrip("/")
UPSTREAM_API_KEY = os.getenv("UPSTREAM_API_KEY", "").strip()
UPSTREAM_MODEL = _required_env("UPSTREAM_MODEL")
UPSTREAM_TIMEOUT_SECONDS = _env_float("UPSTREAM_TIMEOUT_SECONDS", 120.0)
UPSTREAM_DEFAULT_MAX_TOKENS = _env_int("UPSTREAM_DEFAULT_MAX_TOKENS", 300)
UPSTREAM_NUM_CTX = _env_int("UPSTREAM_NUM_CTX", 0)
MAX_EXPOSED_TOOLS = _env_int("MAX_EXPOSED_TOOLS", 8)
MAX_TOOL_DESCRIPTION_CHARS = _env_int("MAX_TOOL_DESCRIPTION_CHARS", 120)
MAX_MESSAGE_HISTORY = _env_int("MAX_MESSAGE_HISTORY", 6)
MCP_AUTH_HEADER = os.getenv("MCP_AUTH_HEADER", "").strip()
MCP_AUTH_TOKEN = os.getenv("MCP_AUTH_TOKEN", "").strip()
TOOL_ALLOWLIST = _allowlist()

MCP_REQUEST_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
UPSTREAM_REQUEST_TIMEOUT = httpx.Timeout(UPSTREAM_TIMEOUT_SECONDS, connect=10.0)
MAX_TOOL_ROUNDS = 8


def _compact_schema(node: Any) -> Any:
    if isinstance(node, dict):
        compact: Dict[str, Any] = {}
        for key, value in node.items():
            if key in {"description", "title", "examples", "default"}:
                continue
            compact[key] = _compact_schema(value)
        return compact
    if isinstance(node, list):
        return [_compact_schema(item) for item in node]
    return node


def _trim_messages(messages: List[Dict[str, Any]], max_history: int) -> List[Dict[str, Any]]:
    if max_history <= 0 or len(messages) <= max_history:
        return messages

    # Keep newest conversation turns and preserve a leading system message when present.
    system_message = None
    tail = messages
    if messages and messages[0].get("role") == "system":
        system_message = messages[0]
        tail = messages[1:]

    tail = tail[-max_history:]
    if system_message:
        return [system_message, *tail]
    return tail


def _is_context_overflow(detail: str) -> bool:
    text = detail.lower()
    return (
        "exceeds the available context size" in text
        or "exceed_context_size_error" in text
        or "maximum context length" in text
        or "context window" in text
    )


def _parse_sse_json(payload_text: str) -> Dict[str, Any]:
    # MCP servers may reply as text/event-stream; parse last data frame as JSON.
    data_chunks: List[str] = []
    for line in payload_text.splitlines():
        if line.startswith("data:"):
            data_chunks.append(line[5:].strip())

    if not data_chunks:
        raise HTTPException(status_code=502, detail="MCP SSE response missing data frames")

    raw = data_chunks[-1]
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail="MCP SSE data is not valid JSON") from exc

    if not isinstance(parsed, dict):
        raise HTTPException(status_code=502, detail="MCP SSE payload is not a JSON object")

    return parsed


async def _mcp_rpc(method: str, params: Dict[str, Any]) -> Dict[str, Any]:
    payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": method,
        "params": params,
    }
    headers: Dict[str, str] = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if MCP_AUTH_HEADER and MCP_AUTH_TOKEN:
        headers[MCP_AUTH_HEADER] = MCP_AUTH_TOKEN

    try:
        async with httpx.AsyncClient(timeout=MCP_REQUEST_TIMEOUT) as client:
            response = await client.post(MCP_URL, json=payload, headers=headers)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"MCP transport error: {type(exc).__name__}: {exc}") from exc

    if response.status_code >= 400:
        raise HTTPException(
            status_code=502,
            detail=f"MCP request failed with HTTP {response.status_code}",
        )

    content_type = response.headers.get("content-type", "").lower()
    if "text/event-stream" in content_type:
        data = _parse_sse_json(response.text)
    else:
        try:
            data = response.json()
        except ValueError as exc:
            raise HTTPException(status_code=502, detail="MCP response is not valid JSON") from exc

    if "error" in data:
        err = data["error"]
        code = err.get("code", "unknown")
        message = err.get("message", "unknown error")
        raise HTTPException(status_code=502, detail=f"MCP error {code}: {message}")

    return data.get("result", {})


async def _list_tools() -> List[Dict[str, Any]]:
    result = await _mcp_rpc("tools/list", {})
    raw_tools = result.get("tools", [])

    tools: List[Dict[str, Any]] = []
    for tool in raw_tools:
        name = str(tool.get("name", "")).strip()
        if not name:
            continue
        if TOOL_ALLOWLIST and name not in TOOL_ALLOWLIST:
            continue

        schema = tool.get("inputSchema")
        if not isinstance(schema, dict):
            schema = {"type": "object", "properties": {}}
        schema = _compact_schema(schema)

        description = str(tool.get("description", "")).strip()
        if MAX_TOOL_DESCRIPTION_CHARS > 0 and len(description) > MAX_TOOL_DESCRIPTION_CHARS:
            description = description[:MAX_TOOL_DESCRIPTION_CHARS].rstrip() + "..."

        tools.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": schema,
                },
            }
        )

    if MAX_EXPOSED_TOOLS > 0:
        return tools[:MAX_EXPOSED_TOOLS]

    return tools


async def _call_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    if TOOL_ALLOWLIST and name not in TOOL_ALLOWLIST:
        raise HTTPException(status_code=403, detail=f"Tool not allowed: {name}")

    # Compatibility: different MCP servers expect either "arguments" or "input".
    try:
        return await _mcp_rpc("tools/call", {"name": name, "arguments": arguments})
    except HTTPException:
        return await _mcp_rpc("tools/call", {"name": name, "input": arguments})


async def _upstream_chat(payload: Dict[str, Any]) -> Dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    if UPSTREAM_API_KEY:
        headers["Authorization"] = f"Bearer {UPSTREAM_API_KEY}"
    url = f"{UPSTREAM_BASE_URL}/chat/completions"

    try:
        async with httpx.AsyncClient(timeout=UPSTREAM_REQUEST_TIMEOUT) as client:
            response = await client.post(url, headers=headers, json=payload)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Upstream LLM transport error: {type(exc).__name__}: {exc}") from exc

    if response.status_code >= 400:
        msg = response.text
        raise HTTPException(status_code=502, detail=f"Upstream LLM HTTP {response.status_code}: {msg}")

    try:
        return response.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="Upstream LLM response is not valid JSON") from exc


async def _check_mcp_dependency() -> Dict[str, Any]:
    started = time.perf_counter()
    try:
        result = await _mcp_rpc("tools/list", {})
        tools = result.get("tools", []) if isinstance(result, dict) else []
        return {
            "ok": True,
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            "tool_count": len(tools) if isinstance(tools, list) else 0,
        }
    except HTTPException as exc:
        return {
            "ok": False,
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            "error": str(exc.detail),
        }


async def _check_upstream_dependency() -> Dict[str, Any]:
    started = time.perf_counter()
    headers = {"Content-Type": "application/json"}
    if UPSTREAM_API_KEY:
        headers["Authorization"] = f"Bearer {UPSTREAM_API_KEY}"

    url = f"{UPSTREAM_BASE_URL}/models"
    timeout = httpx.Timeout(12.0, connect=5.0)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, headers=headers)
    except httpx.HTTPError as exc:
        return {
            "ok": False,
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            "error": f"Upstream transport error: {type(exc).__name__}: {exc}",
        }

    if response.status_code >= 400:
        return {
            "ok": False,
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            "error": f"Upstream HTTP {response.status_code}",
        }

    model_count = 0
    try:
        payload = response.json()
        data = payload.get("data", []) if isinstance(payload, dict) else []
        if isinstance(data, list):
            model_count = len(data)
    except ValueError:
        pass

    return {
        "ok": True,
        "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        "model_count": model_count,
    }


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    if DEBUG_ERRORS:
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_server_error",
                "exception_type": type(exc).__name__,
                "message": str(exc),
                "traceback": traceback.format_exc(),
                "version": BRIDGE_VERSION,
            },
        )

    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "message": "Unexpected error. Enable DEBUG_ERRORS for details.",
            "version": BRIDGE_VERSION,
        },
    )


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok", "version": BRIDGE_VERSION}


@app.get("/health/deps")
async def health_deps() -> Dict[str, Any]:
    mcp = await _check_mcp_dependency()
    llm = await _check_upstream_dependency()
    ok = bool(mcp.get("ok") and llm.get("ok"))

    return {
        "status": "ok" if ok else "degraded",
        "version": BRIDGE_VERSION,
        "dependencies": {
            "mcp": mcp,
            "llm": llm,
        },
    }


@app.get("/version")
async def version() -> Dict[str, str]:
    return {"version": BRIDGE_VERSION}


@app.get("/v1/models")
async def models() -> Dict[str, Any]:
    return {
        "object": "list",
        "data": [
            {
                "id": UPSTREAM_MODEL,
                "object": "model",
                "owned_by": "ha-mcp-bridge",
            }
        ],
    }


@app.get("/v1/chat/completions")
async def chat_completions_get_hint() -> Dict[str, str]:
    return {
        "detail": "Use POST /v1/chat/completions with JSON body.",
    }


@app.get("/chat/completions")
async def chat_completions_get_hint_alias() -> Dict[str, str]:
    return {
        "detail": "Use POST /chat/completions with JSON body.",
    }


@app.post("/v1/chat/completions")
async def chat_completions(request: Request) -> JSONResponse:
    body = await request.json()

    if body.get("stream"):
        raise HTTPException(status_code=400, detail="stream=true not supported")

    incoming_messages = body.get("messages")
    if not isinstance(incoming_messages, list) or not incoming_messages:
        raise HTTPException(status_code=400, detail="messages must be a non-empty list")

    tools = await _list_tools()
    conversation = _trim_messages(list(incoming_messages), MAX_MESSAGE_HISTORY)

    model = body.get("model") or UPSTREAM_MODEL

    passthrough_fields = [
        "temperature",
        "top_p",
        "presence_penalty",
        "frequency_penalty",
        "response_format",
    ]

    for _ in range(MAX_TOOL_ROUNDS):
        llm_payload: Dict[str, Any] = {
            "model": model,
            "messages": conversation,
            "tools": tools,
            "tool_choice": "auto",
        }
        for field in passthrough_fields:
            if field in body:
                llm_payload[field] = body[field]

        if "max_tokens" in body:
            llm_payload["max_tokens"] = body["max_tokens"]
        elif UPSTREAM_DEFAULT_MAX_TOKENS > 0:
            llm_payload["max_tokens"] = UPSTREAM_DEFAULT_MAX_TOKENS

        if UPSTREAM_NUM_CTX > 0:
            llm_payload["options"] = {"num_ctx": UPSTREAM_NUM_CTX}
            llm_payload["n_ctx"] = UPSTREAM_NUM_CTX

        try:
            llm_response = await _upstream_chat(llm_payload)
        except HTTPException as exc:
            detail_text = str(exc.detail)
            if _is_context_overflow(detail_text):
                # First fallback: progressively reduce exposed tools.
                if len(tools) > 1:
                    tools = tools[: max(1, len(tools) // 2)]
                    continue
                # Second fallback: drop remaining tools.
                if tools:
                    tools = []
                    continue
                # Second fallback: aggressively trim history and retry.
                if len(conversation) > 2:
                    trimmed = max(2, len(conversation) // 2)
                    conversation = _trim_messages(conversation, trimmed)
                    continue
            raise

        choices = llm_response.get("choices", [])
        if not choices:
            raise HTTPException(status_code=502, detail="Upstream LLM returned no choices")

        message = choices[0].get("message", {})
        tool_calls = message.get("tool_calls") or []

        if not tool_calls:
            return JSONResponse(content=llm_response)

        conversation.append(
            {
                "role": "assistant",
                "content": message.get("content", ""),
                "tool_calls": tool_calls,
            }
        )

        for tc in tool_calls:
            fn = tc.get("function", {})
            tool_name = fn.get("name", "")
            tool_call_id = tc.get("id", "")
            raw_args = fn.get("arguments") or "{}"

            try:
                parsed_args = json.loads(raw_args)
                if not isinstance(parsed_args, dict):
                    parsed_args = {}
            except json.JSONDecodeError:
                parsed_args = {}

            tool_result = await _call_tool(tool_name, parsed_args)

            conversation.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "name": tool_name,
                    "content": json.dumps(tool_result),
                }
            )

    raise HTTPException(status_code=502, detail="Exceeded max tool round trips")


@app.post("/chat/completions")
async def chat_completions_alias(request: Request) -> JSONResponse:
    return await chat_completions(request)


@app.post("/v1/completions")
async def legacy_completions(request: Request) -> JSONResponse:
    body = await request.json()
    prompt = body.get("prompt", "")
    model = body.get("model") or UPSTREAM_MODEL

    chat_body: Dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": str(prompt)}],
        "stream": False,
    }

    for field in ["temperature", "top_p", "max_tokens"]:
        if field in body:
            chat_body[field] = body[field]

    class _LegacyRequest:
        def __init__(self, payload: Dict[str, Any]) -> None:
            self._payload = payload

        async def json(self) -> Dict[str, Any]:
            return self._payload

    chat_response = await chat_completions(_LegacyRequest(chat_body))
    chat_payload = json.loads(chat_response.body.decode("utf-8"))
    choices = chat_payload.get("choices", [])
    content = ""
    if choices:
        content = choices[0].get("message", {}).get("content", "")

    completion_payload = {
        "id": chat_payload.get("id", f"cmpl-{uuid.uuid4()}"),
        "object": "text_completion",
        "created": chat_payload.get("created"),
        "model": model,
        "choices": [
            {
                "text": content,
                "index": 0,
                "finish_reason": "stop",
            }
        ],
    }

    return JSONResponse(content=completion_payload)
