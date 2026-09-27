
'use strict';
var TAG = "[UI]";

Java.perform(function () {
    console.log(TAG + " Hooks installing in :ui process...");

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
                for (var i = 0; i < Math.min(value.length, 80); i++) hex += ("0" + (value[i] & 0xFF).toString(16)).slice(-2) + " ";
                console.log(TAG + "     hex: " + hex);
            }
            return this.writeCharacteristic(characteristic);
        };
        console.log(TAG + " ✓ writeCharacteristic hooked");
    } catch (e) { console.log(TAG + " ✗ writeCharacteristic: " + e); }

    // ─── 2. onCharacteristicChanged ──────────────────────────────────────
    try {
        var BluetoothGattCallback = Java.use("android.bluetooth.BluetoothGattCallback");
        BluetoothGattCallback.onCharacteristicChanged.overload('android.bluetooth.BluetoothGatt', 'android.bluetooth.BluetoothGattCharacteristic').implementation = function (gatt, characteristic) {
            var uuid = characteristic.getUuid().toString();
            var value = characteristic.getValue();
            console.log(TAG + " <<< NOTIFY uuid=" + uuid + " len=" + (value ? value.length : 0));
            if (value) {
                var hex = "";
                for (var i = 0; i < Math.min(value.length, 80); i++) hex += ("0" + (value[i] & 0xFF).toString(16)).slice(-2) + " ";
                console.log(TAG + "     hex: " + hex);
            }
            return this.onCharacteristicChanged(gatt, characteristic);
        };
        console.log(TAG + " ✓ onCharacteristicChanged hooked");
    } catch (e) { console.log(TAG + " ✗ onCharacteristicChanged: " + e); }

    // ─── 3. onCharacteristicWrite ──────────────────────────────────────
    try {
        var BluetoothGattCallback2 = Java.use("android.bluetooth.BluetoothGattCallback");
        BluetoothGattCallback2.onCharacteristicWrite.implementation = function (gatt, characteristic, status) {
            var uuid = characteristic.getUuid().toString();
            console.log(TAG + " onCharacteristicWrite uuid=" + uuid + " status=" + status);
            return this.onCharacteristicWrite(gatt, characteristic, status);
        };
        console.log(TAG + " ✓ onCharacteristicWrite hooked");
    } catch (e) {}

    // ─── 4. BluetoothGattCharacteristic.setValue ──────────────────────
    try {
        var BgattChar = Java.use("android.bluetooth.BluetoothGattCharacteristic");
        BgattChar.setValue.overload('[B').implementation = function (value) {
            var uuid = this.getUuid().toString();
            console.log(TAG + " setValue uuid=" + uuid + " len=" + value.length);
            var hex = "";
            for (var i = 0; i < Math.min(value.length, 80); i++) hex += ("0" + (value[i] & 0xFF).toString(16)).slice(-2) + " ";
            console.log(TAG + "     hex: " + hex);
            return this.setValue(value);
        };
        console.log(TAG + " ✓ setValue hooked");
    } catch (e) {}

    // ─── 5. setWriteType ────────────────────────────────────────────────
    try {
        var BgattChar2 = Java.use("android.bluetooth.BluetoothGattCharacteristic");
        BgattChar2.setWriteType.implementation = function (writeType) {
            console.log(TAG + " setWriteType(" + writeType + ") uuid=" + this.getUuid().toString());
            return this.setWriteType(writeType);
        };
        console.log(TAG + " ✓ setWriteType hooked");
    } catch (e) {}

    // ─── 6. G9.g.e (send to TOTA) ───────────────────────────────────────
    try {
        var G9g = Java.use("G9.g");
        G9g.e.overload('[B').implementation = function (data) {
            console.log(TAG + " === G9.g.e() SEND ===");
            if (data) {
                var hex = "";
                for (var i = 0; i < Math.min(data.length, 80); i++) hex += ("0" + (data[i] & 0xFF).toString(16)).slice(-2) + " ";
                console.log(TAG + " hex(" + data.length + "B): " + hex);
            }
            return this.e(data);
        };
        console.log(TAG + " ✓ G9.g.e hooked");
    } catch (e) { console.log(TAG + " ✗ G9.g.e: " + e); }

    // ─── 7. G9.e (GattCallback) ─────────────────────────────────────────
    try {
        var G9e = Java.use("G9.e");
        G9e.onCharacteristicChanged.overload('android.bluetooth.BluetoothGatt', 'android.bluetooth.BluetoothGattCharacteristic').implementation = function (gatt, characteristic) {
            var uuid = characteristic.getUuid().toString();
            var value = characteristic.getValue();
            console.log(TAG + " === G9.e.onCharacteristicChanged uuid=" + uuid + " ===");
            if (value) {
                var hex = "";
                for (var i = 0; i < Math.min(value.length, 80); i++) hex += ("0" + (value[i] & 0xFF).toString(16)).slice(-2) + " ";
                console.log(TAG + " hex(" + value.length + "B): " + hex);
            }
            return this.onCharacteristicChanged(gatt, characteristic);
        };
        console.log(TAG + " ✓ G9.e.onCharacteristicChanged hooked");
    } catch (e) { console.log(TAG + " ✗ G9.e: " + e); }

    // ─── 8. writeDescriptor (CCCD) ──────────────────────────────────────
    try {
        var BluetoothGatt3 = Java.use("android.bluetooth.BluetoothGatt");
        BluetoothGatt3.writeDescriptor.implementation = function (descriptor) {
            var uuid = descriptor.getUuid().toString();
            var value = descriptor.getValue();
            console.log(TAG + " writeDescriptor uuid=" + uuid + " val=" + (value ? value[0] : -1));
            return this.writeDescriptor(descriptor);
        };
        console.log(TAG + " ✓ writeDescriptor hooked");
    } catch (e) {}

    // ─── 9. Cipher ──────────────────────────────────────────────────────
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
    } catch (e) { console.log(TAG + " ✗ Cipher: " + e); }

    // ─── 10. TwsVipcPacket ──────────────────────────────────────────────
    try {
        var TwsVipcPacket = Java.use("com.vivo.tws.command.TwsVipcPacket");
        TwsVipcPacket.$init.overload('int', 'java.lang.String', 'java.lang.String', 'java.lang.String').implementation = function (type, command, device, param) {
            if (type === 1) console.log(TAG + " TwsVipcPacket(REQUEST type=" + type + " cmd=" + command + " dev=" + device + " param=" + (param ? param.substring(0, 50) : "") + ")");
            return this.$init(type, command, device, param);
        };
        console.log(TAG + " ✓ TwsVipcPacket hooked");
    } catch (e) {}

    console.log(TAG + " All hooks installed!");
});
