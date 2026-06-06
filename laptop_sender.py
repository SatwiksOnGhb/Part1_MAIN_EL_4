import json
import threading

import paho.mqtt.client as mqtt


BROKER = "broker.hivemq.com"
PORT = 8000

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
