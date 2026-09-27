# BES2710 (vivo TWS 5i) — Полный реверс прошивки

## КРАТКОЕ РЕЗЮМЕ

**Прошивка НЕ зашифрована.** Она использует LZMA-компрессию + формат VIVDIF01 (VIVO Differential Image Format). Декомпрессия всех 22 чанков выполнена успешно.

## Структура прошивки `firmware_20007_to_20103.bin`

```
┌──────────────────────────────────────────────────────────────────┐
│ VIVO Header    │ 0x0000–0x03FF │ 1024B │ Magic "oviV", метаданные │
├──────────────────────────────────────────────────────────────────┤
│ BES OTA Magic  │ 0x0400–0x0403 │ 4B    │ 0xFFFFFFFF              │
├──────────────────────────────────────────────────────────────────┤
│ Chunk 0        │ 0x0404+       │ var   │ [size(4,BE)][LZMA data] │
│ Chunk 1        │ ...           │ var   │ [size(4,BE)][LZMA data] │
│ ...            │               │       │                         │
│ Chunk 21       │ ...           │ var   │ [size(4,BE)][LZMA data] │
├──────────────────────────────────────────────────────────────────┤
│ CRC32 Footer   │ 0x90EF–0x9107 │ 24B   │ CRC32_OF_IMAGE=0x00000000 │
└──────────────────────────────────────────────────────────────────┘
```

### Параметры LZMA
- Props: 0x5D (lc=3, lp=0, pb=2)
- Dict size: 0x00800000 (8 MB)
- Uncompressed size: 0xFFFFFFFFFFFFFFFF (unknown)
- Формат: LZMA_ALONE (`.lzma`)

### VIVDIF01 заголовок каждого чанка (48+ байт)
```
Offset  Size  Description
0x00    8     Magic: "VIVDIF01"
0x08    8     Partition ID (LE)
0x10    8     Flash address (LE)
0x18    8     Partition size (LE)
0x20    8     Data offset (LE)
0x28    8     Number of diff blocks (LE)
0x30+   var   Diff block data
```

### 22 чанка (все декомпрессированы успешно)
| Chunk | PartID | FlashAddr | Size   | Blocks | Compressed | Decompressed | Entropy |
|-------|--------|-----------|--------|--------|------------|--------------|---------|
| 0     | 0x018  | 0x8000    | 0x8000 | 0      | 706B       | 32824B       | 0.14    |
| 1     | 0x018  | 0x8000    | 0x8000 | 0      | 542B       | 32824B       | 0.11    |
| 2     | 0x018  | 0x8000    | 0x8000 | 0      | 746B       | 32824B       | 0.28    |
| 3     | 0x510  | 0x7EBF    | 0x8000 | 38     | 1669B      | 34096B       | 0.43    |
| 4     | 0x1E0  | 0x7F3E    | 0x8000 | 22     | 2673B      | 33280B       | 0.65    |
| 5     | 0x390  | 0x7994    | 0x8000 | 32     | 3710B      | 33712B       | 1.07    |
| 6     | 0x078  | 0x7F78    | 0x8000 | 0      | 1805B      | 32920B       | 0.42    |
| 7     | 0x078  | 0x7FBD    | 0x8000 | 0      | 1529B      | 32920B       | 0.40    |
| 8     | 0x0F0  | 0x7FD5    | 0x8000 | 0      | 1601B      | 33040B       | 0.38    |
| 9     | 0x030  | 0x7F8C    | 0x8000 | 0      | 2081B      | 32848B       | 0.52    |
| 10    | 0x030  | 0x7F8C    | 0x8000 | 0      | 2544B      | 32848B       | 0.64    |
| 11    | 0x030  | 0x7F8A    | 0x8000 | 2      | 1551B      | 32848B       | 0.39    |
| 12    | 0x0A8  | 0x7F61    | 0x8000 | 0      | 1989B      | 32968B       | 0.48    |
| 13    | 0x1C8  | 0x7F31    | 0x8000 | 0      | 2540B      | 33256B       | 0.74    |
| 14    | 0x030  | 0x8000    | 0x8000 | 0      | 1714B      | 32848B       | 0.44    |
| 15    | 0x0A8  | 0x7F7B    | 0x8000 | 32     | 2400B      | 32968B       | 0.59    |
| 16    | 0x030  | 0x7FBC    | 0x8000 | 68     | 1711B      | 32848B       | 0.48    |
| 17    | 0x060  | 0x7FDE    | 0x8000 | 26     | 2102B      | 32896B       | 0.70    |
| 18    | 0x078  | 0x7FD5    | 0x8000 | 9      | 202B       | 32920B       | 0.04    |
| 19    | 0x030  | 0x7FB8    | 0x8000 | 72     | 213B       | 32848B       | 0.06    |
| 20    | 0x048  | 0x7FB8    | 0x8000 | 72     | 865B       | 32872B       | 0.37    |
| 21    | 0x180  | 0x4A5B    | 0x4A5C | 0      | 1094B      | 19452B       | 0.76    |

