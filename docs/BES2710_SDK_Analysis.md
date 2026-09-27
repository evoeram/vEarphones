# BES2710 SDK для модификации прошивки vivo TWS 5i — полный анализ

## Краткий вывод

**Прошивка vivo TWS 5i зашифрована OEM-ключом, привязанным к eFuse чипа.** Стандартный BES SDK не содержит шифрования — только CRC32. vivo добавила свой слой шифрования поверх формата BES. Для модификации прошивки необходимо получить OEM-ключ через анализ `KeyDll.dll` или реверс-инжиниринг загрузчика BES2710.

---

## 1. Архитектура чипов BES

### Соответствие имён

| Marketing name | BES internal name | Использование | Фокус |
|---|---|---|---|
| **BES2710IUC** | **BEST1502x** | **vivo TWS 5i** | TWS аудио |
| BES2710IHC | BEST1306 | TWS наушники (общий) | Аудио |
| BES2700iMP | BEST1503 | Xiaomi Mi Band 10 | Носимый |
| BES2300P | — | Soundcore Q35 | TWS аудио |

### BES2710 = BEST1502x

- ARM Cortex-M33 (dual-core STAR-MC1 + BECON NPU)
- 4MB flash, ~512KB SRAM (BEST1306), до 1.4MB (BEST1503)
- BLE + классический BT
- BES proprietary RTOS (RTX5)
- Дatasheet: https://datasheet.icspec.com/datasheet/datasheetDetail/119879

---

## 2. Репозитории и их ценность

### A. sprlightning/audio_prj_collections — BES2700IHC SDK (LEAKED)

**URL:** https://github.com/sprlightning/audio_prj_collections

Полный leaked SDK для BES2700IHC (BEST1306). Содержит:
- Build system (kbuild, Makefile)
- RTOS (RTX5)
- BT host stack
- HAL (clocks, GPIO, flash, UART, I2C/SPI, PMU)
- OTA service (`services/ota/bes_ota/`)
- Audio codecs (SBC, AAC, OPUS, LHDC, LDAC, LC3, L2HC)
- Linker scripts для всех BES чипов
- Инструменты: `lzma`, `build_compressed_ota.sh`, `bin2ascii.pl`

**Ключевые файлы для прошивки:**
- `tools/build_compressed_ota.sh` — формат OTA образа
- `services/ota/bes_ota/src/ota_control.cpp` — протокол OTA (3920 строк)
- `services/ota/bes_ota/inc/ota_control.h` — структуры и константы
- `scripts/link/tail_section.lds.S` — layout flash-памяти

### B. Derek-Vencer/tws_earbuds — BES Flashing Tool + Bootloader (LEAKED)

**URL:** https://github.com/Derek-Vencer/tws_earbuds

Factory flashing tool + SecondStage bootloader blobs для ВСЕХ BES чипов.

**Критические файлы:**
| Файл | Размер | Назначение |
|---|---|---|
| `BES_DldProductLine_VS1.70.8/BES_DldProductline.exe` | 1.9MB | Factory flashing tool |
| `BES_DldProductLine_VS1.70.8/KeyDll.dll` | 396KB | **Генерация OEM-ключа** |
| `BES_DldProductLine_VS1.70.8/transferdll.dll` | 808KB | Логика прошивки/шифрования |
| `BES_DldProductLine_VS1.70.8/programmer1502x_2700ibp.bin` | 122KB | **SecondStage bootloader для BES2710** |
| `BES_DldProductLine_VS1.70.8/programmer1502x_2700h.bin` | 122KB | Bootloader для BES2710 (HC variant) |
| `BES_DldProductLine_VS1.70.8/programmer1502x_2700L.bin` | 122KB | Bootloader для BES2710 (L variant) |
| `BES_DldProductLine_VS1.70.8/programmer1306.bin` | 127KB | Bootloader для BEST1306 |
| `BES_DldProductLine_VS1.70.8/programmer1503.bin` | 114KB | Bootloader для BEST1503 (Mi Band 10) |

### C. atc1441/MiBand10-BES2700iMP-BEST1503-Hacking — Custom Firmware

**URL:** https://github.com/atc1441/MiBand10-BES2700iMP-BEST1503-Hacking

Рабочий SDK для BES2700iMP (BEST1503) на основе BEST1306 SDK. Демонстрирует:
- Адаптация BEST1306 → BEST1503 (memory map, clocks, display, touch)
- Flashing через UART Python flasher
- Использование SecondStage bootloader из репозитория Derek-Vencer
- Build: `make T=best1503 CHIP=best1503`

