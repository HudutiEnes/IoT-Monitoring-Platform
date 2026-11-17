import os
import json
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt
import psycopg


# MQTT configuration
MQTT_HOST = os.getenv("MQTT_HOST", "mqtt")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")

TOPIC = "sensors/#"

# Database configuration
DB_HOST = os.getenv("DB_HOST", "timescaledb")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "iot_platform")
DB_USER = os.getenv("DB_USER", "iot_user")
DB_PASSWORD = os.getenv("DB_PASSWORD")

db_connection = None


def connect_database():
    global db_connection

    while True:
        try:
            db_connection = psycopg.connect(
                host=DB_HOST,
                port=DB_PORT,
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD
            )

            print("Connected to TimescaleDB")
            return

        except psycopg.Error as error:
            print(f"Database connection failed: {error}")
            time.sleep(5)


def get_timestamp(data):
    timestamp = data.get("timestamp")

    if timestamp is None:
        return datetime.now(timezone.utc)

    if not isinstance(timestamp, str):
        raise ValueError("timestamp must be an ISO 8601 string")

    parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed


def validate_number(value, field):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be numeric")

    if not __import__("math").isfinite(value):
        raise ValueError(f"{field} must be finite")

    return value


def register_device(device_id, node_type):
    with db_connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO devices (device_id, node_type)
            VALUES (%s, %s)
            ON CONFLICT (device_id)
            DO UPDATE SET node_type = EXCLUDED.node_type
            """,
            (device_id, node_type)
        )


def insert_imu_reading(data):
    device_id = data.get("device_id")
    position = data.get("position")
    session_id = data.get("session_id")
    timestamp = get_timestamp(data)

    if not isinstance(device_id, str) or not device_id:
        raise ValueError("Missing device_id")

    if position not in ("waist", "wrist"):
        raise ValueError("position must be waist or wrist")

    accel = data.get("accel", {})
    gyro = data.get("gyro", {})

    values = [
        validate_number(accel.get(axis), f"accel.{axis}")
        for axis in ("x", "y", "z")
    ]

    values += [
        validate_number(gyro.get(axis), f"gyro.{axis}")
        for axis in ("x", "y", "z")
    ]

    register_device(device_id, "body")

    with db_connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO imu_readings (
                time, session_id, device_id, position,
                accel_x, accel_y, accel_z,
                gyro_x, gyro_y, gyro_z
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                timestamp, session_id, device_id, position,
                *values
            )
        )

    db_connection.commit()

    print(f"Stored MPU-6050 reading: {position}")


def insert_hoop_reading(data):
    device_id = data.get("device_id")
    session_id = data.get("session_id")
    timestamp = get_timestamp(data)

    if not isinstance(device_id, str) or not device_id:
        raise ValueError("Missing device_id")

    distance = validate_number(
        data.get("distance_mm"),
        "distance_mm"
    )

    if not distance.is_integer() if isinstance(distance, float) else False:
        raise ValueError("distance_mm must be an integer")

    distance = int(distance)

    if distance < 0:
        raise ValueError("distance_mm cannot be negative")

    register_device(device_id, "hoop")

    with db_connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO distance_readings (
                time, session_id, device_id, distance_mm
            )
            VALUES (%s, %s, %s, %s)
            """,
            (timestamp, session_id, device_id, distance)
        )

        event_type = data.get("event")

        if event_type is not None:
            if event_type != "make":
                raise ValueError("Unsupported basketball event")

            event_id = data.get("event_id")

            if not isinstance(event_id, str) or not event_id:
                raise ValueError("A unique event_id is required for a make")

            cursor.execute(
                """
                INSERT INTO basketball_events (
                    event_id, time, session_id,
                    device_id, event_type
                )
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (event_id) DO NOTHING
                """,
                (
                    event_id, timestamp, session_id,
                    device_id, event_type
                )
            )

    db_connection.commit()

    print("Stored VL53L0X reading")

    if data.get("event") == "make":
        print(f"Basketball make event: {data['event_id']}")


def process_message(data):
    sensor = data.get("sensor")

    if sensor == "mpu6050":
        insert_imu_reading(data)

    elif sensor == "vl53l0x":
        insert_hoop_reading(data)

    else:
        raise ValueError(f"Unknown sensor type: {sensor}")


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code.is_failure:
        print(f"MQTT connection failed: {reason_code}")
        return

    print(f"Connected to MQTT broker: {MQTT_HOST}:{MQTT_PORT}")

    client.subscribe(TOPIC, qos=1)
    print(f"Subscribed to: {TOPIC}")


def on_message(client, userdata, message):
    global db_connection

    try:
        data = json.loads(message.payload.decode("utf-8"))

        if db_connection is None or db_connection.closed:
            connect_database()

        process_message(data)

    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        print(f"Invalid sensor message: {error}")

    except psycopg.Error as error:
        print(f"Database error: {error}")

        if db_connection is not None:
            db_connection.rollback()
            db_connection.close()
            db_connection = None


def main():
    connect_database()

    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id="basketball-subscriber"
    )

    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

    client.on_connect = on_connect
    client.on_message = on_message

    print("Connecting to MQTT broker...")

    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    client.loop_forever()


if __name__ == "__main__":
    main()
