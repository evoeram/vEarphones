# BES2700/vivo TWS 5i — Полный реверс-инжиниринг SDK

## Чип: BES2700IHC (BEST1502x) / vivo TWS 5i

---

## 1. KeyDll.dll — Генератор OEM-ключей

### GenerateKey() — полный дизассемблик

```asm
GenerateKey(buf1, size1, buf2, size2):
  push ebp
  mov ebp, esp
  sub esp, 0xC0
  push ebx/esi/edi
  ; Заполнить стек 0xCC (debug fill)
  lea edi, [ebp-0xC0]
  mov ecx, 0x30
  mov eax, 0xCCCCCCCC
  rep stosd
  
  ; Записать указатель на ключ 1
  mov [ebp+8], 0x10071B78    ; → "special protect data test"
  ; Записать размер ключа 1
  mov eax, [ebp+0xC]
  mov [eax], 4               ; size = 4
  
  ; Записать указатель на ключ 2
  mov [ebp+0x10], 0x10071B6C ; → "soundplus"
  ; Записать размер ключа 2
  mov eax, [ebp+0x14]
  mov [eax], 4               ; size = 4
  
  xor eax, eax               ; return 0 (success)
  pop edi/esi/ebx
  mov esp, ebp
  pop ebp
  ret
```

### Ключи шифрования

| Ключ | Значение | RVA | Размер |
|------|----------|-----|--------|
| Key 1 | `special protect data test` | 0x71B78 | 25 байт (используется 4) |
| Key 2 | `soundplus` | 0x71B6C | 9 байт (используется 4) |

**PDB путь:** `D:\WorkCode\productline\download tool\extend	ransferdll\Debug\KeyDll.pdb`

---

## 2. transferdll.dll — Оркестратор прошивки

### Экспортируемые функции

| Функция | RVA (real) | Назначение |
|---------|-----------|------------|
| `GenerateKey` (via KeyDll) | — | Получение OEM-ключей |
| `Set_Custom_Special_Data` | 0x542A0 | Подготовка данных с ключами |
| `get_encrypt_efuse_value1` | 0x826E0 | Чтение eFuse значения 1 (16 бит) |
| `get_encrypt_efuse_value2` | 0x82720 | Чтение eFuse значения 2 (16 бит) |
| `end_encrypt_block` | 0x7E6F0 | SetEvent — сигнал завершения |
| `get_key_addr_from_buildinfo` | 0x52EE0 | Поиск FLASH_SIZE в buildinfo |
| `Check_Signed_File_Efus` | 0x82E20 | Проверка подписи файла |
| `judge_bin_file_is_valid` | 0x53220 | Валидация прошивки |
| `dldstart` | 0x81710 | Запуск прошивки |
| `dldstop` | 0x81A20 | Остановка прошивки |

### Поток шифрования

```
PC (transferdll.dll)                    Чип (bootloader)
─────────────────────                   ─────────────────
1. GenerateKey() → ключи
   "special protect data test"
   "soundplus"

2. Read eFuse → get_encrypt_efuse_value1/2
   (16-битные значения из чипа)

3. Check_Signed_File_Efus(filepath)
   Открывает файл, проверяет размер > 0x12
   Читает файл, проверяет подпись

4. Set_Custom_Special_Data(key1, size1, key2, size2)
   Строит blob с ключами + eFuse значениями
   Opcode: 0xBA80
   Копирует ключи в буфер по адресу 0x10147A00

5. Send data to chip via UART ──────────→ 6. Bootloader принимает данные
                                           programmer_main()
                                           
                                           7. SEC_BURN / BURN_DATA
                                           Запись во flash
                                           
                                           8. CRC verify
                                           "Bad CRC" → error
                                           
                                          ←── 9. SetEvent (end_encrypt_block)
                                           Сигнал завершения
```

### Строки шифрования в .rdata

