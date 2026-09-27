#!/usr/bin/env python3
"""
BLE Flash Dump для vivo TWS 5i (BES2710)
=========================================
Чтение прошивки с наушников через BLE TOTA v2 протокол.

Требования:
  pip install bleak pycryptodome

Использование:
  python ble_flash_dump.py --mac AC:40:1E:C0:BC:85 --output flash_dump.bin
  python ble_flash_dump.py --mac AC:40:1E:C0:BC:85 --output flash_dump.bin --start 0x000000 --size 0x400000
  python ble_flash_dump.py --scan
  python ble_flash_dump.py --mac AC:40:1E:C0:BC:85 --info    # только general info

Протокол TOTA v2 (из BES SDK, services/tota_v2/):
  1. BLE GATT connect
  2. Enable notifications (CCCD)
  3. Handshake: CONN_INITIATE(0x1001) → CONN_RESPONSE(0x1002) → CONN_CONFIRM(0x1003)
  4. После handshake: AES-128-CBC шифрование всех команд
  5. READ_FLASH_CMD(0x6202): {address:u32LE, length:u16LE} → ответ {address:u32, length:u16, data[]}
  6. Дамп: чтение по 4096 байт, 0x000000–0x3FFFFF (4 MB)

Пакет TOTA (app_tota_tx_pack / app_tota_rx_unpack):
  [HEAD="HEAD"(4B)] [bufLen:u32LE] [data:bufLen] [CRC32:u32LE] [TAIL="TAIL"(4B)]
  CRC32 — стандартный (zlib, poly 0xEDB88320), по data

Payload внутри data (APP_TOTA_CMD_PAYLOAD_T):
  [cmdCode:u16LE] [paramLen:u16LE] [param:paramLen]

Шифрование (app_tota_encrypt.cpp):
  AES-128-CBC, key = hash_key[0,2,4,...30] (16 байт из SHA256), IV = 00 01 ... 0F
  Дополняется нулями до кратного 16.

Handshake (app_tota_conn.cpp):
  Клиент → CONN_INITIATE: {length:u8, random_key[length]}
  Наушник → CONN_RESPONSE: {length:u8, random_key[length]}
  Обе стороны: SHA256(combine(random_a, random_b)) → hash_key (32B)
  combine: для каждого байта i: _generate_random_algorithm(i, a[i], b[i])
    op = i % 6: 0=a+b, 1=a*b, 2=a&b, 3=a|b, 4=a^b, 5=a*a+b*b
  Выравнивание: коротший ключ дополняется нулями до длины длинного
  Клиент → CONN_CONFIRM: {length:u8, hash_key[32]} (отправляем hash_key)
  Наушник проверяет: memcmp(свой hash_key, полученный) → "connect success."
"""

import argparse
import asyncio
import hashlib
import struct
import sys
import time
import os
from typing import Optional, Tuple, List

# ─── TOTA Constants ───────────────────────────────────────────────────────────

TOTA_HEAD = b"HEAD"
TOTA_TAIL = b"TAIL"
TOTA_HEAD_SIZE = 4
TOTA_LEN_SIZE = 4
TOTA_CRC_SIZE = 4
TOTA_TAIL_SIZE = 4
TOTA_PACKET_VERIFY_SIZE = TOTA_HEAD_SIZE + TOTA_LEN_SIZE + TOTA_CRC_SIZE + TOTA_TAIL_SIZE  # 16

MAX_FLASH_HANDLE_SIZE = 4096

# Command codes (app_tota_cmd_code.h)
OP_TOTA_STRING              = 0x1000
OP_TOTA_CONN_INITIATE       = 0x1001
OP_TOTA_CONN_RESPONSE       = 0x1002
OP_TOTA_CONN_CONFIRM        = 0x1003
OP_TOTA_RESPONSE_TO_CMD     = 0x6000
OP_TOTA_READ_FLASH_CMD      = 0x6202
OP_TOTA_GENERAL_INFO_CMD    = 0x6300
OP_TOTA_EXCHANGE_MTU_CMD    = 0x6301
OP_TOTA_GET_DUMP_INFO_CMD   = 0x6307

# Connection status
TOTA_CONNECTED    = 0
TOTA_SHAKE_HANDED = 1
TOTA_DISCONNECTED = 0xFF

# AES
AES_KEY_SIZE = 16
AES_IV = bytes(range(16))  # 00 01 02 ... 0F
HASH_KEY_SIZE = 32
MAX_RANDOM_KEY_SIZE = 128