**Итого:** 37,128B compressed → 712,860B decompressed (5.0% compression ratio)

## Реверс KeyDll.dll

### GenerateKey()
- Возвращает ДВА статических строковых ключа:
  - Key 1: `"special protect data test"` (25 байт, RVA 0x71b78 в .rdata)
  - Key 2: `"soundplus"` (9 байт)
  - Размер возвращается как 4 для обоих
- RVA 0x25f37 — thunk table из 117 JMP rel32 (MSVC /GTL оптимизация)
- PDB путь: `D:\WorkCode\productline\download tool\extend\transferdll\Debug\KeyDll.pdb`
- Строка "DES" в .rdata — это код локали CRT (German-Switzerland), НЕ криптография

### Назначение
KeyDll.dll используется BES download tool (transferdll.dll) для OEM-шифрования при factory-прошивке через USB. **Не имеет отношения к OTA-прошивке.**

## Реверс transferdll.dll

### Экспорты (все — thunk tables, JMP rel32)
- `end_encrypt_block()` → вызывает SetEvent (KERNEL32) — сигнал завершения, НЕ шифрование
- `get_encrypt_efuse_value1()` → word at [0x10126eac] — 16-bit eFuse value 1
- `get_encrypt_efuse_value2()` → word at [0x101...] — 16-bit eFuse value 2
- `get_key_addr_from_buildinfo()` — получение адреса ключа из build info
- `Check_Signed_File_Efus()` — проверка подписи файла через eFuse
- `Set_OTP_Enable_Security_Boot_Flag()` — установка флага secure boot в OTP

### Customized_Area_Operations (0x542a0)
- Принимает: (key1_buf, key1_size, key2_buf, key2_size)
- Вызывает IAT [0x101017f4]
- Использует ключи из GenerateKey + eFuse values для factory-шифрования

### Назначение
Factory-инструмент для USB-прошивки. Шифрование конфигурируемо: `<encrypt_on>0</encrypt_on>` в productline_cfg.xml.

## Реверс programmer1502x_2700ibp.bin

- Magic: 0x1CEC57BE = BOOT_MAGIC_NUMBER
- Архитектура: ARM Cortex-M33
- Размер: 122 KB
- Назначение: bootloader для flash-операций (read, write, verify, sector management)
- **НЕ содержит криптографии** (нет AES S-box, нет XTEA, нет DES, нет SHA констант)

## APP (vivo TWS earbuds APK)

### OTA поток
1. `DefaultPolicy.startOta(File)` → `C0494g0.e().r(context, p314z5.a)`
2. `p314z5/a.java` (UpgradeHelper) читает .bin через `ContentResolver.openInputStream(uri)`
3. Считает MD5 от raw bytes
4. Передаёт byte[] + MD5 в `B5/e.java` → `B5/j.java` (UpgradeManager)
5. `E9/c.java` нарезает firmware на чанки, отправляет через BLE
6. **Приложение НЕ шифрует/дешифрует прошивку** — отправляет raw bytes

### Policy
- `PolicyFactory` выбирает policy по project/platform
- vivo TWS 5i = BES2710 = TWS2 → `Tws2Policy` (extends `DefaultPolicy`)
- `DefaultPolicy` использует Qualcomm QTI Gaia upgrade protocol
- Gaia стадии: INITIALISATION → UPLOAD → VALIDATION → REBOOT → VERIFICATION → COMPLETE

### Native libraries
- `libvivoseckey.so` (676KB) — vivo SecurityKey SDK (ECDH + AES-GCM) для APP-level коммуникации, НЕ для firmware
- Остальные .so — video editor, logging, BLE SBC, graphics

## BES SDK OTA (из build_compressed_ota.sh)

```bash
# Формат BES OTA:
# 1. Split input на 131072-byte (128KB) chunks
# 2. LZMA compress each chunk (lzma -z -k -f -9)
# 3. Output: magic(0xFFFFFFFF) + [size(4,BE)][LZMA]*N + "CRC32_OF_IMAGE=0x00000000\n"
```

BES SDK OTA код НЕ содержит шифрования — только CRC32 для проверки целостности.

## Выводы

1. **Прошивка НЕ зашифрована** — LZMA компрессия + VIVDIF01 differential format
2. **KeyDll.dll** ключи ("soundplus", "special protect data test") — для factory USB-прошивки, НЕ для OTA
3. **APP отправляет raw bytes** — не шифрует/дешифрует
4. **Bootloader** не содержит криптографии — только flash I/O
5. **Формат VIVDIF01** — differential patch для 22 flash-партиций
6. **Модификация прошивки ВОЗМОЖНА** — декомпрессировать LZMA, модифицировать VIVDIF, рекомпрессировать

## Файлы

- `firmware_20007_to_20103.bin` — оригинальная прошивка (37 KB)
- `firmware_chunks/` — 22 декомпрессированных чанка
- `firmware_chunks/full_decompressed.bin` — полная декомпрессированная прошивка (696 KB)
- `firmware_chunks/metadata.json` — метаданные чанков
