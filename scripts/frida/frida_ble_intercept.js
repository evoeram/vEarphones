
'use strict';

var TAG = "[VIPC]";

Java.perform(function () {
    console.log(TAG + " Hooks installing...");

    // ─── 1. BluetoothGatt.writeCharacteristic ──────────────────────────
    try {
        var BluetoothGatt = Java.use("android.bluetooth.BluetoothGatt");
        BluetoothGatt.writeCharacteristic.overload('android.bluetooth.BluetoothGattCharacteristic').implementation = function (characteristic) {
            var uuid = characteristic.getUuid().toString();
            var value = characteristic.getValue();
            var writeType = characteristic.getWriteType();
            console.log(TAG + " >>> WRITE uuid=" + uuid + " type=" + writeType + " len=" + (value ? value.length : 0));
            if (value) {
                var hex = "";
                for (var i = 0; i < Math.min(value.length, 64); i++) {
                    hex += ("0" + (value[i] & 0xFF).toString(16)).slice(-2) + " ";
                }
                console.log(TAG + "     hex: " + hex);
                // Also try as string
                var str = "";
                for (var i = 0; i < Math.min(value.length, 64); i++) {
                    var c = value[i] & 0xFF;
                    if (c >= 0x20 && c <= 0x7e) str += String.fromCharCode(c);
                    else str += ".";
                }
                console.log(TAG + "     str: " + str);
            }
            return this.writeCharacteristic(characteristic);
        };
        console.log(TAG + " ✓ BluetoothGatt.writeCharacteristic hooked");
    } catch (e) {
        console.log(TAG + " ✗ writeCharacteristic: " + e);
    }

    // ─── 2. BluetoothGattCallback.onCharacteristicChanged ──────────────
    try {
        var BluetoothGattCallback = Java.use("android.bluetooth.BluetoothGattCallback");
        BluetoothGattCallback.onCharacteristicChanged.overload('android.bluetooth.BluetoothGatt', 'android.bluetooth.BluetoothGattCharacteristic').implementation = function (gatt, characteristic) {
            var uuid = characteristic.getUuid().toString();
            var value = characteristic.getValue();
            console.log(TAG + " <<< NOTIFY uuid=" + uuid + " len=" + (value ? value.length : 0));
            if (value) {
                var hex = "";
                for (var i = 0; i < Math.min(value.length, 64); i++) {
                    hex += ("0" + (value[i] & 0xFF).toString(16)).slice(-2) + " ";
                }
                console.log(TAG + "     hex: " + hex);
                var str = "";
                for (var i = 0; i < Math.min(value.length, 64); i++) {
                    var c = value[i] & 0xFF;
                    if (c >= 0x20 && c <= 0x7e) str += String.fromCharCode(c);
                    else str += ".";
                }
                console.log(TAG + "     str: " + str);
            }
            return this.onCharacteristicChanged(gatt, characteristic);
        };
        console.log(TAG + " ✓ onCharacteristicChanged hooked");
    } catch (e) {
        console.log(TAG + " ✗ onCharacteristicChanged: " + e);
    }

    // ─── 3. setWriteType ────────────────────────────────────────────────
    try {
        var BgattChar = Java.use("android.bluetooth.BluetoothGattCharacteristic");
        BgattChar.setWriteType.implementation = function (writeType) {
            console.log(TAG + " setWriteType(" + writeType + ") uuid=" + this.getUuid().toString());
            return this.setWriteType(writeType);
        };
        console.log(TAG + " ✓ setWriteType hooked");
    } catch (e) {}

    // ─── 4. javax.crypto.Cipher ────────────────────────────────────────
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
                    console.log(TAG + " KEY (" + keyBytes.length + "B): " + hex);
                }
            } catch (e) {}
            try {
                var IvSpec = Java.use("javax.crypto.spec.IvParameterSpec");
                var ivSpec = Java.cast(spec, IvSpec);
                var ivBytes = ivSpec.getIV();
                var ivHex = "";
                for (var i = 0; i < ivBytes.length; i++) ivHex += ("0" + (ivBytes[i] & 0xFF).toString(16)).slice(-2);
                console.log(TAG + " IV (" + ivBytes.length + "B): " + ivHex);
            } catch (e) {}
            return this.init(mode, key, spec);
        };
        
        Cipher.init.overload('int', 'java.security.Key').implementation = function (mode, key) {
            var modeStr = (mode === 1) ? "ENCRYPT" : (mode === 2) ? "DECRYPT" : "mode=" + mode;
            console.log(TAG + " Cipher.init " + modeStr + " algo=" + key.getAlgorithm());
            try {
                var keyBytes = key.getEncoded();
                if (keyBytes) {
                    var hex = "";
                    for (var i = 0; i < keyBytes.length; i++) hex += ("0" + (keyBytes[i] & 0xFF).toString(16)).slice(-2);
                    console.log(TAG + " KEY (" + keyBytes.length + "B): " + hex);
                }
            } catch (e) {}
            return this.init(mode, key);
        };
        
        Cipher.doFinal.overload('[B').implementation = function (data) {
            var result = this.doFinal(data);
            var inHex = "";
            for (var i = 0; i < Math.min(data.length, 48); i++) inHex += ("0" + (data[i] & 0xFF).toString(16)).slice(-2);
            var outHex = "";
            if (result) for (var i = 0; i < Math.min(result.length, 48); i++) outHex += ("0" + (result[i] & 0xFF).toString(16)).slice(-2);
            console.log(TAG + " Cipher.doFinal in(" + data.length + "B): " + inHex);
            console.log(TAG + " Cipher.doFinal out(" + (result ? result.length : 0) + "B): " + outHex);
            return result;
        };
        
        console.log(TAG + " ✓ Cipher hooked");
    } catch (e) {
        console.log(TAG + " ✗ Cipher: " + e);
    }

    // ─── 5. TwsVipcPacket ──────────────────────────────────────────────
    try {
        var TwsVipcPacket = Java.use("com.vivo.tws.command.TwsVipcPacket");
        TwsVipcPacket.$init.overload('int', 'java.lang.String', 'java.lang.String', 'java.lang.String').implementation = function (type, command, device, param) {
            console.log(TAG + " TwsVipcPacket(type=" + type + " cmd=" + command + " dev=" + device + " param=" + param + ")");
            return this.$init(type, command, device, param);
        };
        console.log(TAG + " ✓ TwsVipcPacket hooked");
    } catch (e) {}

    // ─── 6. Hook G9.g.e([B)V — send to TOTA ─────────────────────────────
    try {
        var G9g = Java.use("G9.g");
        G9g.e.overload('[B').implementation = function (data) {
            console.log(TAG + " === G9.g.e() SEND ===");
            if (data) {
                var hex = "";
                for (var i = 0; i < Math.min(data.length, 64); i++) hex += ("0" + (data[i] & 0xFF).toString(16)).slice(-2) + " ";
                console.log(TAG + " hex(" + data.length + "B): " + hex);
                var str = "";
                for (var i = 0; i < Math.min(data.length, 64); i++) {
                    var c = data[i] & 0xFF;
                    if (c >= 0x20 && c <= 0x7e) str += String.fromCharCode(c);
                    else str += ".";
                }
                console.log(TAG + " str: " + str);
            }
            return this.e(data);
        };
        console.log(TAG + " ✓ G9.g.e hooked");
    } catch (e) {
        console.log(TAG + " ✗ G9.g.e: " + e);
    }

    // ─── 7. Hook G9.e (BluetoothGattCallback) ───────────────────────────
    try {
        var G9e = Java.use("G9.e");
        G9e.onCharacteristicChanged.overload('android.bluetooth.BluetoothGatt', 'android.bluetooth.BluetoothGattCharacteristic').implementation = function (gatt, characteristic) {
            var uuid = characteristic.getUuid().toString();
            var value = characteristic.getValue();
            console.log(TAG + " === G9.e.onCharacteristicChanged uuid=" + uuid + " ===");
            if (value) {
                var hex = "";
                for (var i = 0; i < Math.min(value.length, 64); i++) hex += ("0" + (value[i] & 0xFF).toString(16)).slice(-2) + " ";
                console.log(TAG + " hex(" + value.length + "B): " + hex);
            }
            return this.onCharacteristicChanged(gatt, characteristic);
        };
        console.log(TAG + " ✓ G9.e.onCharacteristicChanged hooked");
    } catch (e) {
        console.log(TAG + " ✗ G9.e: " + e);
    }

    // ─── 8. ic.c buildRequest ───────────────────────────────────────────
    try {
        var icC = Java.use("ic.c");
        icC.a.overload('java.lang.String', 'java.lang.String', 'java.lang.String', 'java.lang.String').implementation = function (feature, command, device, param) {
            console.log(TAG + " buildRequest(" + feature + "/" + command + " dev=" + device + " param=" + param + ")");
            return this.a(feature, command, device, param);
        };
        console.log(TAG + " ✓ ic.c.a hooked");
    } catch (e) {}

    console.log(TAG + " All hooks installed. Waiting for BLE activity...");
});
