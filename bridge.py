import json
import socket
import threading
import time

import paho.mqtt.client as mqtt


MQTT_BROKER = "broker.hivemq.com"
NODE_IDS = ["100", "101", "102"]
PORT = 20000

node_sockets = {}
mqtt_ready = threading.Event()
pending_commands = {}
pending_lock = threading.Lock()


def make_mqtt_client():
    try:
        return mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
    except (AttributeError, TypeError):
        return mqtt.Client()


def publish_node_status(node_id, status, detail=""):
    topic = f"iot/france/node/{node_id}"
    payload = json.dumps({
        "node": node_id,
        "connection_status": status,
        "detail": detail,
        "timestamp": time.time(),
        "origin": "france",
    })
    client.publish(topic, payload, retain=True)


def on_connect(client, userdata, flags, rc):
    if rc != 0:
        print(f"Bridge failed to connect to HiveMQ, rc={rc}")
        return

    print("Bridge connected to HiveMQ")
    client.subscribe("iot/france/control/#")
    client.publish("iot/france/bridge/status", json.dumps({
        "bridge": "grenoble",
        "connection_status": "online",
        "nodes": NODE_IDS,
        "timestamp": time.time(),
    }), retain=True)
    mqtt_ready.set()


def on_message(client, userdata, msg):
    try:
        target_node = msg.topic.split("/")[-1]
        payload = json.loads(msg.payload.decode("utf-8", errors="ignore"))
        command = str(payload.get("command", "")).strip()

        if target_node in node_sockets and command:
            print(f"Forwarding command to Node {target_node}: {command}")
            with pending_lock:
                pending_commands[target_node] = command
            time.sleep(0.1)
            node_sockets[target_node].send(f"{command}\n".encode())
        elif command:
            print(f"Command for Node {target_node} ignored: node socket not connected")
    except Exception as exc:
        print(f"Error routing command: {exc}")


def handle_node(node_id):
    host = f"m3-{node_id}.grenoble.iot-lab.info"
    topic = f"iot/france/node/{node_id}"

    while True:
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((host, PORT))
            node_sockets[node_id] = sock
            print(f"[SUCCESS] Connected to Node {node_id}")
            publish_node_status(node_id, "connected", f"Socket connected to {host}:{PORT}")

            sock.send(b"\x03")
            time.sleep(0.5)
            sock.send(b"\n")

            while True:
                data = sock.recv(1024).decode("utf-8", errors="ignore")
                if not data:
                    raise ConnectionError("socket closed by remote node")

                stripped = data.strip()
                if not stripped:
                    continue

                with pending_lock:
                    command = pending_commands.get(node_id)

                if not command:
                    print(f"Ignored startup/log output from Node {node_id}: {stripped[:120]}")
                    continue
                print(f"DEBUG Node {node_id} response: {repr(stripped[:120])}")

                payload = json.dumps({
                    "node": node_id,
                    "command": command,
                    "command_output": stripped,
                    "timestamp": time.time(),
                    "origin": "france",
                })
                client.publish(topic, payload)
                print(f"Published command output from Node {node_id}: {stripped[:120]}")

                if "cmd >" in stripped or stripped.endswith(">"):
                    with pending_lock:
                        pending_commands.pop(node_id, None)
        except Exception as exc:
            node_sockets.pop(node_id, None)
            if sock is not None:
                try:
                    sock.close()
                except OSError:
                    pass
            print(f"Node {node_id} connection lost: {exc}. Retrying...")
            publish_node_status(node_id, "disconnected", str(exc))
            time.sleep(5)


client = make_mqtt_client()
client.on_connect = on_connect
client.on_message = on_message
client.connect(MQTT_BROKER, 1883)
client.loop_start()

if not mqtt_ready.wait(timeout=15):
    raise TimeoutError("Timed out connecting bridge to HiveMQ")

for nid in NODE_IDS:
    threading.Thread(target=handle_node, args=(nid,), daemon=True).start()

print("Bi-directional Bridge is running. Press Ctrl+C to stop.")
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("Stopping...")