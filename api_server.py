import json
import threading
from datetime import datetime, timezone, timedelta

import paho.mqtt.client as mqtt
from flask import Flask, jsonify

from device_registry import DeviceRegistry


IST = timezone(timedelta(hours=5, minutes=30))


BROKER = "broker.hivemq.com"
MQTT_PORT = 8000
API_PORT = 5000
OFFLINE_TIMEOUT_SECONDS = 30
OFFLINE_CHECK_INTERVAL_SECONDS = 10
SNAPSHOT_FILE = "live_state.json"
SNAPSHOT_INTERVAL_SECONDS = 5
M3_POLL_INTERVAL_SECONDS = 30
M3_POLL_COMMANDS = ["t", "l", "p"]


registry = DeviceRegistry()


topic_to_device = {}
for device_id, device in registry.devices.items():
    topic_to_device[device.publish_topic] = device_id


data_cache = {}
cache_lock = threading.Lock()


def make_mqtt_client():
    try:
        return mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, transport="websockets")
    except (AttributeError, TypeError):
        return mqtt.Client(transport="websockets")


def on_connect(client, userdata, flags, rc):
    if rc != 0:
        print(f"[MQTT] Connection failed, rc={rc}")
        return
    print("[MQTT] Connected to HiveMQ")
    for device in registry.devices.values():
        client.subscribe(device.publish_topic)


def on_message(client, userdata, msg):
    topic = msg.topic
    device_id = topic_to_device.get(topic)
    if device_id is None:
        return

    try:
        data = json.loads(msg.payload.decode("utf-8", errors="ignore"))
    except json.JSONDecodeError:
        return

    if not isinstance(data, dict):
        return

    timestamp = datetime.now(IST).strftime("%Y-%m-%dT%H:%M:%S.%f%z")

    with cache_lock:
        data_cache[device_id] = {
            "timestamp": timestamp,
            "data": data,
            "topic": topic,
        }

    registry.update_status(device_id, "online")


def start_mqtt_subscriber():
    client = make_mqtt_client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(BROKER, MQTT_PORT)
    client.loop_forever()


def start_m3_auto_poller():
    import time
    publisher = make_mqtt_client()
    try:
        publisher.connect(BROKER, MQTT_PORT)
        publisher.loop_start()
    except Exception as exc:
        print(f"[POLLER] Failed to connect publisher: {exc}")
        return
    print(f"[POLLER] Auto-polling M3 nodes every {M3_POLL_INTERVAL_SECONDS}s")
    cmd_index = 0
    while True:
        time.sleep(M3_POLL_INTERVAL_SECONDS)
        command = M3_POLL_COMMANDS[cmd_index % len(M3_POLL_COMMANDS)]
        cmd_index += 1
        for device_id, device in registry.devices.items():
            if device.device_type != "M3_Node":
                continue
            payload = json.dumps({"command": command})
            try:
                publisher.publish(device.subscribe_topic, payload)
            except Exception as exc:
                print(f"[POLLER] Failed to publish to {device_id}: {exc}")


def start_offline_checker():
    import time
    while True:
        time.sleep(OFFLINE_CHECK_INTERVAL_SECONDS)
        for device_id, device in registry.devices.items():
            if not registry.is_online(device_id, timeout_seconds=OFFLINE_TIMEOUT_SECONDS):
                if device.status != "offline":
                    device.status = "offline"


def start_snapshot_writer():
    import time
    from pathlib import Path
    output_path = Path(__file__).parent / SNAPSHOT_FILE
    while True:
        time.sleep(SNAPSHOT_INTERVAL_SECONDS)
        try:
            with cache_lock:
                cache_snapshot = {
                    device_id: {
                        "data": entry["data"],
                        "timestamp": entry["timestamp"],
                        "topic": entry["topic"],
                    }
                    for device_id, entry in data_cache.items()
                }
            status_snapshot = {}
            for device_id, device in registry.devices.items():
                status_snapshot[device_id] = {
                    "online": registry.is_online(device_id, timeout_seconds=OFFLINE_TIMEOUT_SECONDS),
                    "status": device.status,
                    "last_seen": device.last_seen,
                    "location": device.location,
                    "device_type": device.device_type,
                }
            snapshot = {
                "updated_at": datetime.now(IST).strftime("%Y-%m-%dT%H:%M:%S%z"),
                "status": status_snapshot,
                "cache": cache_snapshot,
            }
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(snapshot, f, indent=2)
        except Exception as exc:
            print(f"[SNAPSHOT] Failed to write {SNAPSHOT_FILE}: {exc}")


