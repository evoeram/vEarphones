# vivo TWS 5i — полная техническая документация

## Базовая информация

| Параметр | Значение |
|----------|----------|
| Модель | vivo TWS 5i |
| Model ID | 206 |
| Проект | DPD2543A |
| Платформа чипа | BES2710IUC |
| Тип чипа | BES2710 (TWS2 в классификации vivo) |
| Текущая версия firmware | 2.0.7 (vercode 20007) |
| Доступная версия firmware | 2.1.3 (vercode 20103) |
| Версия charging case | 1.1.8 (118) |
| MAC left | AC:40:1E:C0:BC:85 |
| MAC right | AC:40:1E:C0:64:D8 |

## Подключение

- Bluetooth BLE (не классический BT для управления)
- Приложение: `com.vivo.vivotws` (vEarphones 5.0.2.2.41.2)
- APK: `C:\Users\User\Desktop\vEarphones\vEarphones  5.0.2.2.41.2.apk`
- UUID для BLE GATT: `K9.a.f3297b` (характеристика уведомлений)

## Звуковые пресеты (audio effect)

### Текущая конфигурация (TWS 5i)

| Поле | Значение |
|------|----------|
| `audio_effect` | 4 (0b00000100) |
| `version_upgrade` | 3 |
| `smart_upgrade` | 0 |

### Битовая маска audio_effect

| Бит | Значение | Описание |
|-----|----------|----------|
| bit 0 (1) | ? | Базовый пресет |
| bit 2 (4) | установлен | TWS 5i базовый режим |
| bit 3 (8) | DeepX | Пользовательская настройка звука (DEEP_X активность) |
| bit 5 (32) | Master | Режим «至臻大师» / Ultimate Master (SHCM) |

### Доступные пресеты при audio_effect=4 (5 штук)

| ID | Название (CN) | Название (EN) | Описание |
|----|---------------|---------------|----------|
| 0 | 原声 | Original Sound | Базовый, без обработки |
| 1 | 清透人声 | Clear Vocal | Чистый вокал |
| 2 | 深沉低音 | Deep Bass | Глубокий бас |
| 3 | 通透高音 | Brilliant Treble | Прозрачные высокие |
| 5 | 3D 影院 | 3D Surround | Объёмное звучание |

### Пресеты при audio_effect=28 (TWS 5 Pro, 7 штук)

| ID | Название (CN) | Название (EN) |
|----|---------------|---------------|
| 0 | 原声 | Original Sound |
| 1 | 清透人声 | Clear Vocal |
| 2 | 深沉低音 | Deep Bass |
| 3 | 通透高音 | Brilliant Treble |
| 4 | 电影 | Movie |
| 5 | 3D 影院 | 3D Surround |
| 11 | 至臻大师 | Ultimate Master (SHCM) |

### Массивы пресетов в приложении

| Массив | Resource ID | Пресеты | Назначение |
|--------|-------------|---------|------------|
| `movie_book_master` | 0x7f03004f / 0x7f030050 | 0,1,2,3,4,5,11 (7) | Полный набор (TWS 5 Pro) |
| `listen_book` | 0x7f030046 / 0x7f030047 | 0,1,2,3,5 (5) | TWS 5i базовый |
| `moba_shoot_race_role_other` | 0x7f030048 / 0x7f030049 | 0,1,2,3,6,7,8,9,10 (9) | Игровые пресеты (недоступны на TWS 5i — firmware ремапит на 4) |

### Логика выбора массива пресетов

Массив выбирается в двух местах кода по значению `audio_effect`:

1. **`J9/c.smali`** — метод выбора массива по `audio_effect`
   - `goto :cond_c` патч → загружает `movie_book_master` независимо от audio_effect
   - НЕ сработал: DeepX требует bit 8, который у TWS 5i отсутствует

2. **`Qa/i.smali`** — два метода:
   - **`n()`** (строки ~4864–6510) — fallback путь, вызывается при отсутствии BLE-наушников
     - Патч: `goto :cond_5` → грузит `movie_book_master`
   - **`p()`** (строки ~6618–9831) — **основной runtime путь**, вызывается при подключённых наушниках по BLE с hardware features
     - `cond_11` (v4==4, audio_effect=4) → грузит `listen_book` (5 пресетов)
     - Патч: `goto :cond_d` → грузит `movie_book_master` (7 пресетов)

### Почему патчи не работают (7 пресетов не появляются)

Значение `audio_effect=4` приходит **от наушника по BLE** при каждом подключении. Патч APK меняет выбор массива в коде, но:

1. **CommonListPreference** (`com.vivo.tws.settings.home.widget`) проверяет `audio_effect_version & 8 == 8` (метод `g0()`). Если bit 8 не установлен (TWS 5i: 4), и key=`audio_effect`, то preference помечается как **отключённая** (`f13280u1 = true`). При `g0()=false` вызывается `super.u()` — стандартный диалог с теми entries, которые были установлены.

2. **Firmware наушника** — это конечный источник правды. Значения 6–10 (MoBA, SHOOT, RACE, ROLE, OTHER) firmware ремапит обратно на 4 при получении. Пресет 11 (Master) требует bit 5 (32) в audio_effect, который у TWS 5i не установлен.

3. Возможные причины неудачи патчей:
   - Третье место установки entries (не найдено)
   - CommonListPreference имеет свою логику фильтрации
   - Путь выполнения в `p()` не достигается из-за другого условия
   - Значение `audio_effect` кэшируется в SharedPreferences и перезатирается при переподключении

### TWS Config JSON

Хранится в SharedPreferences: `earbud_attr_sp.xml`
Содержит конфиг всех моделей наушников vivo (TWS 1/2/Neo/3/4/5/5i/5e/5 Pro, iQOO, Buds Clip, Headphones).
TWS 5i: `audio_effect=4`, `version_upgrade=3`, `smart_upgrade=0`
TWS 5 Pro: `audio_effect=28` (7 пресетов включая Master)
Config скачивается с сервера через `H8/c.java` (CheckResTask)

## OTA Firmware

### Сервер обновлений

| Параметр | Значение |
|----------|----------|
| URL API | `https://ptsouweb.vivo.com.cn/ptsou/api2.do` |
| Метод | POST |
| Параметры | imei, vercode, device=DPD2543A, mac1, mac2, lang, cy, thirdVer, onlyFull, needH5Content |
| Ответ | JSON: `{ redirect, data: { zip: {url, md5, len}, vercode, version, way } }` |
| Требование | Factory-подпись приложения (debug-подпись → `retcode: 20000, "加密失败"`) |

### Firmware URL (перехвачен через logcat)

```
https://ptsou-wsdl.vivo.com.cn/ptsou/zip/2026061522553190473968.bin
```

| Параметр | Значение |
|----------|----------|
| Размер | 37,128 байт |
| SHA256 | `78df435e8e0ed2c9882d0cdeaaa28f0b8cd0ae376da14344ac43116d3b97e860` |
| Версия | v2.1.3 (vercode 20103) |
| Changelog | "Updated the firmware OTA upgrade mechanism to improve the stability and speed of updates. Optimized system stability to improve user experience." |

### Release notes

- EN: `https://ptsou-wsdl.vivo.com.cn/ptsou/lvg/2026/07/2026072316294417946747/new_en-us.json`
- CN: `https://ptsou-wsdl.vivo.com.cn/ptsou/lvg/2026/07/2026072316294417946747/new.json`

### Файл на диске

```
C:\Users\User\Desktop\vEarphones\firmware_20007_to_20103.bin
```

## Формат firmware .bin (BES2710)

### Общая структура

| Секция | Offset | Размер | Описание |
|--------|--------|--------|----------|
| Header | 0x0000 | 512B | Метаданные firmware |
| Meta chunk | 0x01FC | 512B + 6B маркер | Зашифрованная таблица разделов |
| Data chunks | 0x040A | 22 × variable | Зашифрованные данные разделов |
| Footer | 0x90EF | 24B | `CRC32_OF_IMAGE=0x00000000` |

### Header (0x00–0xB5)

| Offset | Размер | Значение | Описание |
|--------|--------|----------|----------|
| 0x00 | 4B | `oviV` | Magic (ViVo firmware) |
| 0x04 | 4B | 0x00008D08 (36104) | Размер payload |
| 0x08 | 4B | 0x0688F566 | Build hash |
| 0x0C | 4B | 0x00000000 | Зарезервировано |
| 0x10 | 4B | 0x000009EF (2543) | Кол-во flash-блоков для записи |
| 0x14 | 4B | 0x003C0003 | Параметры разделов (hi=0x003C=60, lo=0x0003=3) |
| 0x18 | 2B | 0x4E87 (20103) | **VerCode целевой прошивки** |
| 0x1A | 2B | 0x0101 (257) | Версия формата (1.1) |
| 0x1C | 4B | 0x00008000 (32768) | Размер flash-сектора (32KB) |
| 0x20 | 4B | 0x00008D08 | Дубликат payload size |
| 0x24 | 4B | 0x0688F566 | Дубликат build hash |
| 0x28 | 4B | 0x00B60001 | Параметры |
| 0x2C | 4B | 0x00030000 | Кол-во разделов / флаги |
| 0x30–0xB5 | 138B | variable | Таблица смещений / метаданные |
| 0xB6–0x1FB | 326B | zeros | Padding |

