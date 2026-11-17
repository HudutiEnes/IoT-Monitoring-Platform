CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ESP32 nodes
CREATE TABLE IF NOT EXISTS devices (
    device_id TEXT PRIMARY KEY,
    node_type TEXT NOT NULL CHECK (node_type IN ('body', 'hoop')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Basketball training sessions
CREATE TABLE IF NOT EXISTS training_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    notes TEXT
);

-- MPU-6050 measurements
CREATE TABLE IF NOT EXISTS imu_readings (
    time TIMESTAMPTZ NOT NULL,
    reading_id BIGINT GENERATED ALWAYS AS IDENTITY,
    session_id UUID REFERENCES training_sessions(id) ON DELETE SET NULL,
    device_id TEXT NOT NULL REFERENCES devices(device_id),
    position TEXT NOT NULL CHECK (position IN ('waist', 'wrist')),

    accel_x DOUBLE PRECISION NOT NULL,
    accel_y DOUBLE PRECISION NOT NULL,
    accel_z DOUBLE PRECISION NOT NULL,

    gyro_x DOUBLE PRECISION NOT NULL,
    gyro_y DOUBLE PRECISION NOT NULL,
    gyro_z DOUBLE PRECISION NOT NULL,

    PRIMARY KEY (time, reading_id)
);

SELECT create_hypertable(
    'imu_readings',
    'time',
    if_not_exists => TRUE
);

CREATE INDEX IF NOT EXISTS idx_imu_session_time
ON imu_readings (session_id, time DESC);

CREATE INDEX IF NOT EXISTS idx_imu_device_position_time
ON imu_readings (device_id, position, time DESC);

-- VL53L0X distance measurements
CREATE TABLE IF NOT EXISTS distance_readings (
    time TIMESTAMPTZ NOT NULL,
    reading_id BIGINT GENERATED ALWAYS AS IDENTITY,
    session_id UUID REFERENCES training_sessions(id) ON DELETE SET NULL,
    device_id TEXT NOT NULL REFERENCES devices(device_id),
    distance_mm INTEGER NOT NULL CHECK (distance_mm >= 0),

    PRIMARY KEY (time, reading_id)
);

SELECT create_hypertable(
    'distance_readings',
    'time',
    if_not_exists => TRUE
);

CREATE INDEX IF NOT EXISTS idx_distance_session_time
ON distance_readings (session_id, time DESC);

-- Basketball events detected by the hoop node
CREATE TABLE IF NOT EXISTS basketball_events (
    event_id TEXT PRIMARY KEY,
    time TIMESTAMPTZ NOT NULL,
    session_id UUID REFERENCES training_sessions(id) ON DELETE SET NULL,
    device_id TEXT NOT NULL REFERENCES devices(device_id),
    event_type TEXT NOT NULL CHECK (event_type IN ('make')),
    metadata JSONB NOT NULL DEFAULT '{}'::JSONB
);

CREATE INDEX IF NOT EXISTS idx_basketball_events_session_time
ON basketball_events (session_id, time DESC);