# BLE UUIDs — два варианта:
#  SDK default (ble_tota.c): 86868686-... / 97979797-...
#  vivo APK (K9/a.java):     00000837-... / 00000838-d102-11e1-9b23-...
BLE_UUIDS = {
    "sdk": {
        "service":      "86868686-8686-8686-8686-868686868686",
        "characteristic": "97979797-9797-9797-9797-979797979797",
    },
    "vivo": {
        "service":      "00000837-0000-1000-8000-00805f9b34fb",
        "characteristic": "00000838-d102-11e1-9b23-00025b00a5a5",
    },
}
CCCD_UUID = "00002902-0000-1000-8000-00805f9b34fb"

# ─── CRC32 (zlib, poly 0xEDB88320) — как crc32_c в BES SDK ────────────────────

import zlib

def crc32_c(data: bytes) -> int:
    """CRC32 как в BES SDK (crc_c.c) — стандартный zlib CRC32."""
    return zlib.crc32(data) & 0xFFFFFFFF

# ─── AES-128-CBC ──────────────────────────────────────────────────────────────
# Используем библиотеку `cryptography` (доступна), с fallback на `pycryptodome`.

try:
    from cryptography.hazmat.primitives.ciphers import Cipher as _CryptographyCipher
    from cryptography.hazmat.primitives.ciphers import algorithms as _crypto_algs
    from cryptography.hazmat.primitives.ciphers import modes as _crypto_modes
    from cryptography.hazmat.backends import default_backend as _crypto_backend
    HAVE_CRYPTO = True
except ImportError:
    HAVE_CRYPTO = False

try:
    from Crypto.Cipher import AES as AES_Cipher
    HAVE_PYCRYPTO = True
except ImportError:
    HAVE_PYCRYPTO = False

HAVE_AES = HAVE_CRYPTO or HAVE_PYCRYPTO


def aes_encrypt(key: bytes, iv: bytes, data: bytes) -> bytes:
    """AES-128-CBC encrypt, pad with zeros to 16-byte boundary."""
    # BES pads to next 16-byte boundary if not already aligned
    if len(data) % AES_KEY_SIZE != 0:
        padded = data + b'\x00' * (AES_KEY_SIZE - len(data) % AES_KEY_SIZE)
    else:
        padded = data

    if HAVE_CRYPTO:
        cipher = _CryptographyCipher(
            _crypto_algs.AES(key), _crypto_modes.CBC(iv),
            backend=_crypto_backend())
        enc = cipher.encryptor()
        return enc.update(padded) + enc.finalize()
    elif HAVE_PYCRYPTO:
        cipher = AES_Cipher.new(key, AES_Cipher.MODE_CBC, iv)
        return cipher.encrypt(padded)
    else:
        raise RuntimeError("No AES library available (need `cryptography` or `pycryptodome`)")


def aes_decrypt(key: bytes, iv: bytes, data: bytes) -> bytes:
    """AES-128-CBC decrypt."""
    if HAVE_CRYPTO:
        cipher = _CryptographyCipher(
            _crypto_algs.AES(key), _crypto_modes.CBC(iv),
            backend=_crypto_backend())
        dec = cipher.decryptor()
        return dec.update(data) + dec.finalize()
    elif HAVE_PYCRYPTO:
        cipher = AES_Cipher.new(key, AES_Cipher.MODE_CBC, iv)
        return cipher.decrypt(data)
    else:
        raise RuntimeError("No AES library available (need `cryptography` or `pycryptodome`)")

# ─── TOTA Packet ──────────────────────────────────────────────────────────────

def tota_pack(data: bytes) -> bytes:
    """Упаковка TOTA пакета: HEAD + bufLen + data + CRC32 + TAIL."""
    buf_len = len(data)
    crc = crc32_c(data)
    return (
        TOTA_HEAD +
        struct.pack('<I', buf_len) +
        data +
        struct.pack('<I', crc) +
        TOTA_TAIL
    )


def tota_unpack(packet: bytes) -> Optional[bytes]:
    """Распаковка TOTA пакета. Возвращает data или None."""
    if len(packet) < TOTA_PACKET_VERIFY_SIZE:
        return None
    head = packet[:TOTA_HEAD_SIZE]
    if head != TOTA_HEAD:
        return None
    buf_len = struct.unpack_from('<I', packet, TOTA_HEAD_SIZE)[0]
    total = TOTA_PACKET_VERIFY_SIZE + buf_len
    if len(packet) < total:
        return None
    data = packet[TOTA_HEAD_SIZE + TOTA_LEN_SIZE : TOTA_HEAD_SIZE + TOTA_LEN_SIZE + buf_len]
    crc_stored = struct.unpack_from('<I', packet, TOTA_HEAD_SIZE + TOTA_LEN_SIZE + buf_len)[0]
    tail = packet[TOTA_HEAD_SIZE + TOTA_LEN_SIZE + buf_len + TOTA_CRC_SIZE :
                  TOTA_HEAD_SIZE + TOTA_LEN_SIZE + buf_len + TOTA_CRC_SIZE + TOTA_TAIL_SIZE]
    if tail != TOTA_TAIL:
        return None
    if crc32_c(data) != crc_stored:
        return None
    return data

