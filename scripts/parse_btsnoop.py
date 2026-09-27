#!/usr/bin/env python3
"""Парсер btsnoop_hci.log — извлечение BLE GATT write/notify данных.

Формат btsnoop:
  Header (24 байта):
    - signature: "btsnoop\0" (8B)
    - version: 4B
    - datalink type: 4B (1002 = HCI UART / H4)
  Packet record:
    - original length: 4B BE
    - included length: 4B BE
    - packet flags: 4B BE (bit 0 = direction: 0=sent, 1=received)
    - cumulative drops: 4B BE
    - timestamp: 8B BE (microseconds since 2000-01-01 00:00:00)
    - packet data: [included length] bytes
"""
import struct
import sys
from datetime import datetime, timedelta

# UUIDs
TOTA_SERVICE = "00000837"
TOTA_CHAR    = "00000838"
SPP_SERVICE  = "00001100"
SPP_CMD      = "00001101"
SPP_RX       = "00001102"
SPP_DATA     = "00001103"

def parse_btsnoop(filepath):
    """Парсит btsnoop файл и возвращает список пакетов."""
    packets = []
    with open(filepath, "rb") as f:
        # Header
        header = f.read(24)
        if len(header) < 24:
            print("Файл слишком короткий для заголовка")
            return packets
        sig = header[:8]
        if sig != b"btsnoop\x00":
            print(f"Неверная сигнатура: {sig}")
            return packets
        version, dltype = struct.unpack(">II", header[8:16])
        print(f"btsnoop version={version} dltype={dltype}")

        while True:
            rec_hdr = f.read(24)
            if len(rec_hdr) < 24:
                break
            orig_len, incl_len, flags, drops, ts_hi, ts_lo = struct.unpack(">IIIIII", rec_hdr[:24])
            ts = (ts_hi << 32) | ts_lo
            data = f.read(incl_len)
            if len(data) < incl_len:
                break
            # timestamp: microseconds since 2000-01-01 (или другая эпоха)
            try:
                epoch = datetime(2000, 1, 1) + timedelta(microseconds=ts)
            except OverflowError:
                # Попробуем эпоху 1970 (некоторые устройства)
                try:
                    epoch = datetime(1970, 1, 1) + timedelta(microseconds=ts)
                except OverflowError:
                    epoch = datetime.now()
            # direction: flags bit 0 — 0=sent (host→controller), 1=received (controller→host)
            direction = "RX" if (flags & 1) else "TX"
            packets.append({
                "time": epoch,
                "direction": direction,
                "data": data,
                "flags": flags,
            })
    return packets

def parse_hci_packet(data):
    """Разбирает HCI пакет, возвращает (type, opcode, params) или None."""
    if len(data) < 1:
        return None
    pkt_type = data[0]
    # H4 packet types: 0x01=HCI_CMD, 0x02=ACL, 0x03=SCO, 0x04=HCI_EVT
    if pkt_type == 0x02:  # ACL data
        if len(data) < 5:
            return None
        handle_conn, acl_len = struct.unpack("<HH", data[1:5])
        handle = handle_conn & 0x0FFF
        l2cap_len = acl_len
        acl_data = data[5:5+acl_len]
        return {"type": "ACL", "handle": handle, "data": acl_data}
    elif pkt_type == 0x01:  # HCI Command
        if len(data) < 4:
            return None
        opcode = struct.unpack("<H", data[1:3])[0]
        param_len = data[3]
        params = data[4:4+param_len]
        return {"type": "CMD", "opcode": opcode, "params": params}
    elif pkt_type == 0x04:  # HCI Event
        if len(data) < 3:
            return None
        evt_code = data[1]
        param_len = data[2]
        params = data[3:3+param_len]
        return {"type": "EVT", "code": evt_code, "params": params}
    return None