| RVA | Строка |
|-----|--------|
| 0xE73FC | `encrypted mode,efuse_flag = %d` |
| 0xE73CC | (сообщение об ошибке buildinfo) |
| 0xE73D0 | `key_addr_from_buildinfo` |
| 0xE7228 | `FLASH_SIZE=` |
| 0xE7090 | `CRC32_OF_IMAGE=` |
| 0xF1514 | `signed key efuse value:0x%04x, verified value:0x04X%` |
| 0xF156C | `signed file failed: %s` |
| 0xEB114 | `GenerateKey failed, please check keydll` |
| 0xEB150 | `Set custom special data error` |
| 0xEB180 | `customized data address:0x%x` |
| 0xEB1B0 | `keydll Generate customized data` |
| 0xEB1E4 | `Customized_Area_Operations` |

---

## 3. programmer1502x_2700ibp.bin — Bootloader

### Структура

| Параметр | Значение |
|----------|----------|
| Размер | 121,672 байт |
| Magic | 0xBE57EC1C (BOOT_MAGIC_NUMBER) |
| Header | 16 байт, затем нули до 0x61C |
| Code | 0x61C – ~0x14400 |
| Strings | 0x14400 – 0x1DB08 |
| Build | Oct 18 2024 16:50:20 |
| Git | b8b9f8c977-dirty |
| Variant | prod_test/bt_calib |
| Архитектура | ARM Cortex-M33 (Thumb-2) |

### Заголовок

```
0x00: 1C EC 57 BE  — magic (BOOT_MAGIC_NUMBER)
0x04: 01 00 04 00  — version (0x00040001)
0x08: 00 00 00 00  — reserved
0x0C: 44 DD 0B 20  — entry point / SRAM addr (0x200BDD44)
```

### Поддерживаемые чипы

| Чип | Метка в строках |
|-----|-----------------|
| BES2600ZP | `2600ZP %s write error efuse` |
| BES2700L | `2700L %s write error efuse` |
| BES2700IBP | `btdrv_txpower_calib_sel_calib_idx_2700IBP_2700H` |

### Команды протокола UART

#### SYS CMD
- `Reboot` — перезагрузка
- `Shutdown` — выключение
- `Flash boot` — загрузка из flash
- `Set/Clear/Get bootmode` — управление bootmode
- `Set download rate` — скорость загрузки

#### FLASH CMD
- `CMD_GET_ID` — получить ID flash
- `CMD_GET_UNIQUE_ID` — уникальный ID
- `CMD_GET_SIZE` — размер flash
- `CMD_GET_CTRL_INFO` — информация о контроллере
- `CMD_ERASE_CHIP` — стереть весь чип
- `CMD_ENABLE_REMAP` / `CMD_DISABLE_REMAP` — ремаппинг адресов
- `GET_LOCK_STATUS` — статус блокировки

#### DATA Operations
- `SEC_READ` — чтение security register
- `SEC_LOCK` — блокировка security register
- `SEC_ERASE` — стирание security register
- `ERASE_SECTOR` — стирание сектора
- `BURN_DATA` — запись данных
- `SEC_BURN` — запись в security register
- `SEC_ERASE_BURN_DATA` — стирание + запись
- `BULK_WRITE_DATA` — массовая запись

#### EXTEND CMD
- `REG_OP_WRITE` — запись регистра
- `REG_OP_READ` — чтение регистра
- `EFUSE_OP_READ` — чтение eFuse

### Криптография в bootloader

**НЕТ стандартных крипто-констант:**
- ❌ AES S-box
- ❌ DES S-box / IP table
- ❌ XTEA/TEA delta (0x9E3779B9)
- ❌ SHA-1/MD5 init values
- ❌ SHA-256 K[] constants

**Bootloader НЕ выполняет шифрование/дешифрование!**
Он только читает/записывает raw flash данные.
Шифрование выполняется на стороне PC (transferdll.dll + KeyDll.dll).

---

## 4. productline_cfg.xml — Конфигурация

```xml
<encrypt_on>0</encrypt_on>      <!-- Шифрование ВЫКЛЮЧЕНО по умолчанию -->
<keypath />                      <!-- Путь к файлу ключа (пустой) -->
<chipver>1306p</chipver>        <!-- Версия чипа -->
<baudrate>921600</baudrate>     <!-- Скорость UART -->
```