# ─── TOTA Payload ─────────────────────────────────────────────────────────────

def tota_make_payload(cmd_code: int, param: bytes = b'') -> bytes:
    """Создание payload: cmdCode(2) + paramLen(2) + param."""
    return struct.pack('<HH', cmd_code, len(param)) + param


def tota_parse_payload(data: bytes) -> Tuple[int, int, bytes]:
    """Парсинг payload: (cmdCode, paramLen, param)."""
    if len(data) < 4:
        return (0, 0, b'')
    cmd_code, param_len = struct.unpack_from('<HH', data, 0)
    param = data[4:4 + param_len]
    return (cmd_code, param_len, param)

# ─── Handshake crypto ─────────────────────────────────────────────────────────

def _generate_random_algorithm(i: int, a: int, b: int) -> int:
    """Алгоритм из app_tota_conn.cpp."""
    op = i % 6
    if op == 0: return (a + b) & 0xFF
    elif op == 1: return (a * b) & 0xFF
    elif op == 2: return (a & b) & 0xFF
    elif op == 3: return (a | b) & 0xFF
    elif op == 4: return (a ^ b) & 0xFF
    elif op == 5: return (a * a + b * b) & 0xFF
    return 0


def calculate_hash_key(random_a: bytes, random_b: bytes) -> bytes:
    """Вычисление hash_key из двух random keys (app_tota_conn.cpp)."""
    # Align lengths
    len_a = len(random_a)
    len_b = len(random_b)
    if len_a > len_b:
        random_b = random_b + b'\x00' * (len_a - len_b)
    elif len_a < len_b:
        random_a = random_a + b'\x00' * (len_b - len_a)
    key_len = max(len_a, len_b)
    # Combine
    combined = bytes(_generate_random_algorithm(i, random_a[i], random_b[i]) for i in range(key_len))
    # SHA256
    return hashlib.sha256(combined).digest()


def derive_aes_key(hash_key: bytes) -> bytes:
    """Извлечение AES key из hash_key: hash_key[0,2,4,...30]."""
    return bytes(hash_key[2 * i] for i in range(AES_KEY_SIZE))

# ─── BLE TOTA Client ──────────────────────────────────────────────────────────

