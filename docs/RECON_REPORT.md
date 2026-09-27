# vivo TWS 5i — Реверс-инжиниринг и извлечение прошивки

**Дата:** 2026-09-27
**Устройство:** vivo TWS 5i
**Чип:** BES2710
**MAC (L):** `AC:40:1E:C0:BC:85`
**MAC (R):** `AC:40:1E:C0:64:D8`

---

## 1. Параметры устройства

| Параметр | Значение |
|----------|----------|
| Firmware version | 2.0.7 (V=2.0.7_2.0.7, L=R) |
| Build | 259 |
| Features | 7 (0b111) |
| Battery voltage | 4256 mV |
| Battery percent | 100% |
| Sample rate | 48000 Hz |
| Codec | 2 (SBC/AAC) |
| CaseOpentime | 1029900 ms |
| HandsetAddr | 4871564 |
| BLE pairing | Yes (Windows, secure connection) |
| MTU | 245 (auto-negotiated) |

---

## 2. BLE GATT карта сервисов

### Service 00000837 (TOTA)
| Characteristic | UUID | Properties | Описание |
|----------------|------|------------|----------|
| TOTA_CHAR | `00000838-d102-11e1-9b23-00025b00a5a5` | READ(2) + WRITE(8) + NOTIFY(16) = 26 | Vivo custom VIPC handler |

### Service 00001100 (SPP/VIPC)
| Characteristic | UUID | Properties | Описание |
|----------------|------|------------|----------|
| SPP_CMD | `00001101-d102-11e1-9b23-00025b00a5a5` | WRITE(8) = 8 | Командный канал (write) |
| SPP_RX | `00001102-d102-11e1-9b23-00025b00a5a5` | READ(2) + NOTIFY(16) = 18 | Приём данных (notify) |
| SPP_RW | `00001103-d102-11e1-9b23-00025b00a5a5` | READ(2) + WRITE_NO_RESP(4) + NOTIFY(16) = 22 | Чтение/запись + notify |

### Service 01000100 (vivo custom)
| Characteristic | UUID | Properties | Описание |
|----------------|------|------------|----------|
| NEW_CMD | `03000300-0000-1000-8000-009278563412` | WRITE(8) + WRITE_NO_RESP(4) = 12 | Loopback/test (эхо) |
| NEW_RX | `02000200-0000-1000-8000-009178563412` | NOTIFY(16) = 16 | Notify для loopback |

### Прочие сервисы
| Service | Описание |
|---------|----------|
| `00001800` | Generic Access (Device Name, Appearance) |
| `00001801` | Generic Attribute (Service Changed) |
| `00001844` | HID Service |
| `00001846` | HID Data |
| `0000184d` | Audio Control |
| `0000184e` | Battery |
| `00001850` | Paging |
| `00001853` | Unknown |
| `00001855` | Unknown (char 00002b51, READ) |

---

## 3. Протоколы

### 3.1. Авто-данные (SPP_RX 00001102)

Наушник **автоматически** отправляет 23+ JSON пакетов при BLE подключении.
Команды инициировать не нужно — просто подключиться и слушать 30-60 сек.

#### Формат пакета авто-данных
```
[00][1b][82][cmd_byte][00][seq][payload...]
```

| cmd_byte | Назначение | Размер |
|----------|------------|--------|
| `0x49` | Hello (device info) | 57B |
| `0x24` | JSON data (eventId) | 242B |
| `0x07` | Status (battery/link) | 9B |
| `0x4b` | BD addr | 12B |
| `0x75` | Unknown | 6B |
| `0x51` | Unknown | 6B |
| `0x0d` | Unknown | 6B |

#### Hello пакет (57B)
```
00 1b 82 49 00 02 [BD addr 6B] [hostname] [phone model]
```
Пример: содержит `DESKTOP-MOBILE3O` и `OnePlus 9RT 5G`

#### JSON пакеты (242B каждый)
Заголовок: `00 1b 82 24 00 01 [seq_byte] [JSON...]`

### 3.2. Полученные Event IDs

