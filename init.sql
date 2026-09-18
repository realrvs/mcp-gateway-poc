CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    agent_svid VARCHAR(255) NOT NULL,
    tool_name VARCHAR(255) NOT NULL,
    decision VARCHAR(50) NOT NULL,
    reasoning TEXT,
    latency_ms INTEGER
);

CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_svid ON audit_log(agent_svid);
