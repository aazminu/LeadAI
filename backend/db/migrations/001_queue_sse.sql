ALTER TYPE leadstatus ADD VALUE IF NOT EXISTS 'queued';
ALTER TYPE leadstatus ADD VALUE IF NOT EXISTS 'disqualified';

CREATE TABLE IF NOT EXISTS pipeline_events (
    id VARCHAR PRIMARY KEY,
    lead_id VARCHAR NOT NULL REFERENCES leads(id),
    sequence INTEGER NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    agent VARCHAR(100),
    icon VARCHAR(20),
    message TEXT,
    detail TEXT,
    payload JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_pipeline_events_lead_id
ON pipeline_events(lead_id);

ALTER TABLE IF EXISTS leads
ADD COLUMN IF NOT EXISTS attempt_count INTEGER NOT NULL DEFAULT 0;

ALTER TABLE IF EXISTS leads
ADD COLUMN IF NOT EXISTS last_error TEXT;
