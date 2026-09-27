# vEarphones — vivo TWS 5i (BES2710) Reverse Engineering

Реверс-инжиниринг и извлечение прошивки наушников **vivo TWS 5i** на чипе **BES2710** (Bestechnic).

## Устройство

| Параметр | Значение |
|----------|----------|
| Модель | vivo TWS 5i |
| Чип | BES2710 (BEST1306) |
| Project ID | DPD2543A |
| MAC (L) | `AC:40:1E:C0:BC:85` |
| MAC (R) | `AC:40:1E:C0:64:D8` |
| Firmware | 2.0.7 (V=2.0.7_2.0.7, L=R) |
| Build | 259 |
| Features | 7 (0b111) |
| Flash | 4 MB |

## Структура репозитория

```
vEarphones/
├── docs/                           # Документация и отчёты
│   ├── RECON_REPORT.md             # Полный отчёт реконнайтсинга
│   ├── PROTOCOL_ANALYSIS.md        # Анализ BLE протоколов (TOTA, VIPC, SPP)
│   ├── BES2710_Firmware_Reverse.md # Реверс прошивки (LZMA, VIVDIF01)
│   ├── BES2710_SDK_Analysis.md     # Анализ BES SDK
│   ├── BES2710_SDK_Reverse_Engineering.md
│   ├── Firmware_Full_Image_Analysis.md
│   ├── vivo_tws5i_notes.md         # Заметки по протоколам и анализу
│   └── README_original.md          # Исходный README
├── scripts/                        # Python и Frida скрипты
│   ├── ble_flash_dump.py           # BLE TOTA v2 клиент (Bleak + WinRT)
│   ├── ble_flash_dump.bat          # Bat-обёртка для запуска
│   ├── ble_gaia_probe.py           # Gaia/VIPC probe
│   ├── firmware_sdk.py             # Firmware unpack/repack SDK (LZMA, VIVDIF01)
│   ├── parse_btsnoop.py            # BTSnoop HCI парсер
│   ├── frida_capture.py            # Frida capture runner
│   ├── frida_run.py                # Frida run helper
│   ├── run_frida.py                # Frida launcher
│   └── frida/                      # Frida JS скрипты
│       ├── frida_ble_intercept.js  # Перехват BLE трафика
│       ├── frida_full_firmware.js  # Полное извлечение прошивки
│       ├── frida_ota_active.js     # Активный OTA перехват
│       ├── frida_ui_intercept.js   # Перехват UI
│       ├── frida_vipc_intercept.js # VIPC перехват
│       └── frida_test.js           # Тестовый скрипт
├── firmware/                       # Binary данные прошивки
│   ├── firmware_20007_to_20103.bin # OTA diff patch (37 KB, VIVDIF01)
│   ├── firmware_decompressed.bin   # Декомпрессированный firmware (712 KB)
│   ├── firmware_diff.bin           # Diff patch копия
│   ├── firmware_patched_test.bin   # Тестовый patched firmware
│   ├── firmware_repacked.bin       # Перепакованный firmware
│   ├── patched_chunk_0.bin         # Patched chunk 0
│   └── tota_key_a.bin              # TOTA key A
├── captures/                       # Захваченные данные
│   ├── ble_vipc_dump.json          # VIPC protocol analysis (JSON)
│   ├── event_record_gatt.txt       # GATT event log
│   ├── event_record_new.txt        # Event log (новый)
│   └── ui*.xml                     # UI dumps (Android hierarchy)
├── sdk_refs/                       # Git submodules — BES SDK исходники
│   ├── tws_earbuds/                # Derek-Vencer/tws_earbuds (flasher tool)
│   └── audio_prj_collections/      # sprlightning/audio_prj_collections (BES2700IHC SDK)
├── apk_analysis/                   # Анализ APK (см. docs)
├── tools/                          # Утилиты (см. docs)
└── .gitignore
```

## Ключевые результаты