### Meta chunk (0x01FC–0x0405)

512 байт зашифрованных данных (энтропия 4.67 — частично структурированные).
Заканчивается стандартным end-маркером: `00 00 [CRC16=0xC202] 5D 00`.
Вероятно — зашифрованная таблица разделов flash-памяти (partition layout manifest).

### Chunk format (повторяющийся, 22 чанка)

```
┌─ Start marker: 00 80 00 FF FF FF FF FF FF   (9 байт)
├─ Sync:         2B 12 47 11 97 94 B2 77      (8 байт)
├─ Data:         [encrypted payload]           (variable)
├─ FF padding:   FF FF FF ...                  (выравнивание flash-сектора)
└─ End marker:   00 00 [CRC16 LE] 5D 00       (6 байт)
```

- Sync-паттерн `2B1247119794B277` повторяется перед каждым чанком (возможно nonce/IV)
- Общий размер зашифрованных данных: **35,503 байт**
- CRC16 в end-маркере не проходит проверку на raw данных → CRC считается **до** шифрования

### Таблица чанков

| Chunk | Offset | Data len | CRC16 |
|-------|--------|----------|-------|
| 0 | 0x0416 | 684 | 0x1E02 |
| 1 | 0x06DC | 520 | 0xEA02 |
| 2 | 0x08FE | 724 | 0x8506 |
| 3 | 0x0BEC | 1647 | 0x710A |
| 4 | 0x1275 | 2651 | 0x7E0E |
| 5 | 0x1CEA | 3688 | 0x0D07 |
| 6 | 0x2B6C | 1783 | 0xF905 |
| 7 | 0x327D | 1507 | 0x4106 |
| 8 | 0x387A | 1579 | 0x2108 |
| 9 | 0x3EBF | 2059 | 0xF009 |
| 10 | 0x46E4 | 2522 | 0x0F06 |
| 11 | 0x50D8 | 1529 | 0xC507 |
| 12 | 0x56EB | 1967 | 0xEC09 |
| 13 | 0x5EB4 | 2518 | 0xB206 |
| 14 | 0x68A4 | 1692 | 0x6009 |
| 15 | 0x6F5A | 2378 | 0xAF06 |
| 16 | 0x78BE | 1689 | 0x3608 |
| 17 | 0x7F71 | 2080 | 0xCA00 |
| 18 | 0x87AB | 180 | 0xD500 |
| 19 | 0x8879 | 191 | 0x6103 |
| 20 | 0x8952 | 843 | 0x4604 |
| 21 | 0x8CB7 | 1072 | нет (до footer) |

### Шифрование

- Энтропия данных: **7.96/8.0** → зашифровано
- Вероятный алгоритм: AES-CBC или XOR с OEM-ключом (типично для BES2500/2710)
- OEM-ключ неизвестен — модификация firmware невозможна без него

### Footer (0x90EF–0x9107)

```
CRC32_OF_IMAGE=0x00000000
```
CRC32 = placeholder (0x00000000), заполняется при установке на устройстве.

## BLE OTA протокол (BES2710)

### Архитектура приложения

| Класс | Назначение |
|-------|------------|
| `p314z5/a.java` (UpgradeHelper) | Читает .bin через ContentResolver.openInputStream(uri), считает MD5, передаёт в B5/e |
| `B5/e.java` (case 0) | Принимает byte[] (firmware) + byte[] (MD5), сохраняет в H5.a |
| `B5/j.java` (UpgradeManager) | Оркестрация: состояния, очередь чанков, расчёт размера чанка |
| `E9/c.java` | Нарезка firmware на чанки, отправка BLE-команд, обработка ответов |
| `H5/a.java` | Хранилище: f2330a=firmware bytes, f2331b=offset, f2332c=chunkSize, f2333d=remaining, f2334e=md5 |
| `K5/a.java` | BLE-команды (UpgradeMessage): code + content |
| `J5/a.java` | Опции подтверждения: CONFIRM(0), ABORT(1), INTERACTIVE_COMMIT(0), SILENT_COMMIT(2) |
| `J5/b.java` | Стадии: TRANSFER_COMPLETE(1), COMMIT(2), BATTERY_LOW(0), IN_PROGRESS(3), WARNING(4) |
| `J5/e.java` | Фазы: START(1), PRE_REBOOT(2), POST_REBOOT(3), COMMIT(4), POST_COMMIT(5) |
| `J5/f.java` | Обработчик ошибок BES2710 bootloader |
| `G9/g.java` | BLE GATT manager (writeCharacteristic) |
| `p031c6/b.java` | Контроллер UI/состояния OTA |
| `C0494g0` | Singleton-провайдер (WorkManager) |