**Шифрование — опциональная функция!** Включается через `<encrypt_on>1</encrypt_on>`.

---

## 5. Прошивка vivo TWS 5i

### Формат файла

| Смещение | Размер | Значение |
|----------|--------|----------|
| 0x00 | 4 | Magic: `oviV` (0x5669766F LE) |
| 0x04 | 4 | Размер данных: 36104 (0x8D08) |
| 0x08 | 4 | CRC/Hash: 0x0688F566 |
| 0x0C | 4 | 0 (reserved) |
| 0x10 | 4 | Версия: 2543 (0x09EF) |
| 0x14 | 4 | Флаги: 0x003C0003 |
| 0x18 | 4 | 0x01014E87 |
| 0x1C | 4 | Размер блока: 32768 (0x8000) |
| 0x20 | 4 | Дубликат: 36104 (0x8D08) |
| 0x24 | 4 | Дубликат CRC: 0x0688F566 |
| 0x28 | 4 | 0x00B60001 |
| 0x2C | 4 | 0x00030000 |
| 0x30+ | ~ | Метаданные чанков (перемежаются с 0x01) |
| 0xC0+ | 0 | Zero padding до начала данных |
| ~0x0B5+ | ~36000 | Зашифрованные данные (entropy 7.99/8.0) |

### Строки в прошивке

| Смещение | Строка |
|----------|--------|
| 0x90EF | `CRC32` |

### Анализ энтропии
- Энтропия данных: **7.9948 / 8.0** → зашифровано
- Повторяющихся 16-байтных блоков: **0** → не ECB
- Вероятный алгоритм: **AES-CBC** или потоковый шифр

---

## 6. Ключи шифрования (извлечены из KeyDll.dll)

```
Key 1: "special protect data test" (hex: 73 70 65 63 69 61 6C 20 70 72 6F 74 65 63 74 20 64 61 74 61 20 74 65 73 74)
Key 2: "soundplus"                   (hex: 73 6F 75 6E 64 70 6C 75 73)
```

Size field = 4 для обоих ключей. Возможные интерпретации:
1. Используются только первые 4 байта: `spec` (0x73706563) и `soun` (0x736F756E)
2. Size = 4 DWORD'а = 16 байт: `spec ial _pro tect` и `soun dplu s       `
3. Size = количество элементов в key schedule

---

## 7. BES SDK OTA (справочно)

BES2700IHC SDK (sprlightning/audio_prj_collections):
- `services/ota/bes_ota/src/ota_control.cpp` (135,851 байт) — только CRC32
- `tools/build_compressed_ota.sh` — LZMA компрессия
- `scripts/link/tail_section.lds.S` — формат хвоста прошивки

**BES SDK НЕ содержит шифрования.** Шифрование добавлено OEM-слоем (vivo).

---

## 8. Инструменты для модификации прошивки

###已有的 инструменты

| Инструмент | Источник | Назначение |
|-----------|----------|------------|
| KeyDll.dll | Derek-Vencer/tws_earbuds | OEM ключи |
| transferdll.dll | Derek-Vencer/tws_earbuds | Оркестратор |
| programmer1502x_2700ibp.bin | Derek-Vencer/tws_earbuds | Bootloader |
| BES2700IHC SDK | sprlightning/audio_prj_collections | Сборка прошивки |
| OpenPineBuds | pine64/OpenPineBuds | Open-source BES firmware |
| bestool | nnonickreal/openqore | UART read/write flash |
| besota.py | nnonickreal/besota | BLE OTA flasher |

### Следующие шаги для расшифровки

1. **Попробовать ключи как XOR** — простейший вариант
2. **Попробовать AES-CBC с key1/key2** — 16 байт из первых 16 символов строк
3. **Попробовать DES** — строки "DES" в .rdata locale table (возможно coincidence)
4. **Динамический анализ** — загрузить transferdll.dll в debugger,
   вызвать GenerateKey, перехватить Set_Custom_Special_Data,
   посмотреть реальный ключ после обработки
5. **UART дамп** — подключиться к наушнику через UART,
   прочитать flash и eFuse через bestool
