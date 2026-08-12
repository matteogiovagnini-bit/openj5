-- OpenJ5 PostgreSQL Initialization Script

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Robot events store
CREATE TABLE IF NOT EXISTS events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_type VARCHAR(255) NOT NULL,
    source_node VARCHAR(50) NOT NULL,
    aggregate_id VARCHAR(255),
    payload JSONB NOT NULL DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    version INTEGER NOT NULL DEFAULT 1,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_events_event_type ON events(event_type);
CREATE INDEX idx_events_source_node ON events(source_node);
CREATE INDEX idx_events_aggregate_id ON events(aggregate_id);
CREATE INDEX idx_events_timestamp ON events(timestamp DESC);
CREATE INDEX idx_events_payload_gin ON events USING GIN(payload);

-- Configuration snapshots
CREATE TABLE IF NOT EXISTS config_snapshots (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    node_id VARCHAR(50) NOT NULL,
    config JSONB NOT NULL,
    version INTEGER NOT NULL,
    checksum VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(node_id, version)
);

CREATE INDEX idx_config_snapshots_node ON config_snapshots(node_id, version DESC);

-- Robot state history
CREATE TABLE IF NOT EXISTS robot_state_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    state VARCHAR(50) NOT NULL,
    previous_state VARCHAR(50),
    node_states JSONB NOT NULL DEFAULT '{}',
    trigger VARCHAR(255),
    metadata JSONB DEFAULT '{}',
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_state_history_timestamp ON robot_state_history(timestamp DESC);

-- Plugin registry
CREATE TABLE IF NOT EXISTS plugins (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    plugin_id VARCHAR(255) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    version VARCHAR(50) NOT NULL,
    author VARCHAR(255),
    description TEXT,
    state VARCHAR(50) NOT NULL DEFAULT 'loaded',
    config JSONB DEFAULT '{}',
    installed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Firmware/OTA registry
CREATE TABLE IF NOT EXISTS firmware (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    firmware_id VARCHAR(255) NOT NULL UNIQUE,
    node_id VARCHAR(50) NOT NULL,
    version VARCHAR(50) NOT NULL,
    file_url TEXT NOT NULL,
    checksum_sha256 VARCHAR(64) NOT NULL,
    signature TEXT,
    size_bytes BIGINT,
    status VARCHAR(50) NOT NULL DEFAULT 'registered',
    rollout_percentage INTEGER DEFAULT 100,
    staged_rollout BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deployed_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

CREATE INDEX idx_firmware_node ON firmware(node_id, version DESC);

-- OTA deployment status
CREATE TABLE IF NOT EXISTS ota_deployments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    firmware_id VARCHAR(255) NOT NULL REFERENCES firmware(firmware_id),
    node_id VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    progress FLOAT DEFAULT 0.0,
    error TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_ota_deployments_status ON ota_deployments(status);

-- Calibration profiles
CREATE TABLE IF NOT EXISTS calibration_profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    profile_id VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    version VARCHAR(50) NOT NULL,
    positions JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(profile_id, version)
);

-- Events for log aggregation
CREATE TABLE IF NOT EXISTS system_logs (
    id BIGSERIAL PRIMARY KEY,
    level VARCHAR(20) NOT NULL,
    logger VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    correlation_id VARCHAR(64),
    node_id VARCHAR(50),
    metadata JSONB DEFAULT '{}',
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_system_logs_level ON system_logs(level);
CREATE INDEX idx_system_logs_timestamp ON system_logs(timestamp DESC);
CREATE INDEX idx_system_logs_node ON system_logs(node_id);

-- Partition by month for log retention
SELECT partman.create_parent(
    p_parent_table := 'public.system_logs',
    p_control := 'timestamp',
    p_type := 'native',
    p_interval := '1 month',
    p_premake := 3
);