class TOTAClient:
    def __init__(self, mac: str, uuid_set: str = "auto"):
        self.mac = mac
        self.uuid_set = uuid_set
        self.client = None
        self.char_uuid = None
        self.service_uuid = None
        self.aes_key = None
        self.connect_status = TOTA_DISCONNECTED
        self._rx_buffer = bytearray()
        self._response_event = asyncio.Event()
        self._response_data = None
        self._notification_data = bytearray()
        self._log_level = 1  # 0=quiet, 1=normal, 2=verbose

    def log(self, msg: str, level: int = 1):
        if self._log_level >= level:
            print(msg)

    def hexdump(self, data: bytes, prefix: str = "  ", max_len: int = 64):
        if self._log_level < 2:
            return
        d = data[:max_len]
        hex_str = ' '.join(f'{b:02x}' for b in d)
        if len(data) > max_len:
            hex_str += f' ... ({len(data)} bytes total)'
        print(f"{prefix}{hex_str}")

    async def connect(self):
        """BLE GATT подключение и поиск TOTA service."""
        from bleak import BleakScanner, BleakClient
        # На Windows bleak не всегда подключается по строке MAC —
        # используем find_device_by_address для получения объекта устройства.
        # Наушники могут уходить в sleep — делаем несколько попыток сканирования.
        device = None
        for scan_attempt in range(5):
            print(f"[*] Scanning for {self.mac} (attempt {scan_attempt+1}/5)...")
            device = await BleakScanner.find_device_by_address(self.mac, timeout=15.0)
            if device:
                break
            await asyncio.sleep(2)
        if not device:
            raise RuntimeError(f"Device {self.mac} not found in BLE scan after 5 attempts")
        print(f"[+] Found: {device.name} ({device.address})")
        self.client = BleakClient(device, timeout=30.0)
        await self.client.connect()
        self.log(f"[BLE] Connected to {self.mac}")

        # Получить список services (bleak 3.x: свойство, bleak 0.x: get_services())
        services = []
        try:
            svc_obj = self.client.services
            if isinstance(svc_obj, dict):
                services = list(svc_obj.values())
            else:
                services = list(svc_obj)
        except AttributeError:
            try:
                services = list(await self.client.get_services())
            except AttributeError:
                services = []

        # ВСЕГДА показывать все services
        self.log(f"[BLE] Found {len(services)} services:", 1)
        for service in services:
            self.log(f"  Service: {service.uuid}", 1)
            for char in service.characteristics:
                props = ','.join(char.properties)
                self.log(f"    Char: {char.uuid} [{props}]", 1)

        # Найти TOTA service — попробовать все UUID sets
        uuid_sets_to_try = []
        if self.uuid_set == "auto":
            uuid_sets_to_try = ["vivo", "sdk"]
        else:
            uuid_sets_to_try = [self.uuid_set]

        found = False
        for set_name in uuid_sets_to_try:
            uuids = BLE_UUIDS[set_name]
            svc_uuid = uuids["service"]
            char_uuid = uuids["characteristic"]
            for service in services:
                if str(service.uuid).lower() == svc_uuid.lower():
                    for char in service.characteristics:
                        if str(char.uuid).lower() == char_uuid.lower():
                            self.service_uuid = svc_uuid
                            self.char_uuid = char_uuid
                            self.log(f"[BLE] Using service ({set_name}): {svc_uuid}")
                            self.log(f"[BLE] Characteristic: {char_uuid}")
                            found = True
                            break
                    if found:
                        break
            if found:
                break

        if not found:
            # Fallback: взять первый writable+notify characteristic из любого service
            self.log("[BLE] TOTA UUID not found, trying first write+notify char...", 1)
            for service in services:
                for char in service.characteristics:
                    props = char.properties
                    if 'write' in props and 'notify' in props:
                        self.service_uuid = str(service.uuid)
                        self.char_uuid = str(char.uuid)
                        self.log(f"[BLE] Fallback: {self.char_uuid} [{','.join(props)}]", 1)
                        found = True
                        break
                if found:
                    break

        if not found:
            raise RuntimeError("No writable+notify characteristic found")

        # Enable notifications
        try:
            await self.client.start_notify(self.char_uuid, self._notification_handler)
        except TypeError:
            self.client.start_notify(self.char_uuid, self._notification_handler)
        self.log("[BLE] Notifications enabled")

    async def _notification_handler(self, sender, data: bytearray):
        """Обработка входящих BLE notifications."""
        self.log(f"[BLE RX] {len(data)} bytes", 2)
        self.hexdump(bytes(data), "  ")

        # Добавить в буфер
        self._rx_buffer.extend(data)

        # Попытка распаковать TOTA пакет
        while len(self._rx_buffer) >= TOTA_PACKET_VERIFY_SIZE:
            # Проверка HEAD
            if self._rx_buffer[:TOTA_HEAD_SIZE] != TOTA_HEAD:
                # Попробовать найти HEAD в буфере
                idx = self._rx_buffer.find(TOTA_HEAD)
                if idx < 0:
                    self._rx_buffer.clear()
                    return
                del self._rx_buffer[:idx]

            if len(self._rx_buffer) < TOTA_HEAD_SIZE + TOTA_LEN_SIZE:
                break

            buf_len = struct.unpack_from('<I', self._rx_buffer, TOTA_HEAD_SIZE)[0]
            total_size = TOTA_PACKET_VERIFY_SIZE + buf_len

            if buf_len > 65536:
                self.log(f"[TOTA] Invalid buf_len: {buf_len}, clearing buffer")
                self._rx_buffer.clear()
                break

            if len(self._rx_buffer) < total_size:
                self.log(f"[TOTA] Partial packet: have {len(self._rx_buffer)}, need {total_size}", 2)
                break

            # Извлечь полный пакет
            packet = bytes(self._rx_buffer[:total_size])
            del self._rx_buffer[:total_size]

            unpacked = tota_unpack(packet)
            if unpacked is None:
                self.log("[TOTA] Failed to unpack packet")
                continue

            self.log(f"[TOTA RX] payload: {len(unpacked)} bytes", 2)
            self.hexdump(unpacked, "  ")

            # Если зашифровано — расшифровать
            if self.connect_status == TOTA_SHAKE_HANDED and self.aes_key:
                try:
                    decrypted = aes_decrypt(self.aes_key, AES_IV, unpacked)
                    self.log(f"[TOTA RX] decrypted: {len(decrypted)} bytes", 2)
                    self.hexdump(decrypted, "  ")
                    unpacked = decrypted
                except Exception as e:
                    self.log(f"[TOTA] Decrypt error: {e}")

            self._response_data = unpacked
            self._response_event.set()

    async def send_raw(self, data: bytes):
        """Отправка raw bytes через BLE GATT write."""
        # BLE MTU обычно 23-517, payload = MTU - 3
        # Отправляем по частям если нужно
        chunk_size = 180  # безопасный размер для большинства MTU
        offset = 0
        while offset < len(data):
            chunk = data[offset:offset + chunk_size]
            await self.client.write_gatt_char(self.char_uuid, chunk, response=False)
            offset += len(chunk)
            if offset < len(data):
                await asyncio.sleep(0.02)  # небольшая задержка между чанками

    async def send_tota(self, payload: bytes, encrypt: bool = False) -> bytes:
        """Отправка TOTA пакета и ожидание ответа."""
        if encrypt and self.aes_key:
            payload = aes_encrypt(self.aes_key, AES_IV, payload)
            self.log(f"[TOTA TX] encrypted: {len(payload)} bytes", 2)
        elif encrypt and not self.aes_key:
            self.log("[TOTA] WARNING: encrypt requested but no AES key!")

        packet = tota_pack(payload)
        self.log(f"[TOTA TX] packet: {len(packet)} bytes (payload {len(payload)})", 2)
        self.hexdump(packet, "  ")

        self._response_event.clear()
        self._response_data = None

        await self.send_raw(packet)

        # Ждать ответ
        try:
            await asyncio.wait_for(self._response_event.wait(), timeout=10.0)
        except asyncio.TimeoutError:
            self.log("[TOTA] Timeout waiting for response")
            return b''

        return self._response_data or b''

    async def send_command(self, cmd_code: int, param: bytes = b'', encrypt: bool = False) -> bytes:
        """Отправка TOTA команды и возв ответа (payload data)."""
        payload = tota_make_payload(cmd_code, param)
        resp = await self.send_tota(payload, encrypt=encrypt)

        if not resp:
            return b''

        rcmd, rlen, rparam = tota_parse_payload(resp)
        self.log(f"[TOTA] Response: cmd=0x{rcmd:04x} len={rlen}")
        return rparam

    async def handshake(self) -> bool:
        """TOTA handshake: CONN_INITIATE → CONN_RESPONSE → CONN_CONFIRM."""
        import os as _os

        # Генерируем random key B (клиент)
        rand_len = _os.urandom(1)[0] % (MAX_RANDOM_KEY_SIZE + 1)
        if rand_len < 16:
            rand_len += 16
        random_b = _os.urandom(rand_len)

        # CONN_INITIATE: отправляем {length:u8, random_key[length]}
        initiate_param = bytes([rand_len]) + random_b
        self.log(f"[TOTA] Handshake: CONN_INITIATE (random_b len={rand_len})")

        # Отправить без шифрования
        resp = await self.send_command(OP_TOTA_CONN_INITIATE, initiate_param, encrypt=False)
        if not resp:
            self.log("[TOTA] Handshake: no response to CONN_INITIATE")
            return False

        # Разобрать ответ: CONN_RESPONSE с random_a
        if len(resp) < 1:
            self.log("[TOTA] Handshake: response too short")
            return False

        rand_a_len = resp[0]
        if len(resp) < 1 + rand_a_len:
            self.log(f"[TOTA] Handshake: response missing random_a (len={rand_a_len}, got {len(resp)})")
            return False
        random_a = resp[1:1 + rand_a_len]

        self.log(f"[TOTA] Handshake: got random_a len={rand_a_len}")
        self.hexdump(random_a, "  random_a: ", 32)

        # Вычислить hash_key
        hash_key = calculate_hash_key(random_a, random_b)
        self.log(f"[TOTA] hash_key: {hash_key.hex()}")

        # derive AES key
        self.aes_key = derive_aes_key(hash_key)
        self.log(f"[TOTA] AES key: {self.aes_key.hex()}")

        # CONN_CONFIRM: отправляем hash_key
        # Структура: {length:u8, hash_key[32]}
        confirm_param = bytes([HASH_KEY_SIZE]) + hash_key
        self.log("[TOTA] Handshake: CONN_CONFIRM")

        resp = await self.send_command(OP_TOTA_CONN_CONFIRM, confirm_param, encrypt=False)
        if resp:
            # Ожидаем "connect success." или подобное
            try:
                msg = resp.decode('utf-8', errors='replace')
                self.log(f"[TOTA] Handshake response: {msg}")
            except:
                self.log(f"[TOTA] Handshake response (raw): {resp.hex()}")

        self.connect_status = TOTA_SHAKE_HANDED
        self.log("[TOTA] Handshake complete — encrypted channel established")
        return True

    async def read_flash(self, address: int, length: int) -> bytes:
        """Чтение flash по адресу. OP_TOTA_READ_FLASH_CMD."""
        # TOTA_READ_FLASH_STRUCT_T: {address:u32, length:u16}
        param = struct.pack('<IH', address, length)
        self.log(f"[TOTA] READ_FLASH: addr=0x{address:08x} len={length}")

        resp = await self.send_command(OP_TOTA_READ_FLASH_CMD, param, encrypt=True)
        if not resp:
            self.log(f"[TOTA] READ_FLASH: no response for addr=0x{address:08x}")
            return b''

        # TOTA_FLASH_DATA_T: {address:u32, length:u16, data[]}
        if len(resp) < 6:
            self.log(f"[TOTA] READ_FLASH: response too short ({len(resp)} bytes)")
            return b''

        resp_addr, resp_len = struct.unpack_from('<IH', resp, 0)
        data = resp[6:6 + resp_len]
        self.log(f"[TOTA] READ_FLASH: got addr=0x{resp_addr:08x} len={resp_len}", 2)
        return data

    async def get_general_info(self) -> bytes:
        """Получение general info: BT name, BLE name, battery, firmware version, etc."""
        self.log("[TOTA] Getting general info...")
        return await self.send_command(OP_TOTA_GENERAL_INFO_CMD, b'', encrypt=True)

    async def disconnect(self):
        """Отключение."""
        if self.client:
            try:
                await self.client.stop_notify(self.char_uuid)
            except:
                pass
            try:
                await self.client.disconnect()
            except:
                pass
        self.connect_status = TOTA_DISCONNECTED
        self.log("[BLE] Disconnected")