### D. pine64/OpenPineBuds — BES2300 SDK + bestool

**URL:** https://github.com/pine64/OpenPineBuds

SDK для PineBuds Pro (BES2300). Содержит:
- Полный build через Docker
- Реверс-инжиниренный `bestool` (read/write flash)
- Backup/flash скрипты
- Кастомная прошивка с изменениями аудио

### E. nnonickreal/openqore — BES Firmware Patcher

**URL:** https://github.com/nnonickreal/openqore

Toolkit для модификации прошивки BES-наушников (Soundcore Q35, BES2300P):
- `qorepatcher` — патчер прошивки (замена звуков, 16kHz→48kHz)
- `besota` — OTA flasher через BLE RFCOMM
- `bestool-ng` — read/write flash через UART
- Документация по UART подключению, чтению/прошивке

### F. nnonickreal/besota — BLE OTA Flasher

**URL:** https://github.com/nnonickreal/besota

Python скрипт для прошивки BES наушников по BLE:
- Протокол BESOTA v1 (BES2300-2600)
- Команды: handshake (0x8E), metadata (0x80), erase (0x86), data (0x85), CRC (0x82), apply (0x88), finish (0x92)
- CRC32 патчинг прошивки перед прошивкой
- Поддержка Windows (native BT socket) и Linux

---

## 3. Формат прошивки BES (стандартный)

### OTA Image (build_compressed_ota.sh)

```
┌─ Magic: FF FF FF FF (4 байта)
├─ Chunk 0: [4B size LE][LZMA compressed data (128KB block)]
├─ Chunk 1: [4B size LE][LZMA compressed data]
├─ ...
├─ Chunk N: [4B size LE][LZMA compressed data]
└─ Tail: "CRC32_OF_IMAGE=0x00000000\n"
```

- Исходный файл делится на блоки по 131072 байт (128KB)
- Каждый блок сжимается LZMA (-9)
- Перед каждым блоком — 4B размер (LE) сжатых данных
- CRC32 вычисляется по данным до marker'а, записывается в хвост

### Flash Layout (tail_section.lds.S)

```
FLASH: [CODE] [OTA_APP_BOOT_INFO] [AUD] [COMBO] [PROMPT] [HOTWORD]
       [RAM_DUMP] [CORE_DUMP] [OTA_UPGRADE] [LOG_DUMP] [CRASH_DUMP]
       [CUSTOM_PARAMETER] [LHDC_LICENSE] [USERDATA ×2] [ANC] [RESERVED] [FACTORY]
```

- `OTA_CODE_OFFSET = 0x180000` (образ OTA пишется начиная с этого смещения)
- `FLASH_SECTOR_SIZE = 4096` (4KB)
- `BOOT_MAGIC_NUMBER = 0xBE57EC1C`

### OTA протокол (ota_control.h)

| Команда | Code | Направление | Назначение |
|---|---|---|---|
| OTA_COMMAND_START | 0x80 | App→Device | Начать OTA |
| OTA_RSP_START | 0x81 | Device→App | Готов |
| OTA_COMMAND_SEGMENT_VERIFY | 0x82 | App→Device | CRC32 сегмента |
| OTA_RSP_SEGMENT_VERIFY | 0x83 | Device→App | Результат CRC |
| OTA_DATA_PACKET | 0x85 | App→Device | Данные прошивки |
| OTA_COMMAND_CONFIG_OTA | 0x86 | App→Device | Конфигурация |
| OTA_COMMAND_GET_OTA_RESULT | 0x88 | App→Device | Финальная проверка |
| OTA_DATA_ACK | 0x8B | Device→App | ACK (SPP) |
| OTA_COMMAND_RESUME_VERIFY | 0x8C | App→Device | Возобновление |
| OTA_COMMAND_GET_VERSION | 0x8E | App→Device | Получить версию |
| OTA_COMMAND_SIDE_SELECTION | 0x90 | App→Device | Выбор стороны (L/R) |
| OTA_COMMAND_IMAGE_APPLY | 0x92 | App→Device | Применить образ |
| OTA_CMD_GET_OTA_VERSION | 0x99 | App→Device | Версия протокола OTA |

**BES_OTA_START_MAGIC_CODE = 0x54534542 ("BEST")**

---

## 4. Шифрование прошивки

### Архитектура шифрования BES

