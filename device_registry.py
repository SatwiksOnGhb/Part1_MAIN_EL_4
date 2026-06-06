import json
from pathlib import Path


class Device:
    def __init__(self, data):
        self.device_id = data["device_id"]
        self.device_type = data["device_type"]
        self.location = data["location"]
        self.sensors = data["sensors"]
        self.actuators = data["actuators"]
        self.publish_topic = data["publish_topic"]
        self.subscribe_topic = data["subscribe_topic"]
        self.status = data["status"]
        self.last_seen = data["last_seen"]

    def __repr__(self):
        return f"Device({self.device_id}, {self.device_type}, {self.location})"


class DeviceRegistry:
    def __init__(self, registry_file="device_registry.json"):
        registry_path = Path(__file__).parent / registry_file
        with open(registry_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.devices = {}
        for device_data in data["devices"]:
            device = Device(device_data)
            self.devices[device.device_id] = device

    def get_device_by_location(self, location):
        return [d for d in self.devices.values() if d.location == location]

    def get_device_by_sensor(self, reading_type):
        matches = []
        for device in self.devices.values():
            for sensor in device.sensors:
                if reading_type in sensor.get("readings", []):
                    matches.append(device)
                    break
        return matches

    def get_device_by_id(self, device_id):
        return self.devices.get(device_id)

    def get_device_by_type(self, device_type):
        return [d for d in self.devices.values() if d.device_type == device_type]

    def get_devices_with_actuator(self):
        return [d for d in self.devices.values() if d.actuators]

    def update_status(self, device_id, status):
        from datetime import datetime, timezone
        device = self.devices.get(device_id)
        if device is None:
            return False
        device.status = status
        device.last_seen = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return True

    def is_online(self, device_id, timeout_seconds=120):
        from datetime import datetime, timezone
        device = self.devices.get(device_id)
        if device is None:
            return False
        try:
            last_seen_dt = datetime.strptime(device.last_seen, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            return False
        age = (datetime.now(timezone.utc) - last_seen_dt).total_seconds()
        return age <= timeout_seconds

    def get_capabilities(self, device_id):
        device = self.devices.get(device_id)
        if device is None:
            return None
        readings = []
        for sensor in device.sensors:
            readings.extend(sensor.get("readings", []))
        controls = []
        for actuator in device.actuators:
            controls.extend(actuator.get("control", []))
        return {
            "device_id": device.device_id,
            "device_type": device.device_type,
            "location": device.location,
            "sensors": device.sensors,
            "actuators": device.actuators,
            "readings": readings,
            "controls": controls,
            "publish_topic": device.publish_topic,
            "subscribe_topic": device.subscribe_topic,
        }