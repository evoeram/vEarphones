#!/usr/bin/env python3
"""
Gaia/BES OTA протокол зонд для vivo TWS 5i (BES2710).

Использует формат BLE-пакета из APK: [opcode:1B][length:2B LE][payload]
И V1V2 формат: [vendor:2B LE][command:2B LE][data]

Также пробует:
  - MTU negotiation
  - Service 00000837 (GAIA_NEO / TOTA)
  - Service 00001100 (SPP-подобный канал)
  - Разные write types (response=True/False)
  - Длительное ожидание notifications (5 сек)
"""

import asyncio
import struct
import sys
import time
from typing import Optional

# BLE UUIDs из K9/a.smali и h5.1/e.smali
TOTA_SERVICE = "00000837-0000-1000-8000-00805f9b34fb"
TOTA_CHAR    = "00000838-d102-11e1-9b23-00025b00a5a5"

SPP_SERVICE  = "00001100-d102-11e1-9b23-00025b00a5a5"
SPP_CMD_CHAR = "00001101-d102-11e1-9b23-00025b00a5a5"
SPP_RX_CHAR  = "00001102-d102-11e1-9b23-00025b00a5a5"
SPP_RW_CHAR  = "00001103-d102-11e1-9b23-00025b00a5a5"

CCCD_UUID = "00002902-0000-1000-8000-00805f9b34fb"

MAC = "AC:40:1E:C0:BC:85"


def make_bes_ota_packet(opcode: int, payload: bytes = b'') -> bytes:
    """BES OTA формат: [opcode:1B][length:2B LE][payload]."""
    return struct.pack('<BH', opcode, len(payload)) + payload


def make_v1v2_packet(vendor: int, command: int, data: bytes = b'') -> bytes:
    """V1V2 формат: [vendor:2B LE][command:2B LE][data]."""
    return struct.pack('<HH', vendor, command) + data


def hexdump(data: bytes, prefix: str = "  ", max_len: int = 64) -> str:
    d = data[:max_len]
    s = ' '.join(f'{b:02x}' for b in d)
    if len(data) > max_len:
        s += f' ... ({len(data)} bytes)'
    return f"{prefix}{s}"


async def find_device(mac: str, attempts: int = 5, timeout: float = 15.0):
    """Поиск устройства с повторами."""
    from bleak import BleakScanner
    for i in range(attempts):
        print(f"[*] Scan {i+1}/{attempts} for {mac}...")
        dev = await BleakScanner.find_device_by_address(mac, timeout=timeout)
        if dev:
            print(f"[+] Found: {dev.name} ({dev.address})")
            return dev
        await asyncio.sleep(2)
    return None