app = Flask(__name__)


def device_summary(device):
    summary = {
        "id": device.device_id,
        "type": device.device_type,
        "location": device.location,
        "sensors": [
            {"name": s["name"], "readings": s.get("readings", [])}
            for s in device.sensors
        ],
        "status": device.status,
    }
    if device.actuators:
        summary["actuators"] = [
            {"name": a["name"], "control": a.get("control", [])}
            for a in device.actuators
        ]
    return summary


@app.route("/api/devices")
def get_all_devices():
    devices = [device_summary(d) for d in registry.devices.values()]
    return jsonify({"devices": devices})


@app.route("/api/device/<device_id>/reading")
def get_device_reading(device_id):
    if device_id not in registry.devices:
        return jsonify({"error": f"Device '{device_id}' not found"}), 404

    with cache_lock:
        entry = data_cache.get(device_id)

    if entry is None:
        return jsonify({
            "device_id": device_id,
            "reading": None,
            "timestamp": None,
            "message": "No data received yet",
        }), 200

    return jsonify({
        "device_id": device_id,
        "reading": entry["data"],
        "timestamp": entry["timestamp"],
    })


@app.route("/api/zone/<zone>/devices")
def get_zone_devices(zone):
    matches = registry.get_device_by_location(zone)
    devices = [
        {
            "id": d.device_id,
            "sensors": [
                {"name": s["name"], "readings": s.get("readings", [])}
                for s in d.sensors
            ],
        }
        for d in matches
    ]
    return jsonify({"zone": zone, "devices": devices})


@app.route("/api/network/topology")
def get_network_topology():
    nodes = list(registry.devices.keys()) + ["hivemq_broker"]
    edges = []
    for device_id in registry.devices:
        edges.append({"source": device_id, "target": "hivemq_broker"})
        edges.append({"source": "hivemq_broker", "target": device_id})
    return jsonify({"nodes": nodes, "edges": edges})


@app.route("/api/cache/all")
def get_full_cache():
    with cache_lock:
        snapshot = {
            device_id: {
                "data": entry["data"],
                "timestamp": entry["timestamp"],
                "topic": entry["topic"],
            }
            for device_id, entry in data_cache.items()
        }
    return jsonify(snapshot)


@app.route("/api/status")
def get_status():
    status = {}
    for device_id, device in registry.devices.items():
        online = registry.is_online(device_id, timeout_seconds=OFFLINE_TIMEOUT_SECONDS)
        status[device_id] = {
            "online": online,
            "status": device.status,
            "last_seen": device.last_seen,
        }
    return jsonify(status)


@app.route("/")
def index():
    return jsonify({
        "service": "IoT Device API",
        "endpoints": [
            "GET /api/devices",
            "GET /api/device/<device_id>/reading",
            "GET /api/zone/<zone>/devices",
            "GET /api/network/topology",
            "GET /api/cache/all",
            "GET /api/status",
        ],
    })


def main():
    mqtt_thread = threading.Thread(target=start_mqtt_subscriber, daemon=True)
    mqtt_thread.start()

    offline_thread = threading.Thread(target=start_offline_checker, daemon=True)
    offline_thread.start()

    snapshot_thread = threading.Thread(target=start_snapshot_writer, daemon=True)
    snapshot_thread.start()

    poller_thread = threading.Thread(target=start_m3_auto_poller, daemon=True)
    poller_thread.start()

    print(f"[API] Running on http://localhost:{API_PORT}")
    print(f"[SNAPSHOT] Writing {SNAPSHOT_FILE} every {SNAPSHOT_INTERVAL_SECONDS}s")
    app.run(host="0.0.0.0", port=API_PORT, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()