### ✅ Работает
- BLE подключение (Bleak + WinRT)
- Приём авто-данных (23+ JSON пакетов на SPP_RX после reset)
- VIPC unlock (0x05 + 16B → ACK)
- VIPC ping (0x02 + 16B zeros → ACK после unlock)
- Subscribe (0x03 + any → ACK)
- Configure (0x04 + 4B → ACK)
- WinRT raw GATT (notify + write на TOTA)
- MTU 245 (auto-negotiated)
- Декомпрессия firmware (LZMA + VIVDIF01, 712 KB)

### ❌ Блокеры
- **WRITE_TYPE_SIGNED** — APK использует `setWriteType(2)`, WinRT/Bleak не поддерживает signed writes → error 0x03
- **AES-128-CBC** — VIPC команды зашифрованы, ключ получить не удалось
- **BES TOTA v2** — HEAD/TAIL пакеты на vivo custom UUIDs → нет ответа
- **Полный образ прошивки** — vivo OTA сервер отдаёт только diff patches

## BLE GATT сервисы

| Service | UUID | Описание |
|---------|------|----------|
| TOTA | `00000837-...` | Vivo custom VIPC handler (char 00000838) |
| SPP/VIPC | `00001100-...` | SPP_CMD (00001101), SPP_RX (00001102), SPP_RW (00001103) |
| vivo custom | `01000100-...` | Loopback/test |
| HID | `00001844/00001846` | HID Service/Data |
| Battery | `0000184e` | Battery |

## VIPC протокол

```
[FF][55][len:1B][protocol_byte][data]
```

| Proto | Name | Data | Response |
|-------|------|------|----------|
| 0x02 | command | 16B | NACK→ACK (после unlock 0x05) |
| 0x03 | subscribe | any | ACK 0x00 |
| 0x04 | configure | 4B | ACK 0x00 |
| 0x05 | init/unlock | 16B | ACK 0x00 |

## Firmware формат

```
VIVO Header (1024B) → BES OTA Magic (4B) → Chunk[0..21] → CRC32 Footer
```

Каждый chunk: `[size:4B BE][LZMA data]`
LZMA: props=0x5D (lc=3, lp=0, pb=2), dict=8MB, format=LZMA_ALONE

## SDK submodules

Исходники BES SDK подключены как git submodules:

```bash
git clone --recurse-submodules https://github.com/evoeram/vEarphones.git
```

Или инициализация после клона:
```bash
git submodule update --init --recursive
```

- **tws_earbuds** — [Derek-Vencer/tws_earbuds](https://github.com/Derek-Vencer/tws_earbuds): BES flashing tool + SecondStage bootloader blobs
- **audio_prj_collections** — [sprlightning/audio_prj_collections](https://github.com/sprlightning/audio_prj_collections): BES2700IHC / BEST1306 SDK source leak

## Исключённые файлы

Крупные бинарники исключены через `.gitignore` (регенерируемы или доступны отдельно):
- APK файлы (`*.apk`, `*.idsig`) — декомпиляция через apktool/jadx
- `apktool.jar`, Frida wheels (`*.whl`), `frida-server-*`
- Apktool/jadx output (`apktool_out/`, `verify_out/`, `sources/`, `resources/`)
- BTSnoop captures (`*.cfa`), logs (`*.log`), screenshots (`*.png`)
- Firmware chunks (`firmware_chunks/`, `firmware_unpack_test/`, `firmware_work/`)

## Следующие шаги

1. **Android + Frida** — перехват vivo APK BLE трафика, извлечение AES ключа
2. **Анализ 712KB firmware** — поиск AES ключа, command handlers, flash read routines
3. **Classic BT RFCOMM SPP** — pybluez, SPP может не требовать signed writes
4. **OTA server** — получить больше diff патчей для анализа
5. **Применить diff** — обновить до v2.1.3, сделать BLE-дамп новой версии

## Лицензия

Проект создан для исследовательских целей. SDK исходники в submodules имеют собственные лицензии (Apache 2.0 для audio_prj_collections).