```
┌──────────────────────────────────────────────────────────┐
│ Factory Flashing Tool (BES_DldProductline.exe)           │
│  └─ transferdll.dll                                      │
│       ├─ Reads eFuse from chip (get_encrypt_efuse_value) │
│       ├─ Calls KeyDll.dll::GenerateKey()                 │
│       │   └─ Combines eFuse + OEM secret → AES/DES key   │
│       ├─ Encrypts firmware sections                      │
│       ├─ Burns security register magic numbers           │
│       └─ Writes encrypted data to flash                  │
└──────────────────────────────────────────────────────────┘
```

### KeyDll.dll — анализ

| Параметр | Значение |
|---|---|
| Экспорт | `GenerateKey` (единственный) |
| Импорты | KERNEL32.dll (RegOpenKeyExW, RegCloseKey) |
| PDB путь | `D:\WorkCode\productline\download tool\extend\transferdll\Debug\KeyDll.pdb` |
| Размер | 396,288 байт |
| Алгоритм | Вероятно DES (найден "DES" string, таблицы перестановок) |

**GenerateKey** — генерирует ключ шифрования на основе:
1. eFuse значений чипа (уникальных для каждого чипа)
2. OEM-специфичных данных (из реестра Windows или hardcoded)
3. Внутренней логики (таблицы перестановок в .data секции)

### transferdll.dll — анализ

Экспортируемые функции шифрования:
- `end_encrypt_block` — завершение блока шифрования
- `get_encrypt_efuse_value1` / `get_encrypt_efuse_value2` — чтение eFuse
- `get_key_addr_from_buildinfo` — получение адреса ключа из build info
- `Check_Signed_File_Efus` — проверка подписи файла
- `Set_OTP_Enable_Security_Boot_Flag` — включение secure boot
- `Custom_Special_Data_Protected` — защита кастомных данных
- `get_app_crc` — получение CRC приложения

Ключевые строки из логов:
```
"Non-encrypted mode, efuse_flag = %d"        → шифрование опционально
"GenerateKey failed, please check keydll"     → ключ из KeyDll
"key dll authorized failed"                   → KeyDll требует авторизацию
"call keyDLL.dll in download process:0X%X"    → вызов в процессе прошивки
"signed key efuse value:0x%04x"               → ключ связан с eFuse
"keydll Generate customized data"             → генерация кастомных данных
```

### Цепочка безопасности

```
1. eFuse на чипе → хранит уникальный ID + флаги шифрования
2. KeyDll.dll::GenerateKey(eFuse) → OEM ключ шифрования
3. transferdll.dll → шифрует секции прошивки
4. Security Register → magic numbers для верификации
5. OTP (One-Time Programmable) → permanent secure boot flag
6. Bootloader (programmer*.bin) → проверяет подпись при загрузке
```

### Vivo TWS 5i — формат прошивки

```
┌─ Header (512 байт, 0x00-0x1FF)
│   ├─ Magic: 'oviV' (0x6F766956)
│   ├─ Payload size: 0x8D08 (36104)
│   ├─ Build hash: 0x0688F566
│   ├─ VerCode: 20103 (0x4E87)
│   ├─ Flash sector: 32768 (0x8000)
│   ├─ 22 partition entries (5B каждая: 01 + 4B data)
│   └─ Zero padding (0xB6-0x1FB)
│
├─ Meta chunk (0x1FC-0x409, 526 байт, ENCRYPTED)
│   └─ End: 00 00 [CRC16=0xC202] 5D 00
│
├─ Data chunk 0-21 (0x40A-0x90EE)
│   ├─ Start: 00 80 00 FF FF FF FF FF FF (9B)
│   ├─ Sync:  2B 12 47 11 97 94 B2 77 (8B, ОДИНАКОВЫЙ для всех)
│   ├─ Data:  [encrypted] (variable size, 180-3688 байт)
│   └─ End:   00 00 [CRC16 LE] 5D 00 (6B)
│
└─ Footer (0x90EF-0x9107, 24 байт)
    └─ "CRC32_OF_IMAGE=0x00000000"
```

**Анализ шифрования:**
- Энтропия данных чанков: **7.99/8.0** → сильное шифрование
- **0 повторяющихся 16-байт блоков** → не ECB
- **0 повторяющихся 8-байт блоков** → не простой XOR
- Sync паттерн одинаковый для всех 22 чанков → фиксированный IV
- CRC16 в end-маркере не проходит на зашифрованных данных → CRC на plaintext
- XOR с sync паттерном не даёт читаемый текст → не XOR

