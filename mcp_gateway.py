"""
Enterprise MCP Gateway.

Единая точка входа для AI-агентов при вызове legacy-систем
через Model Context Protocol (MCP).

Функции:
- SSE-транспорт (соответствует спецификации Anthropic MCP)
- JSON-RPC 2.0 обработка
- Проксирование запросов к upstream MCP-серверам
- RBAC через X-Agent-SVID
- Append-only audit log в PostgreSQL

Порт: 8000
"""

import json
import os
import time
from contextlib import asynccontextmanager

import asyncpg
import httpx
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse


# ─── Configuration ────────────────────────────────────────────────

DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://mcp_user:mcp_password@localhost:5432/mcp_audit",
)
EIS_URL = os.getenv("EIS_SERVER_URL", "http://localhost:8001")

ALLOWED_SVIDS = {
    "spiffe://cluster.local/ns/default/sa/langgraph-agent",
    "spiffe://company.ru/agents/llm_agent_v1",
}

DEFAULT_SVID = "spiffe://cluster.local/ns/default/sa/langgraph-agent"


# ─── Lifespan ─────────────────────────────────────────────────────

db_pool: asyncpg.Pool | None = None
http_client: httpx.AsyncClient | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_pool, http_client

    # Startup
    db_pool = await asyncpg.create_pool(DB_URL, min_size=2, max_size=10)
    http_client = httpx.AsyncClient(timeout=30.0)

    print(f"[gateway] Connected to PostgreSQL")
    print(f"[gateway] Upstream EIS: {EIS_URL}")
    print(f"[gateway] Ready to serve MCP requests on port 8000")

    yield

    # Shutdown
    if http_client:
        await http_client.aclose()
    if db_pool:
        await db_pool.close()
    print("[gateway] Shutdown complete")


app = FastAPI(title="Enterprise MCP Gateway", lifespan=lifespan)


# ─── Audit log ────────────────────────────────────────────────────

async def log_audit(
    svid: str,
    tool: str,
    decision: str,
    reason: str,
    latency_ms: int,
) -> None:
    """Append-only запись в audit log."""
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO audit_log
                (agent_svid, tool_name, decision, reasoning, latency_ms)
            VALUES ($1, $2, $3, $4, $5)
            """,
            svid,
            tool,
            decision,
            reason,
            latency_ms,
        )


# ─── Schemas ──────────────────────────────────────────────────────

class JSONRPCRequest(BaseModel):
    jsonrpc: str = "2.0"
    method: str
    params: dict = {}
    id: int | str


# ─── SSE endpoint (MCP transport) ─────────────────────────────────

@app.get("/mcp/sse")
async def mcp_sse(request: Request):
    """
    SSE endpoint для MCP-транспорта.

    Согласно спецификации Anthropic MCP, клиент подключается
    к SSE, получает URL для отправки сообщений, а затем
    отправляет JSON-RPC запросы на этот URL.
    """
    async def event_generator():
        # Первое событие — endpoint для отправки сообщений
        yield {
            "event": "endpoint",
            "data": "/mcp/messages",
        }

        # Держим соединение открытым
        while True:
            if await request.is_disconnected():
                break

    return EventSourceResponse(event_generator())


# ─── JSON-RPC endpoint (MCP transport) ────────────────────────────

@app.post("/mcp/messages")
async def handle_message(rpc: JSONRPCRequest, request: Request):
    """
    Обработчик JSON-RPC 2.0 сообщений.

    Методы:
    - initialize — handshake (упрощён)
    - tools/list — список tools от upstream MCP-серверов
    - tools/call — вызов tool (проксирование в upstream)
    """
    start_time = time.time()

    # RBAC: извлечь SVID из заголовка
    agent_svid = request.headers.get("X-Agent-SVID", DEFAULT_SVID)

    # ─── initialize ────────────────────────────────────────────────
    if rpc.method == "initialize":
        latency = int((time.time() - start_time) * 1000)
        await log_audit(agent_svid, "initialize", "ALLOWED", "Handshake", latency)
        return {
            "jsonrpc": "2.0",
            "id": rpc.id,
            "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "enterprise-mcp-gateway", "version": "0.1.0"},
                "capabilities": {"tools": {}},
            },
        }

    # ─── RBAC check ────────────────────────────────────────────────
    if agent_svid not in ALLOWED_SVIDS:
        latency = int((time.time() - start_time) * 1000)
        await log_audit(
            agent_svid,
            rpc.method,
            "REJECTED",
            f"SVID not in allow-list",
            latency,
        )
        raise HTTPException(status_code=403, detail="Agent SVID not allowed")

    # ─── tools/list ────────────────────────────────────────────────
    if rpc.method == "tools/list":
        resp = await http_client.get(f"{EIS_URL}/tools")
        resp.raise_for_status()
        tools = resp.json()

        latency = int((time.time() - start_time) * 1000)
        await log_audit(agent_svid, "tools/list", "ALLOWED", "Fetched tools", latency)

        return {
            "jsonrpc": "2.0",
            "id": rpc.id,
            "result": {"tools": tools},
        }

    # ─── tools/call ────────────────────────────────────────────────
    if rpc.method == "tools/call":
        tool_name = rpc.params.get("name")
        arguments = rpc.params.get("arguments", {})

        if tool_name != "publish_notice":
            latency = int((time.time() - start_time) * 1000)
            await log_audit(
                agent_svid,
                tool_name or "unknown",
                "REJECTED",
                "Tool not in allow-list",
                latency,
            )
            raise HTTPException(status_code=404, detail="Tool not supported")

        # Проксируем в EIS MCP Server
        resp = await http_client.post(
            f"{EIS_URL}/call/publish_notice",
            json=arguments,
        )
        result_data = resp.json()

        latency = int((time.time() - start_time) * 1000)
        await log_audit(
            agent_svid,
            tool_name,
            "ALLOWED",
            "Proxied to EIS MCP Server",
            latency,
        )

        return {
            "jsonrpc": "2.0",
            "id": rpc.id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(result_data, ensure_ascii=False),
                    }
                ]
            },
        }

    # ─── Unknown method ───────────────────────────────────────────
    latency = int((time.time() - start_time) * 1000)
    await log_audit(agent_svid, rpc.method, "REJECTED", "Unknown method", latency)
    raise HTTPException(status_code=400, detail="Method not supported")


# ─── Health ───────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "mcp-gateway",
        "upstream": EIS_URL,
    }
