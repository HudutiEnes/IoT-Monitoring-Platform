import os
import json
import time

import paho.mqtt.client as mqtt
import psycopg


# MQTT configuration
MQTT_HOST = os.getenv("MQTT_HOST", "mqtt")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")

# Database configuration
DB_HOST = os.getenv("DB_HOST", "timescaledb")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "iot_platform")
DB_USER = os.getenv("DB_USER", "iot_user")
DB_PASSWORD = os.getenv("DB_PASSWORD")

TOPIC = "sensors/#"

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
            print("Retrying in 5 seconds...")
            time.sleep(5)


def insert_reading(data):
    global db_connection

    device_id = data.get("device_id")
    temperature = data.get("temperature")
    humidity = data.get("humidity")

    if not isinstance(device_id, str) or not device_id.strip():
        raise ValueError("Invalid device_id")

    if not isinstance(temperature, (int, float)) or isinstance(temperature, bool):
        raise ValueError("Invalid temperature")

    if not isinstance(humidity, (int, float)) or isinstance(humidity, bool):
        raise ValueError("Invalid humidity")

    try:
        with db_connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO sensor_readings
                    (device_id, temperature, humidity)
                VALUES (%s, %s, %s)
                """,
                (device_id, temperature, humidity)
            )

        db_connection.commit()

        print(f"Saved reading from {device_id}")

    except psycopg.Error:
        db_connection.rollback()
        db_connection.close()
        db_connection = None
        raise


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code.is_failure:
        print(f"MQTT connection failed: {reason_code}")
        return

    print(f"Connected to MQTT: {MQTT_HOST}:{MQTT_PORT}")
    client.subscribe(TOPIC)
    print(f"Subscribed to {TOPIC}")


def on_message(client, userdata, message):
    global db_connection

    try:
        payload = message.payload.decode("utf-8")
        data = json.loads(payload)

        if db_connection is None or db_connection.closed:
            connect_database()

        insert_reading(data)

    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as error:
        print(f"Invalid sensor message: {error}")

    except psycopg.Error as error:
        print(f"Database insertion failed: {error}")


def main():
    connect_database()

    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id="iot-python-subscriber"
    )

    client.username_pw_set(
        MQTT_USERNAME,
        MQTT_PASSWORD
    )

    client.on_connect = on_connect
    client.on_message = on_message

    print("Connecting to MQTT broker...")

    client.connect(
        MQTT_HOST,
        MQTT_PORT,
        keepalive=60
    )

    client.loop_forever()


if __name__ == "__main__":
    main()