---

## 5. Пути расшифровки

### Путь A: Анализ KeyDll.dll (НАИБОЛЕЕ ПЕРСПЕКТИВНЫЙ)

**Задача:** Реверс-инжиниринг `GenerateKey()` функции

**Что нужно:**
1. Загрузить `KeyDll.dll` в IDA Pro / Ghidra
2. Найти функцию `GenerateKey` (RVA 0x25F37, file offset 0x1337)
3. Декомпилировать и понять алгоритм генерации ключа
4. Определить, какие eFuse значения используются
5. Понять, как комбинируются eFuse + OEM секрет

**Файлы для анализа:**
- `C:\Users\User\Desktop\vEarphones\KeyDll.dll` (396KB)
- `C:\Users\User\Desktop\vEarphones\transferdll.dll` (808KB)
- `C:\Users\User\Desktop\vEarphones\programmer1502x_2700ibp.bin` (122KB)

**Сложность:** Средняя. KeyDll всего 396KB, один экспорт, импортирует только KERNEL32.

### Путь B: Реверс-инжиниринг bootloader'а

**Задача:** Декомпилировать SecondStage bootloader для BES2710

**Файл:** `programmer1502x_2700ibp.bin` (121,672 байт)
- Magic: `1C EC 57 BE` = BOOT_MAGIC_NUMBER (0xBE57EC1C)
- Это ARM Cortex-M33 бинарник
- Загрузить в Ghidra как ARM little-endian
- Найти функции дешифрования

**Сложность:** Высокая. ARM binary без символов.

### Путь C: UART доступ к наушнику

**Задача:** Получить debug UART доступ к vivo TWS 5i

**Что нужно:**
1. Разобрать наушник
2. Найти UART pads на PCB
3. Подключиться USB-UART адаптером
4. Использовать `bestool` (из OpenPineBuds) или `bestool-ng` (из openqore)
5. Прочитать flash напрямую (backup)
6. Найти ключ в RAM или flash

**Инструменты:**
- `bestool` (OpenPineBuds): `bestool read-image --port /dev/ttyACM0`
- `bestool-ng` (openqore): улучшенная версия
- Baudrate: 921600 (из productline_cfg.xml)

**Сложность:** Средняя (нужно вскрытие наушника).

### Путь D: BLE OTA с модифицированным образом

**Задача:** Отправить модифицированный образ через BLE OTA

**Подход:**
1. Использовать `besota.py` (nnonickreal) как основу
2. Адаптировать протокол для BES2710 (vivo TWS 5i использует BLE, не RFCOMM)
3. Протокол vivo: commands 1,4,7,11,19,20 (из K5.a)
4. Отправить стандартный BES образ (без шифрования) и проверить:
   - Принимает ли bootloader незашифрованный образ?
   - Какая ошибка возникает? (27=OEM validation, 56-62=various)

**Риск:** Может брикнуть наушник.

### Путь E: Перехват ключа при factory flashing

**Задача:** Перехватить ключ во время factory прошивки

**Подход:**
1. Запустить `BES_DldProductline.exe` под отладчиком (x64dbg)
2. Поставить breakpoint на `GenerateKey` в KeyDll.dll
3. Перехватить сгенерированный ключ
4. Понять входные данные (eFuse values)

**Сложность:** Низкая, но нужен BES programmer hardware.

---

## 6. Инструменты для работы

### Build (компиляция прошивки)

| Инструмент | Назначение |
|---|---|
| BES2700IHC SDK | Базовый SDK (build system, HAL, RTOS) |
| arm-none-eabi-gcc 10.3 | Toolchain для ARM Cortex-M33 |
| MSYS2 make 4.4.1 | Сборка (Windows) |
| `build_compressed_ota.sh` | Создание OTA образа из .bin |

### Flash (прошивка)

| Инструмент | Назначение |
|---|---|
| `bestool` / `bestool-ng` | UART flash (read/write) |
| `besota.py` | BLE OTA flasher |
| `BES_DldProductline.exe` | Factory flashing tool |
| `programmer1502x_2700ibp.bin` | SecondStage bootloader |

### Reverse Engineering

| Инструмент | Назначение |
|---|---|
| IDA Pro / Ghidra | Декомпиляция KeyDll.dll, bootloader |
| jadx | Декомпиляция APK |
| `binwalk` | Анализ бинарников |