### Приложение НЕ парсит .bin!

Приложение читает **весь файл** как raw `byte[]`, считает MD5, и отправляет байты чанками. Формат .bin парсит **bootloader BES2710** внутри наушника.

### Поток OTA

```
1. Чтение .bin файла → byte[] (полностью в память)
2. Вычисление MD5 файла
3. BLE: отправка SYNC/START (code 1)
4. Наушник отвечает SYNC_CFM (code 20) → версия протокола
   - Приложение поддерживает протокол v4
   - Если версия > 4 → ABORT
5. BLE: отправка DATA_CHUNK (code 4) × N
   - Каждый чанк: [is_last:1B] [data:N B]
   - Размер чанка: min(MTU-4, available_size), минимум 11B
   - Прогресс: (offset / total) * 100%
6. BLE: отправка MD5_VERIFY (code 19) — последние 4B MD5 + 4B длины
7. Наушник: TRANSFER_COMPLETE (code 11)
8. Приложение: CONFIRM (code 7) или ABORT
9. Наушник: COMMIT → REBOOT
10. После ребута: POST_REBOOT → POST_COMMIT
```

### BLE-команды (K5.a)

| Code | Назначение |
|------|------------|
| 1 | SYNC / START — начать OTA |
| 4 | DATA_CHUNK — порция данных прошивки |
| 7 | ABORT — отмена |
| 8 | CANCEL |
| 11 | TRANSFER_COMPLETE — завершение передачи |
| 12 | BATTERY_LOW_CONFIRM |
| 14 | IN_PROGRESS_CONFIRM |
| 15 | COMMIT_CFM |
| 16 | COMMIT_CONFIRM |
| 19 | MD5_VERIFY — отправка хеша для проверки |
| 20 | SYNC_CFM — ответ наушника (версия протокола) |
| 21 | SYNC / RESTART |
| 22 | SYNC_RETRY |
| 31 | ERROR_REPORT — код ошибки от наушника |
| 32 | REBOOT — команда перезагрузки |

### Формат BLE-пакета

```
[opcode:1B] [length:2B LE] [payload:N B]
```

### Условия установки OTA

- Заряд батареи достаточен (проверяется перед стартом)
- Нет активного звонка
- Таймаут: 600 секунд
- Поддержка silent commit: зависит от версии протокола (≥4)

### Ошибки BES2710 bootloader

| Код | Сообщение |
|-----|-----------|
| 16 | internal error |
| 17 | unknown ID |
| 19 | wrong variant |
| 20 | wrong partition number |
| 21 | partition size mismatch |
| 22 | partition type not found |
| 23 | partition open failed |
| 24 | partition write failed |
| 25 | Partition close failed type 1 |
| 26 | SFS validation failed |
| 27 | OEM validation failed |
| 28 | upgrade failed |
| 33 | battery low |
| 34 | invalid sync ID |
| 48 | bad length partition parse |
| 49 | bad length too short |
| 50 | bad length upgrade header |
| 51 | bad length partition header |
| 52 | bad length signature |
| 56-62 | OEM validation failed (various) |
| 72 | partition type not matching |
| 73 | partition type two DFU |
| 80 | partition write failed header |
| 81 | partition write failed data |
| 88 | file too small |
| 89 | file too big |
| 112 | silent commit not supported |
| 128 | application configuration version incompatible |
| 129 | Sync ID is different |
| 130 | sync ID of 0 was sent |
| 166 | dual link reject |

### Хранение на устройстве

| Путь | Назначение |
|------|------------|
| `/data/data/com.vivo.vivotws/files/box/<filename>` | Скачанный firmware .bin |
| SharedPreferences: `update_info.xml`, ключ `update_file_path` | Путь к .bin |
| SharedPreferences: `update_info_box.xml` | Состояние charging case update |
| SharedPreferences: `earbud_attr_sp.xml` | TWS config JSON (все модели) |

## Архитектура OTA обновлений в приложении

### Классы OTA

