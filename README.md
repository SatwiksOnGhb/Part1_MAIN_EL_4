# IoT Mesh System

NLP-driven IoT management system that bridges local ESP32 sensors and remote FIT IoT-LAB M3 nodes through a unified MQTT-based architecture, exposed via a REST API.

Built as Team 35's project at RV College of Engineering, Bengaluru.

## Architecture

```
ESP32 Zones (LDR / DHT11 / MQ2)   FIT IoT-LAB M3 Nodes (Grenoble)
              \                       /
               \                     /
                +---> HiveMQ Broker <---+
                          |
                          v
                  api_server.py (Flask)
                  - MQTT subscriber thread
                  - In-memory data cache
                  - Device registry
                  - REST endpoints
                          |
                          v
                  NLP intent layer (future)
```

## Components

| File | Role |
|------|------|
| `bridge.py` | Runs on FIT IoT-LAB Grenoble server; bridges M3 nodes (private TCP) to HiveMQ (public MQTT) |
| `api_server.py` | Flask REST API + embedded MQTT subscriber; maintains live data cache |
| `device_registry.py` | `DeviceRegistry` class with location/sensor/status/capability queries |
| `device_registry.json` | Central database of all devices, sensors, actuators, and MQTT topics |
| `network_graph.py` | `IoTNetworkGraph` class; generates network topology PNG via networkx + matplotlib |
| `laptop_sender.py` | CLI for sending commands to any device via MQTT |

## API Endpoints

| Endpoint | Returns |
|----------|---------|
| `GET /api/devices` | All registered devices with sensors, actuators, status |
| `GET /api/device/<device_id>/reading` | Latest cached reading for a device |
| `GET /api/zone/<zone>/devices` | All devices in a given zone |
| `GET /api/network/topology` | Graph of nodes and bidirectional edges to HiveMQ |
| `GET /api/cache/all` | Entire live MQTT cache |

## Setup

```bash
pip install flask paho-mqtt networkx matplotlib
```

## Running

**1. On the FIT IoT-LAB Grenoble server (via SSH):**
```bash
python3 bridge.py
```

**2. Locally (in two separate terminals):**
```bash
python api_server.py
python laptop_sender.py
```

**3. Generate topology graph (one-shot):**
```bash
python network_graph.py
```

## Devices

| Device ID | Type | Location | Sensors |
|-----------|------|----------|---------|
| esp32_zone_a | ESP32 | Zone A | LDR (light) |
| esp32_zone_c | ESP32 | Zone C | DHT11 (temp + humidity) |
| esp32_zone_d | ESP32 | Zone D | MQ2 (gas) |
| m3_node_100 | M3_Node | FIT Lab Grenoble | LPS331AP (temp + pressure), ISL29020 (light) |
| m3_node_101 | M3_Node | FIT Lab Grenoble | LPS331AP, ISL29020 |
| m3_node_102 | M3_Node | FIT Lab Grenoble | LPS331AP, ISL29020 |

## Notes

ESP32 firmware (`.ino` files) is not included in this repository.
