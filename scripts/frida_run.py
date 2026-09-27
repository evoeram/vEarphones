#!/usr/bin/env python3
"""Frida runner: spawn com.vivo.vivotws, inject hooks, resume, capture output."""
import frida
import sys
import time
import os

PACKAGE = "com.vivo.vivotws"
SCRIPT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frida_full_firmware.js")

def on_message(message, data):
    if message["type"] == "send":
        print(f"[SEND] {message['payload']}")
    elif message["type"] == "error":
        print(f"[ERROR] {message.get('description', message)}")
        if "stack" in message:
            print(message["stack"])

def main():
    print(f"[*] Connecting to USB device...")
    device = frida.get_usb_device(timeout=10)
    print(f"[*] Device: {device}")

    print(f"[*] Spawning {PACKAGE}...")
    pid = device.spawn([PACKAGE])
    print(f"[*] Spawned PID: {pid}")

    print(f"[*] Attaching...")
    session = device.attach(pid)

    print(f"[*] Loading script from {SCRIPT_PATH}...")
    with open(SCRIPT_PATH, "r", encoding="utf-8") as f:
        script_code = f.read()

    script = session.create_script(script_code)
    script.on("message", on_message)
    script.load()

    print(f"[*] Resuming process...")
    device.resume(pid)

    print("[*] Process resumed. Hooks are active.")
    print("[*] Now open the app on your phone and trigger 'Check for updates'.")
    print("[*] Press Ctrl+C to stop.\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[*] Detaching...")
        session.detach()
        print("[*] Done.")

if __name__ == "__main__":
    main()
