import json
import threading
import urllib.error
import urllib.request

import paho.mqtt.client as mqtt


BROKER = "broker.hivemq.com"
PORT = 8000
API_URL = "http://localhost:5000/api/status"

TARGET_TO_DEVICE_ID = {
    "zone_a": "esp32_zone_a",
    "zone_c": "esp32_zone_c",
    "zone_d": "esp32_zone_d",
    "100": "m3_node_100",
    "101": "m3_node_101",
    "102": "m3_node_102",
}

connected = threading.Event()


def make_mqtt_client():
    try:
        return mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, transport="websockets")
    except (AttributeError, TypeError):
        return mqtt.Client(transport="websockets")


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to HiveMQ")
        connected.set()
    else:
        print(f"MQTT connection failed, rc={rc}")


def is_device_online(target):
    device_id = TARGET_TO_DEVICE_ID.get(target)
    if device_id is None:
        return None
    try:
        with urllib.request.urlopen(API_URL, timeout=2) as response:
            status_data = json.loads(response.read().decode("utf-8"))
        device_status = status_data.get(device_id)
        if device_status is None:
            return None
        return device_status.get("online", False)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None


client = make_mqtt_client()
client.on_connect = on_connect
client.connect(BROKER, PORT)
client.loop_start()

if not connected.wait(timeout=10):
    raise TimeoutError("Timed out connecting to HiveMQ")

print("--- GLOBAL MESH COMMAND CENTER ---")
print("Local Targets: zone_a (Light), zone_c (Climate), zone_d (Gas)")
print("Remote Targets: 100, 101, 102, etc.")
print("-" * 40)

try:
    while True:
        target = input("\nEnter Target ID (e.g., 100 or zone_d): ").strip().lower()
        cmd = input("Command (read/t/l/p/e/restart): ").strip().lower()

        online = is_device_online(target)
        if online is False:
            override = input(f"WARNING: Target '{target}' appears offline. Send anyway? (y/N): ").strip().lower()
            if override != "y":
                print("Command aborted.")
                continue
        elif online is None:
            print("(Could not verify status with API server - sending anyway)")

        if target.startswith("zone_"):
            topic = f"iot/commands/{target}"
            payload = cmd
        else:
            topic = f"iot/france/control/{target}"
            payload = json.dumps({"command": cmd})

        result = client.publish(topic, payload)
        result.wait_for_publish(timeout=5)
        print(f"Sent '{cmd}' to {topic} (rc={result.rc})")
except KeyboardInterrupt:
    print("\nStopping sender...")
finally:
    client.loop_stop()
    client.disconnect()