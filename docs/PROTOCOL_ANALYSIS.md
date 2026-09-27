
# vEarphones — Protocol Analysis (Session 2026-09-27)

## TOTA Characteristic (00000838) — VIPC Protocol

### Packet Format
[0xFF][0x55][length:1B][protocol_byte][data]

### Protocol Bytes
| Byte | Name | Data Length | Response |
|------|------|-----------|----------|
| 0x00 | ?    | any       | No response |
| 0x01 | ?    | any       | No response |
| 0x02 | command | 16B only | NACK 0x01 (before unlock) / ACK 0x00 (after unlock, only all-zeros) |
| 0x03 | subscribe | any | ACK 0x00 (always) |
| 0x04 | configure | 4B only | ACK 0x00 (always) |
| 0x05 | init/unlock | 16B only | ACK 0x00 (always) |
| 0x06-0xFF | ? | any | No response |

### Response Format
[0xFF][0x55][data_len:1B][0x80|protocol_byte][status_code]
- status 0x00 = success
- status 0x01 = INVALID_CMD
- status 0x03 = PARAM_LEN_OUT_OF_RANGE

### Key Findings
1. 0x05 (16B) unlocks 0x02 commands
2. After unlock, only all-zero 16B data → ACK (ping)
3. All other 16B data → INVALID_CMD (0x01)
4. This suggests AES-128-CBC encryption of command data
5. All-zeros = valid plaintext (ping/heartbeat)
6. Non-zero = encrypted command → can't parse without correct key

### Blockers
- Cannot get AES key (CONN_INITIATE not working inside VIPC)
- V1V2 INIT requires case reset each time
- SPP channel only sends auto-status (242B packets)
- No real commands return data via BLE

### What Works
- BLE connection (Bleak + WinRT)
- TOTA unlock (0x05 + 16B)
- TOTA ping (0x02 + 16B zeros)
- Subscribe (0x03 + any)
- Configure (0x04 + 4B)
- Auto-status on SPP_RX (242B JSON packets)
- V1V2 INIT after case reset → 23 JSON status packets

### Available Data
- 712KB decompressed OTA diff patch (VIVDIF01 format)
- 37KB compressed OTA diff (firmware_20007_to_20103.bin)
- 23 JSON status packets from V1V2 INIT
- Auto-status packets (242B) from SPP_RX