| Класс | Файл | Назначение |
|-------|------|------------|
| CheckResTask | `H8/c.java` | Проверка и скачивание TWS config JSON с сервера |
| CheckBoxUpdateTask | `V8/e.java` | Проверка/скачивание firmware, MD5 verify, deleteOldBinFile |
| TwsOtaServer | `com/vivo/vipc/TwsOtaServer.java` | BLE IPC сервер OTA |
| SmartOtaImpl | `p009a9/d.java` | Фоновые OTA обновления |
| UpgradePolicyHelper | `com/vivo/service/upgrade/earbud/install/UpgradePolicyHelper.java` | Оркестрация установки |
| InstallControlInfo | `com/vivo/service/upgrade/earbud/install/InstallControlInfo.java` | filePath, upgradeMode, upgradeTarget, targetVersion, newVersionMd5 |
| DefaultPolicy | `com/vivo/service/upgrade/earbud/install/policy/DefaultPolicy.java` | startOta → C0494g0.e().r(context, p314z5.a) |
| Tws2Policy | `com/vivo/service/upgrade/earbud/install/policy/Tws2Policy.java` | TWS 5i (BES2710 = TWS2) |
| UpgradeHelper | `p314z5/a.java` | Читает .bin через ContentResolver, MD5, передаёт в B5.e |
| SharedPreferences helper | `p214qc/a.java` | update_file_path ключ |
| Upgrade subscriber | `p273w5/a.java` | callback подписчик |

### Download manager

- TWS config JSON: `context.getCacheDir()/res/<filename>` через `p073f7.a.c()` (vivo download manager)
- Firmware .bin: `context.getFilesDir()/box/<filename>`
- Сервер: `https://ptsouweb.vivo.com.cn/ptsou/api2.do`

## Патчи APK (применённые, но не сработавшие)

| # | Файл | Метод/место | Патч | Результат |
|---|------|-------------|------|-----------|
| 1 | `res/xml/bluetooth_device_home.xml` | XML | Добавлены preference entries | НЕ сработал (Qa/i перезаписывает) |
| 2 | `J9/c.smali` | switch по audio_effect | `goto :cond_c` → movie_book_master | НЕ сработал (DeepX требует bit 8) |
| 3 | `Qa/i.smali` | метод `n()` | `goto :cond_5` → movie_book_master | НЕ сработал (n() не вызывается при подключённых наушниках) |
| 4 | `Qa/i.smali` | метод `p()` | `goto :cond_d` → movie_book_master | НЕ сработал (причина не выяснена) |

### Сборка и подпись

```
apktool: java -jar apktool.jar b apktool_out -o rebuilt.apk -f
zipalign: zipalign.exe -p -f -v 4 rebuilt.apk aligned.apk
sign: apksigner.bat sign --ks debug.keystore --ks-pass pass:android aligned.apk
install: adb -s cc98b72e install -r signed.apk
```

Keystore: `C:/Users/User/.android/debug.keystore` (alias=androiddebugkey, storepass=android)

## Инструменты и окружение

| Инструмент | Путь / версия |
|------------|---------------|
| ADB | `$LOCALAPPDATA/Android/Sdk/platform-tools/adb.exe` |
| Build tools | `$LOCALAPPDATA/Android/Sdk/build-tools/35.0.0/` |
| Apktool | 2.10.0 (`C:/Users/User/Desktop/vEarphones/apktool.jar`) |
| jadx | декомпиляция в `sources/` |
| Устройство | cc98b72e (ADB), root через `su -c` |
| Python | 3.9 (`D:\Program Files\Python39\`) |

## Файлы проекта

| Файл | Назначение |
|------|------------|
| `vEarphones  5.0.2.2.41.2.apk` | Оригинальный APK |
| `apktool_out/` | Декомпилированный smali/resources |
| `sources/` | Декомпилированные Java-источники (jadx) |
| `firmware_20007_to_20103.bin` | Скачанная прошивка BES2710 |
| `vivo tws5i.md` | Этот файл |

## Выводы

1. **7 пресетов на TWS 5i через патч APK — не работают.** Значение `audio_effect=4` приходит от firmware наушника по BLE. Патч кода приложения меняет только UI, но не меняет capabilities наушника. Пресеты 4 (Movie) и 11 (Master) требуют `audio_effect=28` (как у TWS 5 Pro), что требует другой firmware.

2. **Firmware .bin зашифрован.** Для модификации нужен OEM-ключ BES2710 (неизвестен). Bootloader проверяет OEM validation (ошибки 56-62). Без ключа невозможно изменить `audio_effect` в прошивке.

3. **Сервер OTA требует factory-подпись.** Debug-подписанный APK получает `retcode: 20000, "加密失败"`. Для проверки обновлений нужно использовать оригинальный APK.

4. **Приложение не парсит .bin.** Весь файл отправляется как raw bytes в bootloader BES2710 через BLE. Формат парсится внутри чипа.
