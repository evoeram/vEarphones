#!/usr/bin/env python3
"""Запуск Frida скрипта для перехвата BLE/VIPC/AES трафика vivo TWS APK."""
import frida
import sys
import time

SCRIPT_PATH = r"C:\Users\User\Desktop\vEarphones\frida_vipc_intercept.js"
PACKAGE = "com.vivo.vivotws"

def on_message(message, data):
    if message["type"] == "send":
        print(f"[SEND] {message['payload']}")
    elif message["type"] == "error":
        print(f"[ERROR] {message.get('description', message)}")
        if "stack" in message:
            print(f"  Stack: {message['stack'][:500]}")

def main():
    print(f"Connecting to USB device...")
    device = frida.get_usb_device(timeout=10)
    print(f"Device: {device.name}")

    # Найти процесс
    print(f"Looking for {PACKAGE}...")
    procs = [p for p in device.enumerate_processes() if PACKAGE in p.name]
    if not procs:
        print(f"Process not found, spawning {PACKAGE}...")
        pid = device.spawn([PACKAGE])
        session = device.attach(pid)
        device.resume(pid)
    else:
        pid = procs[0].pid
        print(f"Found PID: {pid}")
        session = device.attach(pid)

    print(f"Loading script: {SCRIPT_PATH}")
    with open(SCRIPT_PATH, "r", encoding="utf-8") as f:
        script_code = f.read()

    script = session.create_script(script_code)
    script.on("message", on_message)
    script.load()
    print("Script loaded! Waiting for BLE activity...")
    print("Use the vivo TWS app to interact with earphones.")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping...")
        session.detach()

if __name__ == "__main__":
    main()
