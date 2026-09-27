'use strict';

var TAG = "[FRIDA-VIPC]";

Java.perform(function () {
    console.log(TAG + " Script loaded. Hooking BLE GATT...");

    // ─── 1. Перехват G9/g.e([B)V — отправка данных в TOTA char ───────────────
    try {
        var G9g = Java.use("G9.g");
        G9g.e.implementation = function (data) {
            console.log(TAG + " === G9/g.e() SEND to TOTA ===");
            console.log(TAG + " Data len: " + data.length);
            // Печатаем hex
            var hex = "";
            for (var i = 0; i < Math.min(data.length, 128); i++) {
                var b = data[i] & 0xFF;
                hex += ("0" + b.toString(16)).slice(-2) + " ";
            }
            console.log(TAG + " Hex: " + hex);
            // Печатаем как строку если возможно
            try {
                var str = "";
                for (var i = 4; i < data.length; i++) {
                    var c = data[i] & 0xFF;
                    if (c >= 0x20 && c <= 0x7e) str += String.fromCharCode(c);
                    else str += ".";
                }
                console.log(TAG + " Str: " + str);
            } catch (e) {}
            return this.e(data);
        };
        console.log(TAG + " ✓ G9/g.e hooked");
    } catch (e) {
        console.log(TAG + " ✗ G9/g.e: " + e);
    }

    // ─── 2. Перехват onCharacteristicChanged — данные от наушника ─────────────
    try {
        var G9e = Java.use("G9.e");
        G9e.onCharacteristicChanged.implementation = function (gatt, characteristic) {
            var uuid = characteristic.getUuid().toString();
            var value = characteristic.getValue();
            if (value && value.length > 5) {
                console.log(TAG + " === onCharacteristicChanged UUID=" + uuid + " len=" + value.length + " ===");
                var hex = "";
                for (var i = 0; i < Math.min(value.length, 128); i++) {
                    var b = value[i] & 0xFF;
                    hex += ("0" + b.toString(16)).slice(-2) + " ";
                }
                console.log(TAG + " Hex: " + hex);
                // Проверяем JSON
                try {
                    var str = "";
                    for (var i = 0; i < value.length; i++) {
                        var c = value[i] & 0xFF;
                        if (c >= 0x20 && c <= 0x7e) str += String.fromCharCode(c);
                        else str += ".";
                    }
                    console.log(TAG + " Str: " + str.substring(0, 200));
                } catch (e) {}
            }
            return this.onCharacteristicChanged(gatt, characteristic);
        };
        console.log(TAG + " ✓ G9/e.onCharacteristicChanged hooked");
    } catch (e) {
        console.log(TAG + " ✗ G9/e.onCharacteristicChanged: " + e);
    }

    // ─── 3. Перехват onCharacteristicWrite ──────────────────────────────────
    try {
        var G9e2 = Java.use("G9.e");
        G9e2.onCharacteristicWrite.implementation = function (gatt, characteristic, status) {
            var uuid = characteristic.getUuid().toString();
            console.log(TAG + " onCharacteristicWrite UUID=" + uuid + " status=" + status);
            return this.onCharacteristicWrite(gatt, characteristic, status);
        };
        console.log(TAG + " ✓ G9/e.onCharacteristicWrite hooked");
    } catch (e) {}

    // ─── 4. Перехват setWriteType ────────────────────────────────────────────
    try {
        var BgattChar = Java.use("android.bluetooth.BluetoothGattCharacteristic");
        BgattChar.setWriteType.implementation = function (writeType) {
            console.log(TAG + " setWriteType(" + writeType + ") on UUID=" + this.getUuid().toString());
            return this.setWriteType(writeType);
        };
        console.log(TAG + " ✓ setWriteType hooked");
    } catch (e) {}

    // ─── 5. Перехват AES шифрования ──────────────────────────────────────────
    // Ищем классы шифрования BES TOTA
    var aesClasses = [
        "app.tota_encrypt",
        "tota_encrypt",
        "com.bestechnic.encrypt",
        "org.bouncycastle.crypto.engines.AESEngine",
        "javax.crypto.Cipher"
    ];

    aesClasses.forEach(function (className) {
        try {
            var cls = Java.use(className);
            // Перехватываем все методы
            var methods = cls.class.getDeclaredMethods();
            for (var i = 0; i < methods.length; i++) {
                var m = methods[i];
                var name = m.getName();
                if (name === "init" || name === "doFinal" || name === "encrypt" || name === "decrypt" || name === "update") {
                    try {
                        cls[name].overloads.forEach(function (overload) {
                            overload.implementation = function () {
                                var args = Array.prototype.slice.call(arguments);
                                console.log(TAG + " " + className + "." + name + "(" + args.length + " args)");
                                // Печатаем byte[] аргументы
                                args.forEach(function (arg, idx) {
                                    if (arg && arg.length !== undefined && typeof arg.length === "number") {
                                        var hex = "";
                                        for (var j = 0; j < Math.min(arg.length, 32); j++) {
                                            var b = arg[j] & 0xFF;
                                            hex += ("0" + b.toString(16)).slice(-2);
                                        }
                                        console.log(TAG + "   arg[" + idx + "] (" + arg.length + "B): " + hex);
                                    }
                                });
                                var result = this[name].apply(this, args);
                                if (result && result.length !== undefined && typeof result.length === "number") {
                                    var rh = "";
                                    for (var k = 0; k < Math.min(result.length, 32); k++) {
                                        var rb = result[k] & 0xFF;
                                        rh += ("0" + rb.toString(16)).slice(-2);
                                    }
                                    console.log(TAG + "   result (" + result.length + "B): " + rh);
                                }
                                return result;
                            };
                        });
                    } catch (e) {}
                }
            }
            console.log(TAG + " ✓ " + className + " hooked");
        } catch (e) {
            // Класс не найден — нормально
        }
    });

    // ─── 6. Перехват javax.crypto.Cipher (универсальный AES) ──────────────────
    try {
        var Cipher = Java.use("javax.crypto.Cipher");
        Cipher.init.overload('int', 'java.security.Key').implementation = function (mode, key) {
            var modeStr = (mode === 1) ? "ENCRYPT" : (mode === 2) ? "DECRYPT" : "mode=" + mode;
            console.log(TAG + " Cipher.init " + modeStr + " key=" + key.getAlgorithm());
            // Получаем ключ
            try {
                var keyBytes = key.getEncoded();
                if (keyBytes) {
                    var hex = "";
                    for (var i = 0; i < keyBytes.length; i++) {
                        var b = keyBytes[i] & 0xFF;
                        hex += ("0" + b.toString(16)).slice(-2);
                    }
                    console.log(TAG + " KEY (" + keyBytes.length + "B): " + hex);
                }
            } catch (e) {}
            return this.init(mode, key);
        };
        Cipher.init.overload('int', 'java.security.Key', 'java.security.spec.AlgorithmParameterSpec').implementation = function (mode, key, spec) {
            var modeStr = (mode === 1) ? "ENCRYPT" : (mode === 2) ? "DECRYPT" : "mode=" + mode;
            console.log(TAG + " Cipher.init " + modeStr + " key=" + key.getAlgorithm() + " with IV");
            try {
                var keyBytes = key.getEncoded();
                if (keyBytes) {
                    var hex = "";
                    for (var i = 0; i < keyBytes.length; i++) {
                        var b = keyBytes[i] & 0xFF;
                        hex += ("0" + b.toString(16)).slice(-2);
                    }
                    console.log(TAG + " KEY (" + keyBytes.length + "B): " + hex);
                }
            } catch (e) {}
            // Пытаемся получить IV
            try {
                var IvParameterSpec = Java.use("javax.crypto.spec.IvParameterSpec");
                var ivSpec = Java.cast(spec, IvParameterSpec);
                var ivBytes = ivSpec.getIV();
                var ivHex = "";
                for (var i = 0; i < ivBytes.length; i++) {
                    var b = ivBytes[i] & 0xFF;
                    ivHex += ("0" + b.toString(16)).slice(-2);
                }
                console.log(TAG + " IV (" + ivBytes.length + "B): " + ivHex);
            } catch (e) {}
            return this.init(mode, key, spec);
        };
        Cipher.doFinal.overload('[B').implementation = function (data) {
            var result = this.doFinal(data);
            var hex = "";
            for (var i = 0; i < Math.min(data.length, 32); i++) {
                var b = data[i] & 0xFF;
                hex += ("0" + b.toString(16)).slice(-2);
            }
            console.log(TAG + " Cipher.doFinal input (" + data.length + "B): " + hex);
            if (result) {
                var rh = "";
                for (var i = 0; i < Math.min(result.length, 32); i++) {
                    var rb = result[i] & 0xFF;
                    rh += ("0" + rb.toString(16)).slice(-2);
                }
                console.log(TAG + " Cipher.doFinal output (" + result.length + "B): " + rh);
            }
            return result;
        };
        console.log(TAG + " ✓ javax.crypto.Cipher hooked");
    } catch (e) {
        console.log(TAG + " ✗ Cipher: " + e);
    }

    // ─── 7. Перехват TwsVipcPacket ───────────────────────────────────────────
    try {
        var TwsVipcPacket = Java.use("com.vivo.tws.command.TwsVipcPacket");
        TwsVipcPacket.$init.implementation = function (type, command, device, param) {
            console.log(TAG + " TwsVipcPacket(type=" + type + ", command=" + command + ", device=" + device + ", param=" + param + ")");
            return this.$init(type, command, device, param);
        };
        console.log(TAG + " ✓ TwsVipcPacket hooked");
    } catch (e) {}

    // ─── 8. Перехват ic/c (buildRequest) ─────────────────────────────────────
    try {
        var icC = Java.use("ic.c");
        icC.a.implementation = function (feature, command, device, param) {
            console.log(TAG + " ic.c.a(feature=" + feature + ", command=" + command + ", device=" + device + ", param=" + param + ")");
            return this.a(feature, command, device, param);
        };
        icC.b.implementation = function (feature, command, device, param) {
            console.log(TAG + " ic.c.b(feature=" + feature + ", command=" + command + ", device=" + device + ", param=" + param + ")");
            return this.b(feature, command, device, param);
        };
        console.log(TAG + " ✓ ic.c hooked");
    } catch (e) {}

    // ─── 9. Перехват VipcHelper ──────────────────────────────────────────────
    try {
        var VipcHelper = Java.use("com.android.vivo.tws.fastpair.vipc.vipchelper.VipcHelper");
        VipcHelper.requestAsync.implementation = function (request, callback) {
            console.log(TAG + " VipcHelper.requestAsync");
            try {
                var pkg = request.getPackageName();
                var action = request.getAction();
                console.log(TAG + "   pkg=" + pkg + " action=" + action);
            } catch (e) {}
            return this.requestAsync(request, callback);
        };
        console.log(TAG + " ✓ VipcHelper.requestAsync hooked");
    } catch (e) {}

    // ─── 10. Перехват B5/e (handleGattCharacteristic — обработка ответов) ────
    try {
        var B5e = Java.use("B5.e");
        // B5/e — много методов, перехватываем ключевые
        var methods = B5e.class.getDeclaredMethods();
        for (var i = 0; i < methods.length; i++) {
            var m = methods[i];
            var name = m.getName();
            // Ищем методы обработки данных
            if (name === "run" || name === "a" || name === "b") {
                // Не перехватываем — слишком много методов
            }
        }
        console.log(TAG + " ✓ B5.e found (methods: " + methods.length + ")");
    } catch (e) {}

    console.log(TAG + " All hooks installed. Waiting for BLE activity...");
});