### Analysis

| Инструмент | Назначение |
|---|---|
| Python + struct | Анализ формата прошивки |
| `lzma` | Декомпрессия LZMA чанков |

---

## 7. Конкретные шаги для расшифровки

### Шаг 1: Реверс KeyDll.dll в Ghidra

```
1. Создать проект Ghidra (ARM/x86 — это x86 DLL)
2. Импортировать KeyDll.dll (PE32, x86)
3. Найти экспорт GenerateKey (RVA 0x25F37)
4. Декомпилировать функцию
5. Найти:
   - Какие данные читаются из реестра (RegOpenKeyExW)
   - Какие таблицы используются (DES permutations в .data)
   - Как формируется ключ
```

### Шаг 2: Реверс transferdll.dll — найти вызовы шифрования

```
1. Импортировать transferdll.dll в Ghidra
2. Найти строки:
   - "Non-encrypted mode,efuse_flag = %d" → логика шифрования
   - "call keyDLL.dll in download process" → точка вызова
   - "end_encrypt_block" → функция шифрования
3. Найти функции: get_encrypt_efuse_value1/2, end_encrypt_block
4. Понять, какие части прошивки шифруются
```

### Шаг 3: Реверс bootloader programmer1502x_2700ibp.bin

```
1. Импортировать в Ghidra как ARM Cortex-M33 little-endian
2. Magic 0x1CEC57BE в начале = boot header
3. Найти функции дешифрования (поиск констант:
   - AES S-box: 63 7C 77 7B...
   - XTEA: 0x9E3779B9
   - DES S-boxes
4. Найти, как bootloader проверяет OEM signature
```

### Шаг 4: Извлечь eFuse из наушника

```
1. Подключиться по UART к vivo TWS 5i
2. Использовать bestool для чтения eFuse
3. Или: использовать BLE команду для запроса eFuse
4. Получить encrypt_efuse_value1 и encrypt_efuse_value2
```

### Шаг 5: Сгенерировать ключ и расшифровать

```
1. Запустить GenerateKey с eFuse значениями
2. Получить OEM ключ
3. Расшифровать чанки прошивки
4. Модифицировать (например, изменить audio_effect)
5. Зашифровать обратно
6. Обновить CRC32_OF_IMAGE
7. Прошить через BLE OTA или UART
```

---

## 8. Структура файлов проекта

```
C:\Users\User\Desktop\vEarphones\
├── vivo tws5i.md                          # Исходная документация
├── BES2710_SDK_Analysis.md                # Этот файл
├── firmware_20007_to_20103.bin            # Зашифрованная прошивка vivo
├── vEarphones  5.0.2.2.41.2.apk          # APK приложения
├── apktool_out/                           # Smali/resources
├── sources/                               # Java sources (jadx)
├── KeyDll.dll                             # ★ Генератор OEM-ключа
├── transferdll.dll                        # ★ Логика прошивки/шифрования
├── programmer1502x_2700ibp.bin            # ★ Bootloader BES2710
├── apktool.jar                            # Apktool 2.10.0
└── (downloaded from Derek-Vencer/tws_earbuds)
```

---

## 9. Выводы

1. **Прошивка зашифрована.** Энтропия 7.99/8.0, ноль повторяющихся блоков, не XOR.

2. **Шифрование — OEM-специфичное.** BES SDK не содержит шифрования. vivo (или BES по заказу vivo) добавила шифрование через `KeyDll.dll::GenerateKey()`.

3. **Ключ привязан к eFuse.** Каждый чип имеет уникальные eFuse значения. Ключ генерируется на лету при factory прошивке.

4. **Три пути расшифровки:**
   - **Реверс KeyDll.dll** (x86 DLL, 396KB, 1 экспорт) — наиболее реалистичный
   - **Реверс bootloader** (ARM binary, 122KB) — сложнее, но ключ там
   - **UART доступ** — прочитать flash/eFuse напрямую с наушника

5. **Стандартный BES SDK доступен.** BES2700IHC SDK (leaked) + OpenPineBuds + openqore дают полную базу для сборки кастомной прошивки — **после** расшифровки.

6. **bestool может читать flash.** После UART подключения можно сделать полный дамп flash (включая bootloader, ключи, калибровку).

7. **besota.py — основа для BLE OTA.** Скрипт реализует протокол BESOTA и может быть адаптирован для vivo TWS 5i (BLE вместо RFCOMM).
