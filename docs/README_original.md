# vEarphones — vivo TWS 5i Firmware Extraction

## Device Info
- **Model:** vivo TWS 5i
- **Chip:** BES2710
- **MAC (L):** AC:40:1E:C0:BC:85
- **MAC (R):** AC:40:1E:C0:64:D8
- **Firmware:** 2.0.7 (V=2.0.7_2.0.7, L=R)
- **Build:** 259
- **Features:** 7 (0b111)
- **Battery:** 4256mV, 100%
- **Paired:** Yes (Windows, secure connection)

## BLE GATT Services
| Service | UUID | Chars |
|---------|------|-------|
| TOTA | 00000837-... | 00000838 (READ+WRITE+NOTIFY) |
| SPP/VIPC | 00001100-... | 00001101 (WRITE), 00001102 (READ+NOTIFY), 00001103 (READ+WRITE_NO_RESP+NOTIFY) |
| vivo custom | 01000100-... | 03000300 (WRITE), 02000200 (NOTIFY) |
| HID | 00001844/00001846 | — |
| Battery | 0000184e | — |

## Protocol Discovery

### Auto-Data (SPP_RX 00001102)
Наушник автоматически шлёт 23+ JSON пакетов при подключении:
- **Header:** `00 1b 82 24 00 01 [seq] [JSON]`
- **Event IDs:** A102|10037, 10062, 10078, 10080, 10086-10097, 10100, 10105, 10124, 10128, 10156, 10164, 10165
- **Key data:** version=259, V=2.0.7, Features=7, battery, RSSI, HCI status

### Hello Packet (57B, auto on connect)
`00 1b 82 49 00 02 [BD addr] [hostname] [phone model]`

### VIPC Protocol (FF 55 header) — FULLY MAPPED
- **Format:** `[FF][55][len:1B][proto_byte][data]`
- **Response:** `[FF][55][resp_len:1B][0x80|proto_byte][status]`
- Status: 0x00=OK, 0x01=INVALID_CMD, 0x03=PARAM_LEN_OUT_OF_RANGE

| Proto | Name | Data Len | Before Unlock | After 0x05 Unlock |
|-------|------|----------|---------------|-------------------|
| 0x00 | ? | any | No response | No response |
| 0x01 | ? | any | No response | No response |
| 0x02 | command | 16B only | NACK 0x01 | ACK 0x00 (only all-zeros=ping) |
| 0x03 | subscribe | any | ACK 0x00 | ACK 0x00 |
| 0x04 | configure | 4B only | NACK 0x03 / ACK 0x00 | ACK 0x00 |
| 0x05 | init/unlock | 16B only | ACK 0x00 | ACK 0x00 |
| 0x06-0xFF | ? | any | No response | No response |

### Key Discovery: AES-128-CBC Encryption
- 0x05 (16B) unlocks 0x02 commands
- After unlock, ONLY all-zero 16B → ACK (ping/heartbeat)
- All other 16B data → INVALID_CMD (0x01)
- This means 0x02 data is AES-128-CBC encrypted
- All-zeros plaintext = valid (ping), non-zero = can't parse without key
- AES key from TOTA v2 handshake (CONN_INITIATE), but handshake not functional inside VIPC

### BES TOTA v2 (HEAD/TAIL format) — NOT WORKING
- Format: `[HEAD:4B][bufLen:4B LE][cmdCode:2B LE][paramLen:2B LE][param][CRC32:4B LE][TAIL:4B]`
- Commands: CONN_INITIATE(0x1001), READ_FLASH(0x6202), EXCHANGE_MTU(0x6301)
- No response on TOTA char — vivo custom UUIDs, not BES SDK UUIDs

## Blockers
1. **AES-128-CBC encryption on commands:** Only ping (all-zeros) works. Cannot derive AES key.
2. **TOTA v2 handshake not functional:** CONN_INITIATE inside VIPC 0x02 → INVALID_CMD
3. **V1V2 INIT requires case reset:** Only works immediately after physical case reset
4. **WinRT no signed writes:** APK uses WRITE_TYPE_SIGNED, WinRT doesn't support it
5. **No data from commands:** All commands return only 5-byte status, no payload

## What Works
- ✅ BLE подключение (Bleak + WinRT)
- ✅ Auto-data приём (23 JSON пакетов, SPP_RX after case reset)
- ✅ TOTA unlock (0x05 + 16B → ACK)
- ✅ TOTA ping (0x02 + 16B zeros → ACK after unlock)
- ✅ Subscribe (0x03 + any → ACK)
- ✅ Configure (0x04 + 4B → ACK)
- ✅ WinRT raw GATT (notify + write)
- ✅ MTU 245 (auto-negotiated)
- ✅ Auto-status (242B JSON packets on SPP_RX)

## What Doesn't Work
- ❌ Real VIPC commands (only ping works)
- ❌ BES TOTA v2 (HEAD/TAIL → no response)
- ❌ AES key derivation (handshake broken)
- ❌ V1V2 INIT without case reset
- ❌ SPP_CMD commands (no response)

## Files
- `PROTOCOL_ANALYSIS.md` — detailed protocol findings
- `ble_flash_dump.py` — BLE TOTA v2 client (patched for cryptography + Windows)
- `ble_gaia_probe.py` — Gaia/VIPC probe
- `ble_vipc_dump.json` — VIPC protocol analysis
- `firmware_chunks/full_decompressed.bin` — 712KB decompressed firmware
- `firmware_20007_to_20103.bin` — 37KB VIVDIF01 diff patch
- `firmware_sdk.py` — firmware unpack/repack SDK
- `frida_full_firmware.js` — Frida script for full firmware extraction
- `apktool_out/` — decompiled APK
- `tws_earbuds-main/` — BES SDK source code

## Next Steps
1. **Android + Frida:** intercept vivo APK BLE traffic, extract AES key from TOTA encryption
2. **Анализ 712KB firmware dump:** search for AES key, command handlers, flash read routines
3. **Правый наушник:** попробовать MAC AC:40:1E:C0:64:D8
4. **OTA server:** получить больше diff патчей для анализа
