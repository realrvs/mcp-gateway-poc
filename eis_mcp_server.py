"""
Mock EIS MCP Server.

Имитирует внешнюю систему ЕИС (Единая информационная система в сфере закупок).
Предоставляет tools для публикации извещений.

Порт: 8001
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


app = FastAPI(title="EIS MCP Server (Mock)")


# ─── Schemas ──────────────────────────────────────────────────────

class PublishNoticeRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    amount: float = Field(..., gt=0)
    region: str = Field(..., min_length=2, max_length=50)


# ─── Tools registry ───────────────────────────────────────────────

TOOLS = [
    {
        "name": "publish_notice",
        "description": "Публикация извещения о закупке в ЕИС",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Название закупки",
                },
                "amount": {
                    "type": "number",
                    "description": "Сумма в рублях",
                },
                "region": {
                    "type": "string",
                    "description": "Регион закупки",
                },
            },
            "required": ["title", "amount", "region"],
        },
    },
]


# ─── Endpoints ────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "eis-mcp-server"}


@app.get("/tools")
async def list_tools():
    """Вернуть список доступных tools."""
    return TOOLS


@app.post("/call/publish_notice")
async def publish_notice(payload: PublishNoticeRequest):
    """
    Mock-реализация публикации извещения.

    В реальной системе здесь был бы SOAP-вызов к ЕИС
    с сертификатом и подписью.
    """
    if payload.amount > 100_000_000:
        raise HTTPException(
            status_code=400,
            detail="Amount exceeds maximum allowed (100M RUB)",
        )

    return {
        "status": "SUCCESS",
        "notice_id": f"EIS-2026-{payload.region.upper()}-{abs(hash(payload.title)) % 10000:04d}",
        "message": (
            f"Закупка '{payload.title}' на сумму {payload.amount:,.2f} руб. "
            f"в регионе {payload.region} успешно зарегистрирована."
        ),
    }