def parse_l2cap(acl_data):
    """Разбирает L2CAP пакет. Возвращает (cid, payload) или None."""
    if len(acl_data) < 4:
        return None
    l2cap_len, l2cap_cid = struct.unpack("<HH", acl_data[:4])
    payload = acl_data[4:4+l2cap_len]
    return {"cid": l2cap_cid, "payload": payload}

# ATT opcodes
ATT_WRITE_REQ    = 0x12
ATT_WRITE_CMD    = 0x52
ATT_HANDLE_NFY   = 0x1B
ATT_HANDLE_IND   = 0x1D
ATT_READ_RSP     = 0x0B
ATT_READ_REQ     = 0x0A
ATT_WRITE_RSP    = 0x13

def parse_att(payload):
    """Разбирает ATT payload. Возвращает dict с opcode, handle, value."""
    if len(payload) < 1:
        return None
    opcode = payload[0]
    result = {"opcode": opcode}

    if opcode in (ATT_WRITE_REQ, ATT_WRITE_CMD):
        # Write Request/Command: opcode(1) + handle(2 LE) + value
        if len(payload) >= 3:
            handle = struct.unpack("<H", payload[1:3])[0]
            value = payload[3:]
            result["op"] = "WRITE"
            result["handle"] = handle
            result["value"] = value
    elif opcode == ATT_HANDLE_NFY:
        # Handle Notification: opcode(1) + handle(2 LE) + value
        if len(payload) >= 3:
            handle = struct.unpack("<H", payload[1:3])[0]
            value = payload[3:]
            result["op"] = "NOTIFY"
            result["handle"] = handle
            result["value"] = value
    elif opcode == ATT_HANDLE_IND:
        if len(payload) >= 3:
            handle = struct.unpack("<H", payload[1:3])[0]
            value = payload[3:]
            result["op"] = "INDICATE"
            result["handle"] = handle
            result["value"] = value
    elif opcode == ATT_WRITE_RSP:
        result["op"] = "WRITE_RSP"
    elif opcode == ATT_READ_RSP:
        result["op"] = "READ_RSP"
        result["value"] = payload[1:]
    elif opcode == ATT_READ_REQ:
        if len(payload) >= 3:
            handle = struct.unpack("<H", payload[1:3])[0]
            result["op"] = "READ_REQ"
            result["handle"] = handle
    else:
        result["op"] = f"UNKNOWN(0x{opcode:02x})"

    return result

# Handle → UUID mapping (заполним после парсинга GATT discovery)
# Для vivo TWS 5i:
# 0x00838 → TOTA_CHAR (00000838)
# 0x00101 → SPP_CMD  (00001101)
# 0x00102 → SPP_RX   (00001102)
# 0x00103 → SPP_DATA (00001103)

def hexdump(data, prefix="  "):
    """Возвращает hex+ascii дамп."""
    lines = []
    for i in range(0, len(data), 16):
        chunk = data[i:i+16]
        hexpart = " ".join(f"{b:02x}" for b in chunk)
        asciipart = "".join(chr(b) if 32 <= b <= 126 else "." for b in chunk)
        lines.append(f"{prefix}{i:04x}: {hexpart:<48s} {asciipart}")
    return "\n".join(lines)

