## Integration with Agentic Orchestration PoC

This Gateway is **integrated** with [agentic-orchestration-poc](https://github.com/realrvs/agentic-orchestration-poc):

- BPMN process calls MCP Gateway via JSON-RPC 2.0
- Worker sends X-Agent-SVID: `spiffe://company.ru/agents/llm_agent_v1`
- Audit log confirms: `publish_notice` ALLOWED, latency 45 ms
- Full cycle: BPMN → LLM → Policy → MCP Gateway → EIS → End