| EventId | Описание | Ключевые params |
|---------|----------|------------------|
| A102\|10037 | vivofastpair | result, vivofastpairincasestate |
| A102\|10062 | result/fail_reason | result=2, fail_reason_1=4 |
| A102\|10078 | Case info | CaseOpentime=1029900, PeerAclConStatus=5 |
| A102\|10080 | Audio dump | play_time, src_addr=4a558c, mirrorA2dp |
| A102\|10086 | BT link | bd_addr=4871564, HCI_status=0 |
| A102\|10087 | BT link | bd_addr, HCI_status=8 |
| A102\|10088 | BT link | **Features=7**, AT_CMD=0 |
| A102\|10089 | BT link | bd_addr, duration |
| A102\|10090 | BT link | Local_initiated, Signaling |
| A102\|10091 | BT link | HCI_status=2, seid=2 |
| A102\|10092 | BT link | HCI_status=8 |
| A102\|10093 | BT link | HCI_status=8, fail_reason |
| A102\|10094 | Dis status | AclDisStatus, A2dpDisStatus, HfpDisStatus, GaiaDisStatus |
| A102\|10095 | Error | error_code=0, AclStatus=5 |
| A102\|10096 | **Version** | **version=259**, Status=1 |
| A102\|10097 | Type | type=0 |
| A102\|10100 | Kymera | AclDisStatus, KymeraScoState, KymeraA2dpState |
| A102\|10105 | Underflow | underflow=0 |
| A102\|10110 | Reboot | bt_reboot_reason=65536 |
| A102\|10124 | Playback | Codec=2, SampleRate=48000, TotalSpendDur=64046 |
| A102\|10128 | **Battery** | real_voltage=4256, real_battery_percent=100 |
| A102\|10156 | RMS | rms_mute, RSSI (периодический, каждые ~10 сек) |
| A102\|10164 | Crash | total_crash_count=0 |
| A102\|10165 | Handover | handover_status=0, handover_source=0 |

#### Финальный пакет (67B)
```json
{"V":"2.0.7_2.0.7","C":"100_100","P":"2_2","B":"1_1","D":"0"}
```

### 3.3. VIPC протокол (FF 55 header)

#### Формат пакета
```
[FF][55][len:1B][protocol_id][JSON data]
```

JSON (TwsVipcPacket):
```json
{
  "param": "<subcommand_param>",
  "command": "<subcommand>",
  "type": 1,
  "device": ""
}
```

#### Структура из APK (smali)

**TwsVipcPacket** (`com/vivo/tws/command/TwsVipcPacket.smali`):
- `param` (String) — @SerializedName("param")
- `command` (String) — @SerializedName("command")
- `type` (int) — @SerializedName("type"), TYPE_REQUEST=1, TYPE_RESPONSE=2, TYPE_NOTIFICATION=3
- `device` (String) — @SerializedName("device")

**VIPCHelper** (`ic/c.smali`):
```
ic/c.a(feature, command, device, param):
  TwsVipcPacket(type=1, command=command, device=device, param=param)
  Request.obtain("com.vivo.tws.third.app", feature)
```

Feature НЕ входит в TwsVipcPacket JSON — он передаётся отдельно в Request.

**G9/e.smali** — построение BLE пакета:
```
array[0] = 0xFF
array[1] = 0x55
n(array_length(json), 2, 2, array) → array[2] = len_lo, array[3] = len_hi
array[3] = 0x02  ← ПЕРЕЗАПИСЬ! Всегда 0x02
copy(json → array[4..])
send(array)
```

**G9/g.smali** — отправка через GATT:
```
characteristic.setWriteType(2)  ← WRITE_TYPE_SIGNED
characteristic.setValue(data)
gatt.writeCharacteristic(characteristic)
```

#### VIPC команды из APK

| Feature | Command | Описание |
|---------|---------|----------|
| ota_feature | check | Проверка OTA |
| ota_feature | get_state | Состояние OTA |
| ota_feature | download | Загрузка OTA |
| ota_feature | install | Установка OTA |
| information_feature | get_earbud_status | Статус наушников |
| information_feature | get_earbud_information | Информация о наушниках |
| settings_feature | * | Настройки |
| config_feature | * | Конфигурация |
| fastpair_feature | * | Fast Pair |

#### Тестирование protocol_id (header byte 3)

| protocol_id | Ответ | Расшифровка |
|-------------|-------|-------------|
| 0x00 | Нет ответа | Не распознан |
| 0x01 | Нет ответа | Не распознан |
| 0x02 | `FF 55 01 82 03` | Response (0x80+0x02), **error 0x03** |
| 0x03 | `FF 55 01 83 00` | Response (0x80+0x03), **success 0x00** |
| 0x04 | `FF 55 01 84 03` | Response, error 0x03 |
| 0x05 | `FF 55 01 85 03` | Response, error 0x03 |
| 0x06-0x0F | Нет ответа на TOTA | Не распознан |

APK всегда использует `0x02` — это правильный protocol_id для команд.

#### NACK анализ