async def probe_service(bleak_client, service_uuid: str, char_uuid: str,
                        char_name: str, verbose: bool = True):
    """Зондирование одного service/characteristic."""
    from bleak import BleakGATTCharacteristic

    print(f"\n{'='*60}")
    print(f"[*] Service: {service_uuid}")
    print(f"    Char: {char_uuid} ({char_name})")
    print(f"{'='*60}")

    # Найти characteristic
    char = None
    for svc in bleak_client.services:
        if str(svc.uuid).lower() == service_uuid.lower():
            for ch in svc.characteristics:
                if str(ch.uuid).lower() == char_uuid.lower():
                    char = ch
                    break
            break

    if not char:
        print(f"[-] Characteristic not found!")
        return

    props = char.properties
    print(f"    Properties: {', '.join(props)}")

    # Enable notifications/indications
    rx_data = bytearray()
    rx_event = asyncio.Event()

    def notification_handler(sender, data: bytearray):
        rx_data.extend(data)
        rx_event.set()
        if verbose:
            print(f"  [RX] {len(data)} bytes: {hexdump(bytes(data))}")

    has_notify = 'notify' in props or 'indicate' in props
    if has_notify:
        try:
            await bleak_client.start_notify(char_uuid, notification_handler)
            print(f"[+] Notifications enabled")
            await asyncio.sleep(0.5)
        except Exception as e:
            print(f"[-] Notify failed: {e}")

    # Тестовые пакеты
    test_packets = []

    # 1. BES OTA SYNC (opcode=1, пустой payload)
    test_packets.append(("BES-OTA SYNC (op=1)", make_bes_ota_packet(1)))

    # 2. BES OTA SYNC с version=4
    test_packets.append(("BES-OTA SYNC v4 (op=1, ver=4)", make_bes_ota_packet(1, b'\x04')))

    # 3. BES OTA GET_INFO (opcode=0xFF или 0x00)
    test_packets.append(("BES-OTA GET_INFO (op=0)", make_bes_ota_packet(0)))

    # 4. Gaia V1V2 INIT (vendor=10, cmd=0x0300=768)
    test_packets.append(("Gaia INIT (v=10, c=0x0300)", make_v1v2_packet(10, 0x0300)))

    # 5. Gaia V1V2 GET_VERSION (vendor=10, cmd=0x0001)
    test_packets.append(("Gaia GET_VER (v=10, c=1)", make_v1v2_packet(10, 1)))

    # 6. Gaia V1V2 GET_CAPS (vendor=10, cmd=0x0002)
    test_packets.append(("Gaia GET_CAPS (v=10, c=2)", make_v1v2_packet(10, 2)))

    # 7. vivo V1V2 (vendor=27, cmd=0x0201=513) — GET_DEVICE_INFO
    test_packets.append(("vivo GET_DEV (v=27, c=513)", make_v1v2_packet(27, 513)))

    # 8. vivo V1V2 (vendor=27, cmd=0x0209=521) — первый из APK
    test_packets.append(("vivo cmd 521 (v=27, c=521)", make_v1v2_packet(27, 521)))

    # 9. vivo V1V2 (vendor=27, cmd=0x0202=514)
    test_packets.append(("vivo cmd 514 (v=27, c=514)", make_v1v2_packet(27, 514)))

    # 10. vivo V1V2 (vendor=27, cmd=0x0114=276) — OTA start
    test_packets.append(("vivo OTA (v=27, c=276)", make_v1v2_packet(27, 276)))

    # 11. TOTA HEAD/TAIL CONN_INITIATE
    from ble_flash_dump import tota_pack, tota_make_payload, OP_TOTA_CONN_INITIATE
    import os
    rand_b = os.urandom(32)
    initiate_param = bytes([32]) + rand_b
    payload = tota_make_payload(OP_TOTA_CONN_INITIATE, initiate_param)
    test_packets.append(("TOTA CONN_INIT", tota_pack(payload)))

    # 12. TOTA HEAD/TAIL GENERAL_INFO (без шифрования)
    from ble_flash_dump import OP_TOTA_GENERAL_INFO_CMD
    payload = tota_make_payload(OP_TOTA_GENERAL_INFO_CMD, b'')
    test_packets.append(("TOTA GEN_INFO", tota_pack(payload)))

    # 13. Raw opcode 0x55 (generic test)
    test_packets.append(("Raw 0x55 0x00 0x00", b'\x55\x00\x00'))

    # 14. BES OTA ERASE_FLASH (opcode=2)
    test_packets.append(("BES-OTA ERASE (op=2)", make_bes_ota_packet(2)))

    for desc, pkt in test_packets:
        rx_data.clear()
        rx_event.clear()

        print(f"\n  [{desc}]")
        print(f"  TX ({len(pkt)}B): {hexdump(pkt)}")

        # Try write with response first, then without
        write_ok = False
        for resp_mode in [True, False]:
            try:
                await bleak_client.write_gatt_char(char_uuid, pkt, response=resp_mode)
                mode_str = "WR" if resp_mode else "WR_NO_RESP"
                print(f"  Write ({mode_str}): OK")
                write_ok = True
                break
            except Exception as e:
                mode_str = "WR" if resp_mode else "WR_NO_RESP"
                print(f"  Write ({mode_str}): {e}")

        if not write_ok:
            continue

        # Ждём ответ 5 секунд
        try:
            await asyncio.wait_for(rx_event.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            pass

        if rx_data:
            print(f"  [RX] {len(rx_data)} bytes: {hexdump(bytes(rx_data), max_len=128)}")
            # Попытка разобрать как V1V2
            if len(rx_data) >= 4:
                vendor, cmd = struct.unpack_from('<HH', rx_data, 0)
                is_response = bool(cmd & 0x8000)
                cmd_clean = cmd & 0x7FFF
                print(f"  → V1V2: vendor={vendor} cmd=0x{cmd_clean:04x} response={is_response} data={len(rx_data)-4}B")
            # Попытка разобрать как BES OTA
            if len(rx_data) >= 3:
                opcode, length = struct.unpack_from('<BH', rx_data, 0)
                print(f"  → BES-OTA: op={opcode} len={length} data={len(rx_data)-3}B")
        else:
            print(f"  [-] No response (5s timeout)")

        await asyncio.sleep(0.3)

    # Дополнительно: слушать 3 секунды после всех запросов
    print(f"\n  [*] Listening 3s for async responses...")
    rx_data.clear()
    rx_event.clear()
    try:
        await asyncio.wait_for(rx_event.wait(), timeout=3.0)
        print(f"  [RX] {len(rx_data)} bytes: {hexdump(bytes(rx_data), max_len=128)}")
    except asyncio.TimeoutError:
        print(f"  [-] No async response")

    if has_notify:
        try:
            await bleak_client.stop_notify(char_uuid)
        except:
            pass


async def main():
    from bleak import BleakClient

    print(f"=== vivo TWS 5i Gaia/BES-OTA Protocol Probe ===")
    print(f"MAC: {MAC}")

    device = await find_device(MAC)
    if not device:
        print("[!] Device not found")
        return

    print(f"[*] Connecting...")
    async with BleakClient(device, timeout=30.0) as client:
        print(f"[+] Connected! is_connected={client.is_connected}")

        # MTU negotiation
        try:
            mtu = client._backend._requester.max_pdu_size
            print(f"[BLE] MTU: {mtu}")
        except:
            print(f"[BLE] MTU: unknown")

        # Попытка запросить больший MTU
        try:
            # bleak WinRT backend не имеет прямого метода requestMtu,
            # но он автоматически negociates при подключении
            pass
        except:
            pass

        # Показать все services
        print(f"\n[*] Services:")
        for svc in client.services:
            print(f"  Service: {svc.uuid}")
            for ch in svc.characteristics:
                print(f"    Char: {ch.uuid} [{', '.join(ch.properties)}]")

        # Зондировать TOTA service
        await probe_service(client, TOTA_SERVICE, TOTA_CHAR, "TOTA/GAIA_NEO")

        # Зондировать SPP CMD char
        await probe_service(client, SPP_SERVICE, SPP_CMD_CHAR, "SPP-CMD")

        # Зондировать SPP RW char (write-without-response)
        await probe_service(client, SPP_SERVICE, SPP_RW_CHAR, "SPP-RW")

        print(f"\n[*] Probe complete.")


if __name__ == '__main__':
    asyncio.run(main())
