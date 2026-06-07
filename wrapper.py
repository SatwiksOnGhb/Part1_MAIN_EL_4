#!/usr/bin/env python3
"""
IoT Mesh System Wrapper
One command starts everything: bridge.py on FIT server + api_server.py locally
Uses SSH key authentication (~/.ssh/id_rsa_iotlab)
"""

import subprocess
import threading
import time
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).parent
SSH_KEY = Path.home() / ".ssh" / "id_rsa_iotlab"

print("\n" + "=" * 70)
print("IoT Mesh System Wrapper")
print("=" * 70)

# Check SSH key exists
if not SSH_KEY.exists():
    print(f"\n✗ SSH key not found at {SSH_KEY}")
    print("\nGenerate one with:")
    print('  ssh-keygen -t rsa -f "$HOME\\.ssh\\id_rsa_iotlab"')
    print("\nThen send your public key to the project owner to add to the FIT server:")
    print(f'  Get-Content "{SSH_KEY}.pub"')
    sys.exit(1)

# Get FIT username
print("\n[Setup] FIT Server Credentials")
print("-" * 70)
fit_username = input("FIT username: ").strip()

# Step 1: SSH to FIT and start bridge.py
print("\n[1/2] Starting bridge.py on FIT server...")
print("-" * 70)

try:
    import paramiko

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    # Connect with key auth
    ssh.connect(
        "grenoble.iot-lab.info",
        username=fit_username,
        key_filename=str(SSH_KEY),
        timeout=10
    )

    # Auto-upload bridge.py to FIT server
    local_bridge = PROJECT_DIR / "bridge.py"
    if not local_bridge.exists():
        print("✗ bridge.py not found in project folder")
        sys.exit(1)

    print("  Uploading bridge.py to FIT server...")
    sftp = ssh.open_sftp()
    sftp.put(str(local_bridge), "bridge.py")
    sftp.close()
    print("  ✓ bridge.py uploaded")

    # Kill any existing bridge.py first
    ssh.exec_command("pkill -f bridge.py")
    time.sleep(1)

    # Start bridge.py — keep SSH alive and stream output live
    transport = ssh.get_transport()
    channel = transport.open_session()
    channel.exec_command("python3 bridge.py")

    def stream_bridge():
        while True:
            if channel.recv_ready():
                data = channel.recv(1024).decode("utf-8", errors="replace")
                for line in data.splitlines():
                    print(f"[BRIDGE] {line}")
            if channel.recv_stderr_ready():
                data = channel.recv_stderr(1024).decode("utf-8", errors="replace")
                for line in data.splitlines():
                    print(f"[BRIDGE_ERR] {line}")
            if channel.exit_status_ready():
                break
            time.sleep(0.1)

    bridge_thread = threading.Thread(target=stream_bridge, daemon=True)
    bridge_thread.start()

    print("  Waiting for bridge to connect to M3 nodes...")
    time.sleep(5)
    print("✓ bridge.py running on FIT server")

except ImportError:
    print("✗ paramiko not installed")
    print("   Run: pip install paramiko")
    sys.exit(1)
except paramiko.AuthenticationException:
    print("✗ SSH key authentication failed.")
    print(f"  Make sure your public key has been added to the FIT server.")
    print(f"  Share this with the project owner:")
    print(f'  Get-Content "{SSH_KEY}.pub"')
    sys.exit(1)
except Exception as exc:
    print(f"✗ Failed to connect to FIT server: {exc}")
    sys.exit(1)

# Step 2: Print system info
print("\n" + "=" * 70)
print("SYSTEM RUNNING")
print("=" * 70)
print("\nData available at:")
print(f"  • JSON file: {PROJECT_DIR / 'live_state.json'}")
print("  • API: http://localhost:5000/api/cache/all")
print("  • Status: http://localhost:5000/api/status")
print("\nPress Ctrl+C to stop")
print("=" * 70 + "\n")

# Step 3: Start api_server.py locally
print("[2/2] Starting api_server.py locally...")
print("-" * 70)

if not (PROJECT_DIR / "api_server.py").exists():
    print("✗ api_server.py not found")
    sys.exit(1)

api_process = subprocess.Popen(
    [sys.executable, "api_server.py"],
    cwd=PROJECT_DIR
)

print("✓ api_server.py started\n")

try:
    api_process.wait()
except KeyboardInterrupt:
    print("\n\nShutting down...")
    api_process.terminate()
    api_process.wait(timeout=5)
    channel.close()
    ssh.close()
    print("Done.")
    sys.exit(0)