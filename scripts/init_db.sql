-- Database initialization
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(255) UNIQUE NOT NULL,
    repo VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL,
    conclusion VARCHAR(50),
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS failure_logs (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(255) NOT NULL,
    error_type VARCHAR(100) NOT NULL,
    error_message TEXT,
    stack_trace TEXT,
    severity VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES pipeline_runs(run_id)
);

CREATE TABLE IF NOT EXISTS healing_actions (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(255) NOT NULL,
    action_type VARCHAR(100) NOT NULL,
    success BOOLEAN NOT NULL,
    details JSONB,
    changes_made TEXT[],
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES pipeline_runs(run_id)
);

CREATE TABLE IF NOT EXISTS metrics (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(255),
    metric_name VARCHAR(100) NOT NULL,
    metric_value FLOAT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for better performance
CREATE INDEX idx_pipeline_runs_status ON pipeline_runs(status, conclusion);
CREATE INDEX idx_pipeline_runs_created ON pipeline_runs(created_at DESC);
CREATE INDEX idx_failure_logs_error_type ON failure_logs(error_type);
CREATE INDEX idx_healing_actions_success ON healing_actions(success);

-- Views for analytics
CREATE OR REPLACE VIEW healing_statistics AS
SELECT 
    COUNT(*) FILTER (WHERE conclusion = 'failure') as total_failures,
    COUNT(*) FILTER (WHERE EXISTS (
        SELECT 1 FROM healing_actions ha 
        WHERE ha.run_id = pipeline_runs.run_id
    )) as healing_attempted,
    COUNT(*) FILTER (WHERE EXISTS (
        SELECT 1 FROM healing_actions ha 
        WHERE ha.run_id = pipeline_runs.run_id AND ha.success = true
    )) as healing_successful,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE EXISTS (
            SELECT 1 FROM healing_actions ha 
            WHERE ha.run_id = pipeline_runs.run_id AND ha.success = true
        )) / NULLIF(COUNT(*) FILTER (WHERE conclusion = 'failure'), 0),
        2
    ) as success_rate_percentage
FROM pipeline_runs
WHERE created_at >= NOW() - INTERVAL '30 days';