`FF 55 01 82 03`:
- `FF 55` — header magic
- `01` — data length (1 byte)
- `82` = `0x80` (response flag) + `0x02` (protocol_id=2)
- `03` — error code

Error 0x03 **не зависит** от содержимого JSON (command, type, device, param, feature) — постоянная ошибка.

**Причина error 0x03:** APK использует `WRITE_TYPE_SIGNED` (Android `setWriteType(2)`), который требует bonded device + link-layer signature. WinRT/Bleak **не поддерживает** signed GATT writes — это ограничение Windows BLE API.

### 3.4. BES TOTA v2 (HEAD/TAIL)

#### Формат пакета
```
[HEAD:4B="HEAD"][bufLen:4B LE][payload:bufLen][CRC32:4B LE][TAIL:4B="TAIL"]
```

Payload:
```
[cmdCode:2B LE][paramLen:2B LE][param:paramLen]
```

#### Команды (app_tota_cmd_code.h)

| Команда | Код | Описание |
|---------|-----|----------|
| OP_TOTA_CONN_INITIATE | 0x1001 | Начало handshake |
| OP_TOTA_CONN_RESPONSE | 0x1002 | Ответ handshake |
| OP_TOTA_CONN_CONFIRM | 0x1003 | Подтверждение handshake |
| OP_TOTA_READ_FLASH_CMD | 0x6202 | Чтение flash |
| OP_TOTA_WRITE_FLASH_CMD | 0x6200 | Запись flash |
| OP_TOTA_ERASE_FLASH_CMD | 0x6201 | Стирание flash |
| OP_TOTA_GET_SECINFO_EQ | 0x6203 | Информация о секциях |
| OP_TOTA_EXCHANGE_MTU_CMD | 0x6301 | Обмен MTU |

#### Handshake (app_tota_conn.cpp)
1. Client → `CONN_INITIATE` с `random_key_b`
2. Earphone → `CONN_RESPONSE` с `random_key_a`
3. Client вычисляет `hash_key = SHA256(combined_random_keys)`
4. Client → `CONN_CONFIRM` с `hash_key`
5. Earphone проверяет → `TOTA_SHAKE_HANDED`

#### Результат
BES TOTA v2 (HEAD/TAIL) пакеты отправлены на TOTA char (00000838) — **нет ответа**.
Вывод: UUID 00000837/00000838 — vivo custom, не BES SDK TOTA (BES использует `0x86...86`/`0x97...97`).

---

## 4. BLE подключение

### Bleak (Python)
```python
from bleak import BleakScanner, BleakClient
dev = await BleakScanner.find_device_by_address('AC:40:1E:C0:BC:85', timeout=10.0)
async with BleakClient(dev, timeout=30.0) as client:
    await client.start_notify(SPP_RX, handler)
    # Авто-данные приходят в течение 30-60 сек
```

### WinRT (Python, raw)
```python
from winrt.windows.devices.bluetooth import BluetoothLEDevice
from winrt.windows.devices.bluetooth.genericattributeprofile import (
    GattClientCharacteristicConfigurationDescriptorValue
)
dev = await BluetoothLEDevice.from_bluetooth_address_async(0xAC401EC0BC85)
svc = (await dev.get_gatt_services_for_uuid_async(TOTA_SVC_UUID)).services[0]
ch = (await svc.get_characteristics_for_uuid_async(TOTA_CHAR_UUID)).characteristics[0]
await ch.write_client_characteristic_configuration_descriptor_async(
    GattClientCharacteristicConfigurationDescriptorValue.NOTIFY)
token = ch.add_value_changed(handler)
```

### Особенности Windows BLE
- `BleakClient(mac_string)` не работает → использовать `BleakScanner.find_device_by_address()`
- TOTA notify нестабилен через Bleak (часто "Unreachable")
- WinRT raw GATT надёжнее для TOTA char
- MTU 245 auto-negotiated (не нужно вручную)
- WRITE_TYPE_SIGNED **не поддерживается** WinRT
- `GattWriteOption`: только `WRITE_WITH_RESPONSE(0)` и `WRITE_WITHOUT_RESPONSE(1)`

---

## 5. APK анализ

### Ключевые классы smali

