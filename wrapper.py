#!/usr/bin/env python3
"""
IoT Mesh System Wrapper
One command starts everything: bridge.py on FIT server + api_server.py locally
Person B just runs: python wrapper.py
"""

import subprocess
import threading
import time
import sys
import getpass
from pathlib import Path

PROJECT_DIR = Path(__file__).parent

print("\n" + "=" * 70)
print("IoT Mesh System Wrapper")
print("=" * 70)

# Get FIT password from user (once)
print("\n[Setup] FIT Server Credentials")
print("-" * 70)
fit_password = getpass.getpass("FIT account password (sray): ")

# Step 1: SSH to FIT and start bridge.py in background
print("\n[1/2] Starting bridge.py on FIT server...")
print("-" * 70)

try:
    import paramiko
    
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    # Connect with password auth
    ssh.connect(
        "grenoble.iot-lab.info",
        username="sray",
        password=fit_password,
        timeout=10
    )
    
    # Start bridge.py in background (nohup so it survives SSH disconnect)
    stdin, stdout, stderr = ssh.exec_command("nohup python3 bridge.py > bridge.log 2>&1 &")
    time.sleep(1)
    ssh.close()
    
    print("✓ bridge.py started on FIT server (background)")
    
except ImportError:
    print("✗ paramiko not installed")
    print("   Run: py -m pip install paramiko")
    sys.exit(1)
except paramiko.AuthenticationException:
    print("✗ Authentication failed. Check your FIT password.")
    sys.exit(1)
except Exception as exc:
    print(f"✗ Failed to connect to FIT server: {exc}")
    sys.exit(1)

# Step 2: Start api_server.py locally with visible output
print("\n[2/2] Starting api_server.py locally...")
print("-" * 70)

if not (PROJECT_DIR / "api_server.py").exists():
    print("✗ api_server.py not found")
    sys.exit(1)

# Start with visible output
api_process = subprocess.Popen(
    [sys.executable, "api_server.py"],
    cwd=PROJECT_DIR
)

print("✓ api_server.py started\n")
print("=" * 70)
print("SYSTEM RUNNING")
print("=" * 70)
print("\nData available at:")
print(f"  • JSON file: {PROJECT_DIR / 'live_state.json'}")
print("  • API: http://localhost:5000/api/cache/all")
print("  • Status: http://localhost:5000/api/status")
print("\nPress Ctrl+C to stop")
print("=" * 70 + "\n")

try:
    api_process.wait()
except KeyboardInterrupt:
    print("\n\nShutting down api_server.py...")
    api_process.terminate()
    api_process.wait(timeout=5)
    print("Done.")
    sys.exit(0)
