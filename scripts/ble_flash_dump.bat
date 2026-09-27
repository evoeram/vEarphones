@echo off
REM ============================================================
REM  BLE Flash Dump - vivo TWS 5i (BES2710)
REM  Запуск на ПК с Bluetooth
REM ============================================================
setlocal enabledelayedexpansion

echo.
echo  === BLE Flash Dump - vivo TWS 5i ===
echo.

REM Проверка Python
where python >nul 2>&1
if errorlevel 1 (
    echo  [!] Python не найден. Установите Python 3.8+ с python.org
    pause
    exit /b 1
)

REM Установка зависимостей
echo  [*] Проверка зависимостей...
python -c "import bleak" 2>nul
if errorlevel 1 (
    echo  [*] Устанавливаю bleak...
    pip install bleak
)
python -c "from Crypto.Cipher import AES" 2>nul
if errorlevel 1 (
    echo  [*] Устанавливаю pycryptodome...
    pip install pycryptodome
)

echo.
echo  [*] Зависимости установлены.
echo.

REM Меню
echo  Выберите режим:
echo   1. Сканировать BLE устройства
echo   2. General info (тест подключения)
echo   3. Полный дамп flash (4 MB)
echo   4. Дамп с указанием адреса/размера
echo   5. Probe (тест протокола - все форматы пакетов)
echo.

set /p choice="Режим [1-5]: "

REM MAC по умолчанию - левый наушник
set MAC=AC:40:1E:C0:BC:85
set /p mac="MAC адрес [%MAC%]: "
if not "%mac%"=="" set MAC=%mac%

if "%choice%"=="1" (
    python "%~dp0ble_flash_dump.py" --scan
) else if "%choice%"=="2" (
    python "%~dp0ble_flash_dump.py" --mac %MAC% --info -v
) else if "%choice%"=="3" (
    set OUT=flash_dump.bin
    echo  [*] Выходной файл: !OUT!
    python "%~dp0ble_flash_dump.py" --mac %MAC% --output "!OUT!" -v
) else if "%choice%"=="4" (
    set /p start="Начальный адрес hex [0x000000]: "
    set /p size="Размер hex [0x400000]: "
    set /p out="Выходной файл [flash_dump.bin]: "
    if "!start!"=="" set start=0x000000
    if "!size!"=="" set size=0x400000
    if "!out!"=="" set out=flash_dump.bin
    python "%~dp0ble_flash_dump.py" --mac %MAC% --output "!out!" --start !start! --size !size! -v
) else if "%choice%"=="5" (
    python "%~dp0ble_flash_dump.py" --mac %MAC% --probe -v
) else (
    echo  [!] Неверный выбор
)

echo.
pause
