import json

import paho.mqtt.client as mqtt


BROKER = "broker.hivemq.com"
PORT = 8000
TOPIC = "iot/#"

MY_NODES = ["esp32-node1", "esp32-node3", "esp32-node4", "100", "101", "102", "103", "104"]


def make_mqtt_client():
    try:
        return mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, transport="websockets")
    except (AttributeError, TypeError):
        return mqtt.Client(transport="websockets")


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"Connected to HiveMQ. Subscribing to {TOPIC}")
        client.subscribe(TOPIC)
    else:
        print(f"MQTT connection failed, rc={rc}")


def on_message(client, userdata, msg):
    payload = msg.payload.decode("utf-8", errors="ignore")

    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return

    if not isinstance(data, dict):
        return

    node = str(data.get("node", "Unknown"))
    if node not in MY_NODES:
        return

    if "connection_status" in data:
        sensor_info = f"Status: {data['connection_status']} {data.get('detail', '')}".strip()
    elif "gas_level" in data:
        sensor_info = f"Gas: {data['gas_level']} ({data.get('status', 'N/A')})"
    elif "temperature" in data:
        sensor_info = f"Temp: {data['temperature']} C | Hum: {data.get('humidity', 'N/A')}%"
    elif "light_percent" in data:
        sensor_info = f"Light: {data['light_percent']}%"
    elif "raw_data" in data:
        sensor_info = f"Raw: {data['raw_data']}"
    else:
        sensor_info = json.dumps(data, separators=(",", ":"))

    print(f"[VERIFIED] Node: {node} | {sensor_info}")


client = make_mqtt_client()
client.on_connect = on_connect
client.on_message = on_message

print(f"--- Global Monitor Active: Filtering for {MY_NODES} ---")
client.connect(BROKER, PORT)
client.loop_forever()