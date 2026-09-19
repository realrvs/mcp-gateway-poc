---

## Integration with Agentic Orchestration PoC

Gateway **интегрирован** с [agentic-orchestration-poc](https://github.com/realrvs/agentic-orchestration-poc):

- BPMN-процесс вызывает MCP Gateway через JSON-RPC 2.0
- Worker передаёт `X-Agent-SVID: spiffe://company.ru/agents/llm_agent_v1`
- Audit log фиксирует `publish_notice` ALLOWED (latency 45 ms)
- Полный цикл: BPMN → LLM → Policy → MCP Gateway → EIS → End

**Verified Instance:** `EIS-2026-MOSCOW-5679`

### Cross-Repo Flow
agentic-orchestration-poc (worker.py)
↓ POST /mcp/messages + X-Agent-SVID
mcp-gateway-poc (mcp_gateway.py)
↓ POST /call/publish_notice
eis-mcp-server (mock)
↓ SUCCESS
Audit log (PostgreSQL)