def main():
    filepath = sys.argv[1] if len(sys.argv) > 1 else "btsnoop_fresh.cfa"
    print(f"Парсинг: {filepath}")
    packets = parse_btsnoop(filepath)
    print(f"Всего пакетов: {len(packets)}\n")

    # Сначала найдём GATT discovery (ATT_FIND_BY_TYPE_REQ / ATT_READ_BY_TYPE_REQ)
    # чтобы сопоставить handles → UUIDs
    handle_map = {}  # handle → UUID string

    # Извлекаем ATT write/notify
    att_ops = []
    for pkt in packets:
        hci = parse_hci_packet(pkt["data"])
        if not hci or hci["type"] != "ACL":
            continue
        l2cap = parse_l2cap(hci["data"])
        if not l2cap:
            continue
        if l2cap["cid"] != 0x0004:  # ATT CID
            continue
        att = parse_att(l2cap["payload"])
        if not att:
            continue
        att["time"] = pkt["time"]
        att["direction"] = pkt["direction"]
        att_ops.append(att)

    # Также ищем ATT_FIND_BY_TYPE_RSP и ATT_READ_BY_TYPE_RSP для handle map
    for pkt in packets:
        hci = parse_hci_packet(pkt["data"])
        if not hci or hci["type"] != "ACL":
            continue
        l2cap = parse_l2cap(hci["data"])
        if not l2cap or l2cap["cid"] != 0x0004:
            continue
        payload = l2cap["payload"]
        if len(payload) < 1:
            continue
        opcode = payload[0]
        # ATT_READ_BY_TYPE_RSP (0x09): opcode(1) + length(1) + [handle(2)+value(2)]*
        # Используется для discovery характеристик
        if opcode == 0x09 and len(payload) >= 2:
            item_len = payload[1]
            items = payload[2:]
            i = 0
            while i + item_len <= len(items):
                if item_len == 7:  # handle(2) + perms(1) + uuid(4) — 16-bit UUID
                    decl_handle = struct.unpack("<H", items[i:i+2])[0]
                    uuid_bytes = items[i+3:i+7]
                    uuid_hex = uuid_bytes[::-1].hex()
                    handle_map[decl_handle] = uuid_hex
                    # value handle = decl_handle + 1
                    handle_map[decl_handle + 1] = uuid_hex
                elif item_len == 21:  # handle(2) + perms(1) + uuid(16) — 128-bit UUID
                    decl_handle = struct.unpack("<H", items[i:i+2])[0]
                    uuid_bytes = items[i+3:i+19]
                    uuid_str = str(__import__('uuid').UUID(bytes=bytes(uuid_bytes)))
                    handle_map[decl_handle] = uuid_str
                    handle_map[decl_handle + 1] = uuid_str
                i += item_len
        # ATT_FIND_INFO_RSP (0x05): opcode(1) + format(1) + [handle(2)+uuid(2/16)]*
        elif opcode == 0x05 and len(payload) >= 2:
            fmt = payload[1]
            items = payload[2:]
            if fmt == 1:  # 16-bit UUIDs
                i = 0
                while i + 4 <= len(items):
                    h = struct.unpack("<H", items[i:i+2])[0]
                    uuid_bytes = items[i+2:i+4]
                    uuid_hex = uuid_bytes[::-1].hex()
                    handle_map[h] = uuid_hex
                    i += 4
            elif fmt == 2:  # 128-bit UUIDs
                i = 0
                while i + 18 <= len(items):
                    h = struct.unpack("<H", items[i:i+2])[0]
                    uuid_bytes = items[i+2:i+18]
                    uuid_str = str(__import__('uuid').UUID(bytes=bytes(uuid_bytes)))
                    handle_map[h] = uuid_str
                    i += 18

    print("=== Handle → UUID map ===")
    for h in sorted(handle_map.keys()):
        print(f"  0x{h:04x} → {handle_map[h]}")
    print()

    print("=== ATT Write/Notify operations ===")
    for op in att_ops:
        if op.get("op") in ("WRITE", "NOTIFY", "INDICATE"):
            handle = op.get("handle", 0)
            uuid = handle_map.get(handle, "????")
            value = op.get("value", b"")
            dir_str = op["direction"]
            t = op["time"].strftime("%H:%M:%S.%f")[:-3]
            print(f"\n[{t}] {dir_str} {op['op']} handle=0x{handle:04x} ({uuid}) len={len(value)}")
            print(hexdump(value))

    print(f"\n=== Total ATT ops: {len(att_ops)} ===")
    print(f"Writes: {sum(1 for o in att_ops if o.get('op')=='WRITE')}")
    print(f"Notifies: {sum(1 for o in att_ops if o.get('op')=='NOTIFY')}")

if __name__ == "__main__":
    main()
