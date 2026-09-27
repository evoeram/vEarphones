#!/usr/bin/env python3
"""Запуск Frida перехвата с сохранением вывода в файл.
Запускает frida CLI в фоне, пишет весь вывод в frida_capture.log.
"""
import subprocess
import sys
import time
import os
import threading

SCRIPT_PATH = r"C:\Users\User\Desktop\vEarphones\frida_ble_intercept.js"
LOG_PATH = r"C:\Users\User\Desktop\vEarphones\frida_capture.log"

def find_vivo_pid():
    """Находит PID com.vivo.vivotws через frida-ps."""
    r = subprocess.run(['frida-ps', '-U', '-a'], capture_output=True, text=True, timeout=10)
    for line in r.stdout.split('\n'):
        if 'com.vivo.vivotws' in line and ':ui' not in line:
            parts = line.split()
            for p in parts:
                if p.isdigit():
                    return int(p)
    return None

def main():
    pid = find_vivo_pid()
    if not pid:
        print("vivo APK not found! Launching...")
        ADB = r'C:\Users\User\AppData\Local\Android\Sdk\platform-tools\adb.exe'
        subprocess.run([ADB, 'shell', 'am', 'start', '-n',
                       'com.vivo.vivotws/.home.guide.ThirdAppGuideActivity'],
                      capture_output=True, timeout=10)
        time.sleep(3)
        pid = find_vivo_pid()

    if not pid:
        print("ERROR: Could not find vivo APK process")
        sys.exit(1)

    print(f"Found vivo APK PID: {pid}")
    print(f"Starting Frida intercept...")
    print(f"Log file: {LOG_PATH}")
    print(f"Press Ctrl+C to stop\n")

    # Открываем лог файл
    log_file = open(LOG_PATH, 'w', encoding='utf-8')

    def log_and_print(msg):
        log_file.write(msg + '\n')
        log_file.flush()
        print(msg, flush=True)

    # Запускаем frida
    proc = subprocess.Popen(
        ['frida', '-U', '-p', str(pid), '-l', SCRIPT_PATH],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        bufsize=1, universal_newlines=True
    )

    try:
        while True:
            line = proc.stdout.readline()
            if not line:
                if proc.poll() is not None:
                    break
                time.sleep(0.1)
                continue
            line = line.rstrip()
            if line:
                log_and_print(line)
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        proc.terminate()
        log_file.close()
        print(f"\nLog saved to: {LOG_PATH}")

if __name__ == "__main__":
    main()