# ─── Main ─────────────────────────────────────────────────────────────────────

async def scan_devices():
    """Сканирование BLE устройств."""
    from bleak import BleakScanner
    print("Scanning for BLE devices (10 seconds)...")
    devices = await BleakScanner.discover(timeout=10.0)
    for d in devices:
        name = d.name or "(unknown)"
        print(f"  {d.address}  {name}")
    if not devices:
        print("  No devices found.")
    return devices


async def do_handshake_and_info(client: TOTAClient) -> bool:
    """Подключение + handshake + general info."""
    await client.connect()
    await asyncio.sleep(0.5)

    ok = await client.handshake()
    if not ok:
        print("[!] Handshake failed. Trying without handshake (unencrypted mode)...")
        # Некоторые firmware могут работать без handshake для базовых команд
        client.connect_status = TOTA_CONNECTED
        return False

    await asyncio.sleep(0.3)
    return True


async def dump_flash(mac: str, output_path: str, start: int, size: int,
                     uuid_set: str = "auto", verbose: bool = False):
    """Основная функция дампа flash."""
    if not HAVE_AES:
        print("[!] No AES library available. Install one of:")
        print("[!]   pip install cryptography   (рекомендуется)")
        print("[!]   pip install pycryptodome")
        return False

    client = TOTAClient(mac, uuid_set=uuid_set)
    if verbose:
        client._log_level = 2

    try:
        await client.connect()
        await asyncio.sleep(0.5)

        # Handshake
        print("[*] Starting TOTA handshake...")
        ok = await client.handshake()
        if not ok:
            print("[!] Handshake failed.")
            print("[!] TOTA may not be compiled in this firmware,")
            print("[!] or the firmware is not in factory/test mode.")
            print("[!] Trying unencrypted commands anyway...")
            client.connect_status = TOTA_CONNECTED
        else:
            print("[+] Handshake successful!")

        await asyncio.sleep(0.3)

        # General info
        print("[*] Requesting general info...")
        info = await client.get_general_info()
        if info:
            print(f"[+] General info: {len(info)} bytes")
            client.hexdump(info, "  ", 128)
        else:
            print("[!] No general info response")

        await asyncio.sleep(0.3)

        # Flash dump
        print(f"[*] Starting flash dump: 0x{start:08x} – 0x{start+size-1:08x} ({size} bytes)")
        print(f"[*] Output: {output_path}")

        chunk_size = 4096  # MAX_FLASH_HANDLE_SIZE
        total_chunks = (size + chunk_size - 1) // chunk_size
        dumped = 0

        with open(output_path, 'wb') as f:
            f.truncate(0)  # очистить файл

            for i in range(total_chunks):
                addr = start + i * chunk_size
                remaining = size - dumped
                read_len = min(chunk_size, remaining)

                retries = 3
                data = b''
                for retry in range(retries):
                    data = await client.read_flash(addr, read_len)
                    if data:
                        break
                    print(f"[!] Retry {retry+1}/{retries} for addr=0x{addr:08x}")
                    await asyncio.sleep(0.5)

                if not data:
                    print(f"[!] Failed to read addr=0x{addr:08x} after {retries} retries")
                    # Заполнить нулями или FF
                    data = b'\xff' * read_len
                    print(f"    Filling with 0xFF")

                f.write(data)
                dumped += len(data)

                pct = dumped * 100 / size
                bar_len = 40
                filled = int(bar_len * dumped / size)
                bar = '=' * filled + '-' * (bar_len - filled)
                sys.stdout.write(f"\r[{bar}] {pct:5.1f}%  0x{addr:08x}  {dumped}/{size}")
                sys.stdout.flush()

                # Небольшая задержка между чтениями
                await asyncio.sleep(0.05)

        print()  # newline after progress bar
        print(f"[+] Flash dump complete: {dumped} bytes → {output_path}")

        # Проверка
        actual_size = os.path.getsize(output_path)
        print(f"[+] File size: {actual_size} bytes")

        return True

    except Exception as e:
        print(f"[!] Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await client.disconnect()


def make_v1v2_packet(vendor: int, command: int, data: bytes = b'') -> bytes:
    """V1V2Packet: [vendor:2B LE][command:2B LE][data]."""
    return struct.pack('<HH', vendor, command) + data


async def probe_protocol(mac: str, uuid_set: str = "auto", verbose: bool = True):
    """
    Probe: подключается, показывает все services и пробует V1V2Packet на каждом
    write-characteristic. Формат V1V2Packet: [vendor:2B LE][command:2B LE][data].
    Vendor=27 (vivo TWS), vendor=10 (Gaia). Команды из APK.
    """
    from bleak import BleakScanner, BleakClient

    print(f"[*] Scanning for {mac}...")
    device = await BleakScanner.find_device_by_address(mac, timeout=15.0)
    if not device:
        print(f"[!] Device {mac} not found")
        return
    print(f"[+] Found: {device.name} ({device.address})")

    print(f"[*] Connecting to {mac}...")

    try:
        async with BleakClient(device, timeout=30.0) as bleak_client:
            try:
                mtu = bleak_client._backend._requester.max_pdu_size
                print(f"[BLE] MTU: {mtu}")
            except Exception:
                print("[BLE] MTU: unknown")

            # Собираем все write-capable characteristics
            write_chars = []
            for service in bleak_client.services:
                for char in service.characteristics:
                    props = char.properties
                    if 'write' in props or 'write-without-response' in props:
                        write_chars.append((service, char))

            print(f"[BLE] Found {len(write_chars)} write-capable characteristics:")
            for svc, ch in write_chars:
                print(f"  Service {svc.uuid} → Char {ch.uuid} [{', '.join(ch.properties)}]")

            # Тестируем каждый write-char
            for svc_idx, (svc, ch) in enumerate(write_chars):
                svc_uuid = str(svc.uuid)
                ch_uuid = str(ch.uuid)
                print(f"\n[*] === Service {svc_uuid} / Char {ch_uuid} ===")

                # Сначала слушаем 2 сек
                rx_data = bytearray()
                rx_event = asyncio.Event()

                def notification_handler(sender, data):
                    rx_data.extend(data)
                    rx_event.set()

                has_notify = 'notify' in ch.properties or 'indicate' in ch.properties
                if has_notify:
                    try:
                        await bleak_client.start_notify(ch_uuid, notification_handler)
                        print("[+] Notifications enabled")
                    except Exception as e:
                        print(f"[-] Notify failed: {e}")

                await asyncio.sleep(1.0)

                # Тестируем разные форматы пакетов
                test_packets = []

                # 1. V1V2Packet vendor=27, command=768 (init, vendor=10 actually)
                test_packets.append(("V1V2 vendor=10 cmd=768 (Gaia init)",
                    make_v1v2_packet(10, 768)))
                # 2. V1V2Packet vendor=27, command=521 (first vivo TWS cmd)
                test_packets.append(("V1V2 vendor=27 cmd=521 (vivo TWS)",
                    make_v1v2_packet(27, 521)))
                # 3. V1V2Packet vendor=27, command=276 (OTA start)
                test_packets.append(("V1V2 vendor=27 cmd=276 (OTA)",
                    make_v1v2_packet(27, 276)))
                # 4. V1V2Packet vendor=27, command=514 (one of known cmds)
                test_packets.append(("V1V2 vendor=27 cmd=514",
                    make_v1v2_packet(27, 514)))
                # 5. V1V2Packet vendor=27, command=305 (settings)
                test_packets.append(("V1V2 vendor=27 cmd=305",
                    make_v1v2_packet(27, 305)))
                # 6. TOTA HEAD/TAIL format (cmd=0x6300)
                raw_payload = struct.pack('<HH', OP_TOTA_GENERAL_INFO_CMD, 0)
                test_packets.append(("TOTA HEAD/TAIL cmd=0x6300",
                    tota_pack(raw_payload)))
                # 7. Raw TOTA payload
                test_packets.append(("Raw TOTA payload cmd=0x6300",
                    raw_payload))
                # 8. BES OTA magic
                test_packets.append(("BES magic 0xFFFFFFFF",
                    b'\xff\xff\xff\xff'))
                # 9. V1V2 vendor=27, command=0 (null/cmd list)
                test_packets.append(("V1V2 vendor=27 cmd=0",
                    make_v1v2_packet(27, 0)))
                # 10. V1V2 vendor=27, command=16387 (special in APK)
                test_packets.append(("V1V2 vendor=27 cmd=16387",
                    make_v1v2_packet(27, 16387)))

                for desc, pkt in test_packets:
                    rx_data.clear()
                    rx_event.clear()

                    print(f"\n  [{desc}]")
                    print(f"  TX ({len(pkt)}B): {pkt[:32].hex()}{'...' if len(pkt) > 32 else ''}")

                    try:
                        # Use write-without-response if available, else write
                        if 'write-without-response' in ch.properties:
                            await bleak_client.write_gatt_char(ch_uuid, pkt, response=False)
                        else:
                            await bleak_client.write_gatt_char(ch_uuid, pkt, response=True)
                    except Exception as e:
                        print(f"  Write error: {e}")
                        continue

                    # Ждём ответ 3 сек
                    try:
                        await asyncio.wait_for(rx_event.wait(), timeout=3.0)
                    except asyncio.TimeoutError:
                        pass

                    if rx_data:
                        print(f"  RX ({len(rx_data)}B): {bytes(rx_data[:64]).hex()}{'...' if len(rx_data) > 64 else ''}")
                    else:
                        print("  [-] No response")

                    await asyncio.sleep(0.3)

                if has_notify:
                    try:
                        await bleak_client.stop_notify(ch_uuid)
                    except:
                        pass

            print("\n[*] Probe complete.")

    except Exception as e:
        print(f"[!] Error: {e}")
        import traceback
        traceback.print_exc()


async def main():
    parser = argparse.ArgumentParser(
        description="BLE Flash Dump for vivo TWS 5i (BES2710) via TOTA v2",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python ble_flash_dump.py --scan
  python ble_flash_dump.py --mac AC:40:1E:C0:BC:85 --probe
  python ble_flash_dump.py --mac AC:40:1E:C0:BC:85 --info
  python ble_flash_dump.py --mac AC:40:1E:C0:BC:85 --output flash_dump.bin
  python ble_flash_dump.py --mac AC:40:1E:C0:BC:85 --output flash.bin --start 0 --size 0x400000
  python ble_flash_dump.py --mac AC:40:1E:C0:BC:85 --uuid sdk --probe
        """,
    )
    parser.add_argument('--mac', help='MAC address (e.g. AC:40:1E:C0:BC:85)')
    parser.add_argument('--output', '-o', help='Output file for flash dump')
    parser.add_argument('--start', type=lambda x: int(x, 0), default=0, help='Start address (default: 0)')
    parser.add_argument('--size', type=lambda x: int(x, 0), default=0x400000, help='Dump size (default: 0x400000 = 4MB)')
    parser.add_argument('--scan', action='store_true', help='Scan BLE devices')
    parser.add_argument('--info', action='store_true', help='General info only (no dump)')
    parser.add_argument('--probe', action='store_true', help='Probe BLE protocol (try different packet formats)')
    parser.add_argument('--uuid', choices=['auto', 'vivo', 'sdk'], default='auto',
                        help='BLE UUID set (default: auto - try both)')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')

    args = parser.parse_args()

    if args.scan:
        await scan_devices()
        return

    if not args.mac:
        parser.error("--mac required (or --scan to discover)")

    if args.probe:
        await probe_protocol(args.mac, uuid_set=args.uuid, verbose=args.verbose)
        return

    if args.info:
        client = TOTAClient(args.mac, uuid_set=args.uuid)
        if args.verbose:
            client._log_level = 2
        try:
            await client.connect()
            await asyncio.sleep(0.5)
            print("[*] Starting TOTA handshake...")
            ok = await client.handshake()
            if ok:
                print("[+] Handshake successful!")
            else:
                print("[!] Handshake failed, trying unencrypted...")
                client.connect_status = TOTA_CONNECTED
            await asyncio.sleep(0.3)
            print("[*] Requesting general info...")
            info = await client.get_general_info()
            if info:
                print(f"[+] General info: {len(info)} bytes")
                client.hexdump(info, "  ", 256)
            else:
                print("[!] No response")
        finally:
            await client.disconnect()
        return

    if not args.output:
        parser.error("--output required for flash dump")

    ok = await dump_flash(args.mac, args.output, args.start, args.size,
                          uuid_set=args.uuid, verbose=args.verbose)
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    asyncio.run(main())
