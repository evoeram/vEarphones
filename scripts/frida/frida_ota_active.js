'use strict';
// Frida скрипт: прямой вызов OTA-команд + перехват Binder IPC
// Цель: заставить APK отправить ota_feature/check, ota_feature/download
// и перехватить BLE GATT write в com.android.bluetooth

var TAG = "[OTA]";

Java.perform(function () {
    console.log(TAG + " === OTA Active Probe ===");

    // ─── 1. Перехват TwsVipcPacket (все типы) ──────────────────────────
    try {
        var TwsVipcPacket = Java.use("com.vivo.tws.command.TwsVipcPacket");
        TwsVipcPacket.$init.overload('int', 'java.lang.String', 'java.lang.String', 'java.lang.String').implementation = function (type, command, device, param) {
            var typeStr = ["", "REQUEST", "RESPONSE", "NOTIFICATION"][type] || "type=" + type;
            console.log(TAG + " TwsVipcPacket(" + typeStr + " cmd=" + command + " dev=" + device + " param=" + (param ? param.substring(0, 80) : "") + ")");
            return this.$init(type, command, device, param);
        };
        console.log(TAG + " ✓ TwsVipcPacket hooked");
    } catch (e) { console.log(TAG + " ✗ TwsVipcPacket: " + e); }

    // ─── 2. Перехват ic.c.a (buildRequest) ─────────────────────────────
    try {
        var icC = Java.use("ic.c");
        icC.a.overload('java.lang.String', 'java.lang.String', 'java.lang.String', 'java.lang.String').implementation = function (feature, command, device, param) {
            console.log(TAG + " >>> buildRequest(" + feature + "/" + command + " dev=" + device + " param=" + (param ? param.substring(0, 80) : "") + ")");
            var result = this.a(feature, command, device, param);
            console.log(TAG + " <<< buildRequest result: " + result);
            return result;
        };
        console.log(TAG + " ✓ ic.c.a hooked");
    } catch (e) { console.log(TAG + " ✗ ic.c.a: " + e); }

    // ─── 3. Перехват VipcHelper.requestAsync ───────────────────────────
    try {
        var VipcHelper = Java.use("com.android.vivo.tws.fastpair.vipc.vipchelper.VipcHelper");
        var methods = VipcHelper.class.getDeclaredMethods();
        for (var i = 0; i < methods.length; i++) {
            var m = methods[i];
            var name = m.getName();
            if (name === "requestAsync" || name === "request" || name === "requestSync") {
                console.log(TAG + " VipcHelper method: " + name + " params=" + m.getParameterTypes().length);
            }
        }
        // Пытаемся перехватить все перегрузки requestAsync
        try {
            VipcHelper.requestAsync.overloads.forEach(function(overload) {
                overload.implementation = function () {
                    var args = Array.prototype.slice.call(arguments);
                    console.log(TAG + " VipcHelper.requestAsync(" + args.length + " args)");
                    args.forEach(function(arg, idx) {
                        if (arg !== null && arg !== undefined) {
                            console.log(TAG + "   arg[" + idx + "]: " + arg.toString().substring(0, 100));
                        }
                    });
                    return this.requestAsync.apply(this, args);
                };
            });
            console.log(TAG + " ✓ VipcHelper.requestAsync hooked");
        } catch (e) { console.log(TAG + " ✗ VipcHelper.requestAsync: " + e); }
    } catch (e) { console.log(TAG + " ✗ VipcHelper: " + e); }

    // ─── 4. Перехват BluetoothGatt.writeCharacteristic ─────────────────
    try {
        var BluetoothGatt = Java.use("android.bluetooth.BluetoothGatt");
        BluetoothGatt.writeCharacteristic.overload('android.bluetooth.BluetoothGattCharacteristic').implementation = function (characteristic) {
            var uuid = characteristic.getUuid().toString();
            var value = characteristic.getValue();
            var writeType = characteristic.getWriteType();
            console.log(TAG + " >>> BLE WRITE uuid=" + uuid + " type=" + writeType + " len=" + (value ? value.length : 0));
            if (value) {
                var hex = "";
                for (var i = 0; i < Math.min(value.length, 100); i++) hex += ("0" + (value[i] & 0xFF).toString(16)).slice(-2) + " ";
                console.log(TAG + "     hex: " + hex);
                var str = "";
                for (var i = 0; i < Math.min(value.length, 100); i++) {
                    var c = value[i] & 0xFF;
                    if (c >= 0x20 && c <= 0x7e) str += String.fromCharCode(c);
                    else str += ".";
                }
                console.log(TAG + "     str: " + str);
            }
            return this.writeCharacteristic(characteristic);
        };
        console.log(TAG + " ✓ BluetoothGatt.writeCharacteristic hooked");
    } catch (e) { console.log(TAG + " ✗ writeCharacteristic: " + e); }

    // ─── 5. BluetoothGattCharacteristic.setValue ───────────────────────
    try {
        var BgattChar = Java.use("android.bluetooth.BluetoothGattCharacteristic");
        BgattChar.setValue.overload('[B').implementation = function (value) {
            var uuid = this.getUuid().toString();
            console.log(TAG + " setValue uuid=" + uuid + " len=" + value.length);
            var hex = "";
            for (var i = 0; i < Math.min(value.length, 100); i++) hex += ("0" + (value[i] & 0xFF).toString(16)).slice(-2) + " ";
            console.log(TAG + "     hex: " + hex);
            return this.setValue(value);
        };
        BgattChar.setWriteType.implementation = function (writeType) {
            console.log(TAG + " setWriteType(" + writeType + ") uuid=" + this.getUuid().toString());
            return this.setWriteType(writeType);
        };
        console.log(TAG + " ✓ setValue + setWriteType hooked");
    } catch (e) {}

    // ─── 6. onCharacteristicChanged (входящие данные) ──────────────────
    try {
        var BluetoothGattCallback = Java.use("android.bluetooth.BluetoothGattCallback");
        BluetoothGattCallback.onCharacteristicChanged.overload('android.bluetooth.BluetoothGatt', 'android.bluetooth.BluetoothGattCharacteristic').implementation = function (gatt, characteristic) {
            var uuid = characteristic.getUuid().toString();
            var value = characteristic.getValue();
            console.log(TAG + " <<< BLE NOTIFY uuid=" + uuid + " len=" + (value ? value.length : 0));
            if (value) {
                var hex = "";
                for (var i = 0; i < Math.min(value.length, 100); i++) hex += ("0" + (value[i] & 0xFF).toString(16)).slice(-2) + " ";
                console.log(TAG + "     hex: " + hex);
                var str = "";
                for (var i = 0; i < Math.min(value.length, 100); i++) {
                    var c = value[i] & 0xFF;
                    if (c >= 0x20 && c <= 0x7e) str += String.fromCharCode(c);
                    else str += ".";
                }
                console.log(TAG + "     str: " + str);
            }
            return this.onCharacteristicChanged(gatt, characteristic);
        };
        console.log(TAG + " ✓ onCharacteristicChanged hooked");
    } catch (e) {}

    // ─── 7. G9.g.e (отправка в TOTA) ───────────────────────────────────
    try {
        var G9g = Java.use("G9.g");
        G9g.e.overload('[B').implementation = function (data) {
            console.log(TAG + " === G9.g.e() SEND to TOTA ===");
            if (data) {
                var hex = "";
                for (var i = 0; i < Math.min(data.length, 100); i++) hex += ("0" + (data[i] & 0xFF).toString(16)).slice(-2) + " ";
                console.log(TAG + " hex(" + data.length + "B): " + hex);
                var str = "";
                for (var i = 0; i < Math.min(data.length, 100); i++) {
                    var c = data[i] & 0xFF;
                    if (c >= 0x20 && c <= 0x7e) str += String.fromCharCode(c);
                    else str += ".";
                }
                console.log(TAG + " str: " + str);
            }
            return this.e(data);
        };
        console.log(TAG + " ✓ G9.g.e hooked");
    } catch (e) { console.log(TAG + " ✗ G9.g.e: " + e); }

    // ─── 8. G9.e (GattCallback в vivo) ─────────────────────────────────
    try {
        var G9e = Java.use("G9.e");
        G9e.onCharacteristicChanged.overload('android.bluetooth.BluetoothGatt', 'android.bluetooth.BluetoothGattCharacteristic').implementation = function (gatt, characteristic) {
            var uuid = characteristic.getUuid().toString();
            var value = characteristic.getValue();
            console.log(TAG + " === G9.e.onCharacteristicChanged uuid=" + uuid + " len=" + (value ? value.length : 0) + " ===");
            if (value) {
                var hex = "";
                for (var i = 0; i < Math.min(value.length, 100); i++) hex += ("0" + (value[i] & 0xFF).toString(16)).slice(-2) + " ";
                console.log(TAG + " hex: " + hex);
            }
            return this.onCharacteristicChanged(gatt, characteristic);
        };
        console.log(TAG + " ✓ G9.e.onCharacteristicChanged hooked");
    } catch (e) { console.log(TAG + " ✗ G9.e: " + e); }

    // ─── 9. Cipher (AES шифрование) ────────────────────────────────────
    try {
        var Cipher = Java.use("javax.crypto.Cipher");
        Cipher.init.overload('int', 'java.security.Key', 'java.security.spec.AlgorithmParameterSpec').implementation = function (mode, key, spec) {
            var modeStr = (mode === 1) ? "ENCRYPT" : (mode === 2) ? "DECRYPT" : "mode=" + mode;
            console.log(TAG + " Cipher.init " + modeStr + " algo=" + key.getAlgorithm());
            try {
                var keyBytes = key.getEncoded();
                if (keyBytes) {
                    var hex = "";
                    for (var i = 0; i < keyBytes.length; i++) hex += ("0" + (keyBytes[i] & 0xFF).toString(16)).slice(-2);
                    console.log(TAG + " *** AES KEY (" + keyBytes.length + "B): " + hex);
                }
            } catch (e) {}
            try {
                var IvSpec = Java.use("javax.crypto.spec.IvParameterSpec");
                var ivSpec = Java.cast(spec, IvSpec);
                var ivBytes = ivSpec.getIV();
                var ivHex = "";
                for (var i = 0; i < ivBytes.length; i++) ivHex += ("0" + (ivBytes[i] & 0xFF).toString(16)).slice(-2);
                console.log(TAG + " *** AES IV (" + ivBytes.length + "B): " + ivHex);
            } catch (e) {}
            return this.init(mode, key, spec);
        };
        Cipher.init.overload('int', 'java.security.Key').implementation = function (mode, key) {
            var modeStr = (mode === 1) ? "ENCRYPT" : (mode === 2) ? "DECRYPT" : "mode=" + mode;
            console.log(TAG + " Cipher.init " + modeStr + " (no IV) algo=" + key.getAlgorithm());
            try {
                var keyBytes = key.getEncoded();
                if (keyBytes) {
                    var hex = "";
                    for (var i = 0; i < keyBytes.length; i++) hex += ("0" + (keyBytes[i] & 0xFF).toString(16)).slice(-2);
                    console.log(TAG + " *** AES KEY (" + keyBytes.length + "B): " + hex);
                }
            } catch (e) {}
            return this.init(mode, key);
        };
        Cipher.doFinal.overload('[B').implementation = function (data) {
            var result = this.doFinal(data);
            var inHex = "";
            for (var i = 0; i < Math.min(data.length, 64); i++) inHex += ("0" + (data[i] & 0xFF).toString(16)).slice(-2);
            var outHex = "";
            if (result) for (var i = 0; i < Math.min(result.length, 64); i++) outHex += ("0" + (result[i] & 0xFF).toString(16)).slice(-2);
            console.log(TAG + " Cipher.doFinal in(" + data.length + "B): " + inHex);
            console.log(TAG + " Cipher.doFinal out(" + (result ? result.length : 0) + "B): " + outHex);
            return result;
        };
        console.log(TAG + " ✓ Cipher hooked");
    } catch (e) { console.log(TAG + " ✗ Cipher: " + e); }

    // ─── 10. АКТИВНЫЙ ВЫЗОВ OTA-команд ─────────────────────────────────
    console.log(TAG + " === Scheduling OTA command invocations ===");

    // Через 3 секунды вызываем OTA check
    setTimeout(function () {
        Java.perform(function () {
            console.log(TAG + " === INVOKING ota_feature/check ===");
            try {
                var icC = Java.use("ic.c");
                // buildRequest(feature, command, device, param)
                var result = icC.a("ota_feature", "check", "", "");
                console.log(TAG + " ota_feature/check result: " + result);
            } catch (e) {
                console.log(TAG + " ota_feature/check error: " + e);
            }

            // Также пробуем get_state
            try {
                console.log(TAG + " === INVOKING ota_feature/get_state ===");
                var result2 = icC.a("ota_feature", "get_state", "", "");
                console.log(TAG + " ota_feature/get_state result: " + result2);
            } catch (e) {
                console.log(TAG + " ota_feature/get_state error: " + e);
            }

            // information_feature/get_earbud_information
            try {
                console.log(TAG + " === INVOKING information_feature/get_earbud_information ===");
                var result3 = icC.a("information_feature", "get_earbud_information", "", "");
                console.log(TAG + " get_earbud_information result: " + result3);
            } catch (e) {
                console.log(TAG + " get_earbud_information error: " + e);
            }
        });
    }, 3000);

    // Через 8 секунд вызываем OTA download
    setTimeout(function () {
        Java.perform(function () {
            console.log(TAG + " === INVOKING ota_feature/download ===");
            try {
                var icC = Java.use("ic.c");
                var result = icC.a("ota_feature", "download", "", "");
                console.log(TAG + " ota_feature/download result: " + result);
            } catch (e) {
                console.log(TAG + " ota_feature/download error: " + e);
            }
        });
    }, 8000);

    console.log(TAG + " All hooks installed. OTA commands scheduled (3s and 8s).");
});
