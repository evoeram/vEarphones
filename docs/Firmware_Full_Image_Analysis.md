# Анализ: получение полного образа прошивки vivo TWS 5i

## Устройство
- **Модель**: vivo TWS 5i
- **Чип**: BES2710
- **Project ID**: DPD2543A
- **MAC**: L=AC:40:1E:C0:BC:85, R=AC:40:1E:C0:64:D8
- **Текущая версия**: 20007 (v2.0.7)
- **Целевая версия**: 20103 (v2.1.3)
- **Размер flash**: 4 MB

## Проблема
Сервер vivo OTA отдаёт **только differential patch** (VIVDIF01), а не полный образ прошивки (4 MB).

## API эндпоинт
- **URL**: `https://ptsouweb.vivo.com.cn/ptsou/api2.do`
- **Download**: `https://ptsou-wsdl.vivo.com.cn/ptsou/zip/2026061522553190473968.bin`
- **Шифрование**: `SecurityKeyCipher.toSecurityBytes(map, 3)` — ECDH+AES-GCM via `libvivoseckey.so`
- **Параметры**: `imei`, `vercode`, `device`, `mac1`, `mac2`, `lang`, `cy`, `onlyFull`, `needH5Content`

## Тесты параметра onlyFull

| onlyFull | vercode  | Результат                          |
|----------|----------|------------------------------------|
| 0        | 20007    | ✅ success, diff (way=0, 37128 байт) |
| 0        | 0        | ❌ success:false                    |
| 1        | 20007    | ❌ success:false                    |
| 1        | 0        | ❌ success:false                    |
| 2        | 20007    | ✅ success, diff (way=0, 37128 байт) |
| 2 (orig) | 20007    | ✅ success, diff (37128 байт)       |

**Вывод**: параметр `onlyFull` не влияет на тип отдаваемого файла для прошивки. `onlyFull=1` работает только для конфигурации (`resources.do` endpoint), не для прошивки. Сервер хранит только diff-патчи.

## Тесты подмены версии (Frida)

| Подмена             | onlyFull | Результат        |
|---------------------|----------|------------------|
| vercode=0 (global)  | 2        | ❌ success:false  |
| vercode=1 (global)  | 2        | ❌ success:false  |
| vercode=10000       | 2        | ❌ success:false  |
| vercode=0 (in dobInBackground) | 0 | ❌ success:false |
| vercode=0 (in dobInBackground) | 1 | ❌ success:false |
| без подмены          | 0        | ✅ diff (37128)   |
| без подмены          | 2        | ✅ diff (37128)   |

**Вывод**: подмена `vercode` на любое значение, отличное от реального (20007), вызывает `success:false`. Сервер валидирует версию по MAC-адресу наушников.

## Скачанный файл: firmware_diff.bin

- **Размер**: 37128 байт
- **Magic**: `oviV` (0x5669766f, little-endian "Vivo")
- **Body size**: 36104 байт (offset 4)
- **Project**: 2543 (DPD2543A, offset 16)
- **Target version**: 20103 (0x4E87, offset 24)
- **Block size**: 32768 (offset 28)
- **Энтропия тела**: 7.96 бит/байт (почти максимум — шифровано/сжато)
- **Хвост**: `CRC32_OF_IMAGE=0x00000000`
- **way**: 0 (differential patch)

## Архитектура приложения

### Два пути обновления
1. **Старый путь** (`X8.a` / `CheckUpdateTask`):
   - API: `ptsou/api2.do`
   - Параметры: `onlyFull=2&needH5Content=1`
   - Шифрование: `SecurityKeyCipher.toSecurityBytes`
   - Сборка параметров: `com.vivo.vipc.databus.request.a.h()`

2. **Новый путь** (`p237sb.g` / `CheckUpdateRunnable-sps`):
   - SPS/WebView-based
   - POST с `post_data`
   - Расшифровка: `SecurityKeyCipher.decryptResponse()`
   - Callback: `BridgeUtils.CALL_JS_RESPONSE`

### Ключевые классы
- `X8.a` — CheckUpdateTask (старый путь)
- `Y8.a` — DownloadTask
- `p237sb.g` — CheckUpdateRunnable-sps (новый путь)
- `p237sb.c` — AutoCheckComponent
- `p237sb.h` — генератор параметров для config (`onlyFull=1`)
- `H8.c` — CheckResTask (для config/resources, `onlyFull=1`)
- `p009a9.d` — SmartOtaImpl
- `com.vivo.vipc.databus.request.a` — сборка параметров запроса
- `com.vivo.tws.bean.SimpleEarInfo` — данные наушников (version, MAC, project)

### way (тип обновления)
- `way=0` — differential patch
- `way=1` — smart OTA (поддерживается)
- `way=2` — smart OTA (поддерживается)
- `way=3` — нет обновления

## Frida-хуки (что сработало)

### ✅ Рабочие хуки
- `databus.a.h()` — перехват сборки параметров, замена `onlyFull`
- `X8.a.doInBackground()` — перехват запроса, подмена версии через reflection
- `X8.a.e()` — логирование JSON-ответа сервера
- `SimpleEarInfo.getLeftVersion()/getRightVersion()` — чтение/подмена версии

### ❌ Не сработало
- `p237sb.g` — класс загружается только при ручной проверке через SPS (app кэширует "последняя версия" и не вызывает этот путь)
- `p237sb.c` — та же проблема
- `okhttp3 RealCall` — класс не загрузился в main процессе

### Особенности
- App многопроцессная: main + `:ui`
- Multi-dex с ленивой загрузкой классов
- Polling каждые 2s для установки хуков по мере загрузки классов
- Доступ к полям через reflection (JADX-имена типа `f7259b` не работают в Frida)

## Вывод

**Полный образ прошивки (4 MB) невозможно получить через vivo OTA API.** Сервер хранит только differential patches. Подмена `onlyFull` или `vercode` не приводит к выдаче полного образа.

## Оставшиеся варианты

1. **BLE-дамп** — прочитать текущую прошивку с наушников через BLE (bestool/BES2710 tools, без UART)
2. **Поиск в интернете** — сторонние ресурсы с полными образами
3. **Реверс VIVDIF01** — декодировать diff-патч и реконструировать полный образ из текущей прошивки (нужен дамп текущей)
4. **Применить diff** — обновить наушники до v2.1.3 через приложение, затем сделать BLE-дамп новой версии
