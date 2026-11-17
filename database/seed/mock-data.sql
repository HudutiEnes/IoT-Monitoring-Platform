

BEGIN;

-- Use fixed IDs so we can safely regenerate this mock dataset.
DELETE FROM basketball_events
WHERE session_id IN (
    '11111111-1111-4111-8111-111111111111',
    '22222222-2222-4222-8222-222222222222',
    '33333333-3333-4333-8333-333333333333'
);

DELETE FROM distance_readings
WHERE session_id IN (
    '11111111-1111-4111-8111-111111111111',
    '22222222-2222-4222-8222-222222222222',
    '33333333-3333-4333-8333-333333333333'
);

DELETE FROM imu_readings
WHERE session_id IN (
    '11111111-1111-4111-8111-111111111111',
    '22222222-2222-4222-8222-222222222222',
    '33333333-3333-4333-8333-333333333333'
);

DELETE FROM training_sessions
WHERE id IN (
    '11111111-1111-4111-8111-111111111111',
    '22222222-2222-4222-8222-222222222222',
    '33333333-3333-4333-8333-333333333333'
);

-- Register devices.
INSERT INTO devices (device_id, node_type)
VALUES
    ('body-node-01', 'body'),
    ('hoop-node-01', 'hoop')
ON CONFLICT (device_id)
DO UPDATE SET node_type = EXCLUDED.node_type;

-- Define three training sessions.
CREATE TEMP TABLE mock_sessions (
    session_id UUID PRIMARY KEY,
    started_at TIMESTAMPTZ,
    notes TEXT
) ON COMMIT DROP;

INSERT INTO mock_sessions VALUES
(
    '11111111-1111-4111-8111-111111111111',
    NOW() - INTERVAL '3 days',
    'Mock session - lower intensity'
),
(
    '22222222-2222-4222-8222-222222222222',
    NOW() - INTERVAL '2 days',
    'Mock session - medium intensity'
),
(
    '33333333-3333-4333-8333-333333333333',
    NOW() - INTERVAL '1 hour',
    'Mock session - high intensity'
);

INSERT INTO training_sessions (id, started_at, ended_at, notes)
SELECT
    session_id,
    started_at,
    started_at + INTERVAL '10 minutes',
    notes
FROM mock_sessions;

-- Generate waist and wrist IMU readings every 200 ms.
INSERT INTO imu_readings (
    time, session_id, device_id, position,
    accel_x, accel_y, accel_z,
    gyro_x, gyro_y, gyro_z
)
SELECT
    g.ts,
    s.session_id,
    'body-node-01',
    p.position,

    -- Simulated acceleration.
    sin(EXTRACT(EPOCH FROM g.ts) * 2.0 + p.phase) * 0.35
        * p.intensity + random() * 0.04,

    cos(EXTRACT(EPOCH FROM g.ts) * 1.7 + p.phase) * 0.30
        * p.intensity + random() * 0.04,

    1.0 + sin(EXTRACT(EPOCH FROM g.ts) * 2.5 + p.phase) * 0.15
        * p.intensity + random() * 0.03,

    -- Simulated angular velocity.
    sin(EXTRACT(EPOCH FROM g.ts) * 2.2 + p.phase) * 80
        * p.intensity,

    cos(EXTRACT(EPOCH FROM g.ts) * 1.8 + p.phase) * 60
        * p.intensity,

    sin(EXTRACT(EPOCH FROM g.ts) * 1.5 + p.phase) * 45
        * p.intensity

FROM mock_sessions s
CROSS JOIN LATERAL generate_series(
    s.started_at,
    s.started_at + INTERVAL '10 minutes',
    INTERVAL '200 milliseconds'
) AS g(ts)
CROSS JOIN (
    VALUES
        ('waist', 0.0::DOUBLE PRECISION, 1.0::DOUBLE PRECISION),
        ('wrist', 1.5::DOUBLE PRECISION, 1.5::DOUBLE PRECISION)
) AS p(position, phase, intensity);

-- Generate hoop distance readings every second.
INSERT INTO distance_readings (
    time, session_id, device_id, distance_mm
)
SELECT
    g.ts,
    s.session_id,
    'hoop-node-01',
    CASE
        WHEN FLOOR(EXTRACT(EPOCH FROM g.ts) / 17)::INTEGER % 6 = 0
        THEN (100 + random() * 250)::INTEGER
        ELSE (500 + random() * 1200)::INTEGER
    END
FROM mock_sessions s
CROSS JOIN LATERAL generate_series(
    s.started_at,
    s.started_at + INTERVAL '10 minutes',
    INTERVAL '1 second'
) AS g(ts);

-- Generate successful shot events.
INSERT INTO basketball_events (
    event_id, time, session_id, device_id,
    event_type, metadata
)
SELECT
    'mock-' || s.session_id::TEXT || '-' || shots.shot_no,
    s.started_at + shots.shot_no * INTERVAL '40 seconds',
    s.session_id,
    'hoop-node-01',
    'make',
    jsonb_build_object(
        'source', 'mock',
        'attempt_number', shots.shot_no
    )
FROM mock_sessions s
CROSS JOIN generate_series(1, 15) AS shots(shot_no)
WHERE
    (
        s.session_id = '11111111-1111-4111-8111-111111111111'
        AND shots.shot_no IN (1, 2, 4, 5, 7, 9, 10, 12)
    )
    OR
    (
        s.session_id = '22222222-2222-4222-8222-222222222222'
        AND shots.shot_no IN (1, 3, 5, 6, 8, 10, 12, 14, 15)
    )
    OR
    (
        s.session_id = '33333333-3333-4333-8333-333333333333'
        AND shots.shot_no IN (2, 3, 4, 6, 7, 9, 11, 13, 15)
    );

COMMIT;
