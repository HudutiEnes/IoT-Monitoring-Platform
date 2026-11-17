# IoT Monitoring Platform

A Docker-based IoT monitoring platform built using MQTT, Python, TimescaleDB, and Grafana.

## Architecture

ESP32 Sensors → Android Gateway → Mosquitto MQTT → Python Subscriber → TimescaleDB → Grafana

## Technology Stack

- Ubuntu / Fedora Linux
- Docker and Docker Compose
- Eclipse Mosquitto
- Python
- TimescaleDB
- Grafana
- AWS EC2 (deployment)

## Project Status

- [x] Docker environment
- [x] MQTT broker
- [x] TimescaleDB setup
- [ ] Python MQTT subscriber
- [ ] Sensor data ingestion
- [ ] Grafana dashboards
- [ ] AWS deployment
- [ ] HTTPS configuration

## Development

Clone the repository and configure your environment:

```bash
cp .env.example .env
```

Edit `.env` with your own credentials, then start the services:

```bash
docker compose up -d
```