| Файл | Класс | Назначение |
|------|-------|------------|
| `G9/e.smali` | GattManager callback | Построение пакета FF 55, createBond, setPin |
| `G9/g.smali` | GattManager | setWriteType(2)=SIGNED, writeCharacteristic, queue |
| `K9/a.smali` | UUIDs | 00000837 (service), 00000838 (char), 00002902 (CCCD) |
| `ic/c.smali` | VIPC helper | buildRequest(feature, cmd, device, param) → TwsVipcPacket |
| `com/vivo/tws/command/TwsVipcPacket.smali` | Packet | type, command, device, param (Gson SerializedName) |
| `com/vivo/tws/command/a.smali` | Constants | TYPE_REQUEST=1, TYPE_RESPONSE=2, TYPE_NOTIFICATION=3 |
| `Vb/b.smali` | Upgrade repo | ota_feature/check, get_state, download, install |
| `B5/e.smali` | HomePresenter | ear_temperature_report, VIPC packet handler |

### APK pair flow
1. `BluetoothDevice.createBond()` — инициирует pairing
2. `BluetoothDevice.setPin(passkey)` — устанавливает PIN
3. После bonding → `setWriteType(WRITE_TYPE_SIGNED)` → `writeCharacteristic()`

---

## 6. BES SDK анализ

### ble_tota.c
- BES TOTA UUIDs: `0x868686...86` (service), `0x979797...97` (char)
- **НЕ** 00000837/00000838 — vivo использует custom UUIDs
- Char props: `GATT_WR_REQ | GATT_WR_CMD | GATT_NTF_PROP`
- Security: `ATT_SEC_NONE` (write), `ATT_WR_ENC` (CCCD)
- Preferred MTU: 495

### app_tota_common.h
```c
#define TOTA_HEAD "HEAD"     // 4 bytes
#define TOTA_HEAD_SIZE 4
#define TOTA_LEN_SIZE 4      // uint32_t
#define TOTA_CRC_SIZE 4      // uint32_t
#define TOTA_TAIL "TAIL"     // 4 bytes
#define TOTA_TAIL_SIZE 4
```

### app_tota_conn.cpp
- Handshake: CONN_INITIATE → CONN_RESPONSE → CONN_CONFIRM
- SHA256 для генерации hash_key
- encrypt_key из hash_key
- TOTA_SHAKE_HANDED после успешного handshake

---

## 7. Файлы проекта

| Файл | Размер | Описание |
|------|--------|----------|
| `ble_flash_dump.py` | 891 строк | BLE TOTA v2 client (patched: cryptography, Windows BLE) |
| `ble_gaia_probe.py` | 279 строк | Gaia/VIPC probe |
| `ble_vipc_dump.json` | — | VIPC protocol analysis |
| `README.md` | — | Краткое резюме |
| `firmware_chunks/full_decompressed.bin` | 712 KB | Декомпрессированный firmware dump |
| `firmware_20007_to_20103.bin` | 37 KB | VIVDIF01 diff patch (OTA) |
| `vivo tws5i.md` | 19 KB | Протокол/анализ notes |
| `apktool_out/` | — | Декомпилированный APK |
| `tws_earbuds-main/` | — | BES SDK source |

---

## 8. Блокеры и ограничения

### Главный блокер: WRITE_TYPE_SIGNED
- APK использует `setWriteType(2)` = `WRITE_TYPE_SIGNED`
- Требует bonded device + link-layer MAC signature
- WinRT/Bleak **не поддерживает** signed GATT writes
- Error 0x03 = "write not signed/authenticated"
- Это **фундаментальное ограничение** Windows BLE API

### Дополнительные блокеры
- TOTA notify нестабилен через Bleak (Windows WinRT)
- BES TOTA v2 не работает (vivo custom UUIDs, не BES SDK)
- V1V2 INIT (0x0a 0x00 0x00 0x03) работал один раз (5392B, 23 пакета), но не воспроизводится

---

## 9. Что работает / не работает

### ✅ Работает
- BLE подключение (Bleak + WinRT)
- Приём авто-данных (23 JSON пакета на SPP_RX)
- WinRT raw GATT (notify + write на TOTA)
- VIPC ACK (protocol 0x03 → success)
- MTU 245 (auto)
- BLE pairing (is_paired=True, was_secure=True)

### ❌ Не работает
- VIPC команды (protocol 0x02 → error 0x03)
- BES TOTA v2 (HEAD/TAIL → нет ответа)
- TOTA notify через Bleak (Unreachable)
- Read TOTA char (Value Not Allowed)
- V1V2 INIT (работал один раз, не воспроизводится)

---

## 10. Следующие шаги

1. **Classic BT RFCOMM SPP** — pybluez, SPP может не требовать signed writes
2. **ADB + vivo APK** — отправка команд через приложение на Android
3. **Глубокий анализ 712KB firmware** — strings, disasm, flash layout
4. **OTA server** — получить больше diff патчей для других версий
5. **pybluez signed write** — проверить поддержку signed writes в pybluez
