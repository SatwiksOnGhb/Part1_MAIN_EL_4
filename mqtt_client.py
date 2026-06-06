import json
import threading
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

from device_registry import DeviceRegistry


BROKER = "broker.hivemq.com"
PORT = 8000
PRINT_INTERVAL = 10


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
        print(f"MQTT connection failed, rc={rc}")
        return
    print("Connected to HiveMQ")
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

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    with cache_lock:
        data_cache[device_id] = {
            "timestamp": timestamp,
            "data": data,
            "topic": topic,
        }

    registry.update_status(device_id, "online")


def print_cache():
    with cache_lock:
        cache_snapshot = dict(data_cache)

    print("\n" + "=" * 60)
    print("MQTT DATA CACHE CONTENTS")
    print("=" * 60)

    if not cache_snapshot:
        print("(no messages received yet)")
    else:
        for device_id, entry in cache_snapshot.items():
            print(f"\U0001F4F1 Device: {device_id}")
            print(f"   Timestamp: {entry['timestamp']}")
            print(f"   Data: {entry['data']}")
            print(f"   Topic: {entry['topic']}")

    print("\n" + "=" * 60)
    print("DEVICE STATUS SUMMARY")
    print("=" * 60)

    for device_id in registry.devices:
        online = registry.is_online(device_id, timeout_seconds=30)
        icon = "\U0001F7E2" if online else "\U0001F534"
        status_word = "online" if online else "offline"
        last_seen = registry.devices[device_id].last_seen
        print(f"{icon} {device_id}: {status_word} (last seen: {last_seen})")


def main():
    client = make_mqtt_client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(BROKER, PORT)
    client.loop_start()

    try:
        while True:
            print(f"\nWaiting {PRINT_INTERVAL} seconds for MQTT messages...")
            time.sleep(PRINT_INTERVAL)
            print_cache()
    except KeyboardInterrupt:
        print("\nStopping MQTT client...")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
