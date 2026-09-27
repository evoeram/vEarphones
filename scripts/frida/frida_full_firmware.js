'use strict';

var TAG = "[FRIDA-FULL-FW]";
var hookedClasses = {};

Java.perform(function () {
    console.log(TAG + " Script loaded. Polling for classes every 2s...");

    var pollCount = 0;
    var pollInterval = setInterval(function () {
        Java.perform(function () {
            pollCount++;
            if (pollCount > 300) { clearInterval(pollInterval); return; }

            // --- com.vivo.vipc.databus.request.a: перехват сборки параметров ---
            //   a.h(sb, str, "&onlyFull=2&needH5Content=1") → меняем onlyFull=2 на onlyFull=1
            //   onlyFull=1 = полный образ, onlyFull=2 = differential patch
            if (!hookedClasses["databus.a"]) {
                try {
                    var DA = Java.use("com.vivo.vipc.databus.request.a");
                    DA.h.implementation = function (sb, str1, str2) {
                        var orig = str2;
                        if (str2 !== null && str2.indexOf("onlyFull=") !== -1) {
                            // Пробуем onlyFull=0 — может сервер отдаст полный образ
                            str2 = str2.replace(/onlyFull=\d/, "onlyFull=0");
                            console.log(TAG + " [databus.a.h] PATCHED onlyFull→0: " + str2);
                        }
                        var result = this.h(sb, str1, str2);
                        if (result !== null && result.indexOf("vercode=") !== -1) {
                            console.log(TAG + " [databus.a.h] post_data=" + result);
                        }
                        return result;
                    };
                    hookedClasses["databus.a"] = true;
                    console.log(TAG + " ✓ databus.a.h hooked (onlyFull patch)");
                } catch (e) {}
            }

            // --- X8.a: НЕ подменяем версию, только логируем ---
            if (!hookedClasses["X8.a"]) {
                try {
                    var X8a = Java.use("X8.a");

                    // e(String) — парсит JSON ответ сервера
                    X8a.e.implementation = function (str) {
                        console.log(TAG + " === X8.a.e() RAW JSON ===");
                        console.log(str);
                        var result = this.e(str);
                        if (result !== null) {
                            try {
                                var d = result.getData();
                                if (d !== null && d.getZip() !== null) {
                                    console.log(TAG + " URL=" + result.getRedirect() + d.getZip().getUrl());
                                    console.log(TAG + " len=" + d.getZip().getLen() + " md5=" + d.getZip().getMd5());
                                    console.log(TAG + " vercode=" + d.getVercode() + " version=" + d.getVersion() + " way=" + d.getWay());
                                }
                            } catch (e2) {}
                        }
                        return result;
                    };

                    // doInBackground — подменяем версию на 0 (onlyFull=0 уже патчится в databus.a.h)
                    X8a.doInBackground.implementation = function (args) {
                        console.log(TAG + " === X8.a.doInBackground START ===");
                        try {
                            var fields = X8a.class.getDeclaredFields();
                            var SimpleEarInfoCls = Java.use("com.vivo.tws.bean.SimpleEarInfo");
                            for (var i = 0; i < fields.length; i++) {
                                var f = fields[i];
                                f.setAccessible(true);
                                var fName = f.getName();
                                var fType = f.getType().getName();
                                if (fType === "com.vivo.tws.bean.SimpleEarInfo") {
                                    var si = f.get(this);
                                    if (si !== null) {
                                        si = Java.cast(si, SimpleEarInfoCls);
                                        console.log(TAG + "   field " + fName + ": project=" + si.getProject()
                                            + " leftVer=" + si.getLeftVersion() + " rightVer=" + si.getRightVersion());
                                        si.setLeftVersion(0);
                                        si.setRightVersion(0);
                                        console.log(TAG + "   PATCHED → leftVer=0 rightVer=0");
                                    }
                                }
                            }
                        } catch (e2) {
                            console.log(TAG + "   patch error: " + e2);
                        }
                        var result = this.doInBackground(args);
                        console.log(TAG + " === X8.a.doInBackground END ===");
                        return result;
                    };
                    hookedClasses["X8.a"] = true;
                    console.log(TAG + " ✓ X8.a hooked (logging only, no version patch)");
                } catch (e) {}
            }

            // --- p237sb.g: CheckUpdateRunnable-sps ---
            if (!hookedClasses["p237sb.g"]) {
                try {
                    var G = Java.use("p237sb.g");
                    G.run.implementation = function () {
                        console.log(TAG + " === CheckUpdateRunnable-sps.run() ===");
                        try {
                            var f = this.f28993c.value;
                            var bundle = f.f28990a.value;
                            var uri = bundle.getString("uri");
                            var postData = bundle.getString("post_data");
                            console.log(TAG + "   uri=" + uri);
                            console.log(TAG + "   post_data=" + postData);
                            if (postData !== null && postData.indexOf("onlyFull=2") !== -1) {
                                var patched = postData.replace("onlyFull=2", "onlyFull=1");
                                console.log(TAG + "   PATCHED onlyFull=2→1");
                                bundle.putString("post_data", patched);
                            }
                        } catch (e2) {
                            console.log(TAG + "   error: " + e2);
                        }
                        return this.run();
                    };
                    hookedClasses["p237sb.g"] = true;
                    console.log(TAG + " ✓ p237sb.g (CheckUpdateRunnable-sps) hooked");
                } catch (e) {}
            }

            // --- p237sb.c: AutoCheckComponent handler ---
            if (!hookedClasses["p237sb.c"]) {
                try {
                    var C = Java.use("p237sb.c");
                    C.onChanged.implementation = function (obj) {
                        console.log(TAG + " === AutoCheckComponent.onChanged() ===");
                        try {
                            var bundle = obj.f28990a.value;
                            var code = bundle.getInt("code", -1);
                            var tag = bundle.getString("tag");
                            var resp = bundle.getString("CALL_JS_RESPONSE");
                            console.log(TAG + "   code=" + code + " tag=" + tag);
                            if (resp !== null) console.log(TAG + "   RESPONSE: " + resp);
                        } catch (e2) {}
                        return this.onChanged(obj);
                    };
                    hookedClasses["p237sb.c"] = true;
                    console.log(TAG + " ✓ p237sb.c (AutoCheckComponent) hooked");
                } catch (e) {}
            }

            // --- Y8.a: DownloadTask ---
            if (!hookedClasses["Y8.a"]) {
                try {
                    var Y8a = Java.use("Y8.a");
                    Y8a.doInBackground.implementation = function (args) {
                        console.log(TAG + " === DownloadTask ===");
                        try {
                            var ui = this.f7497d.value;
                            if (ui !== null && ui.getData() !== null) {
                                var zip = ui.getData().getZip();
                                if (zip !== null) {
                                    console.log(TAG + "   URL=" + ui.getRedirect() + zip.getUrl());
                                    console.log(TAG + "   len=" + zip.getLen() + " md5=" + zip.getMd5());
                                }
                            }
                            console.log(TAG + "   file=" + this.f7500g.value);
                        } catch (e2) {}
                        return this.doInBackground(args);
                    };
                    hookedClasses["Y8.a"] = true;
                    console.log(TAG + " ✓ Y8.a (DownloadTask) hooked");
                } catch (e) {}
            }

            // --- okhttp3 RealCall ---
            if (!hookedClasses["RealCall"]) {
                try {
                    var RC = Java.use("okhttp3.internal.connection.RealCall");
                    RC.execute.implementation = function () {
                        var url = this.request().url().toString();
                        if (url.indexOf("ptsou") !== -1 || url.indexOf("api2") !== -1 || url.indexOf(".bin") !== -1) {
                            console.log(TAG + " >>> HTTP " + url);
                        }
                        var resp = this.execute();
                        if (url.indexOf("ptsou") !== -1 || url.indexOf("api2") !== -1 || url.indexOf(".bin") !== -1) {
                            try {
                                var b = resp.body();
                                console.log(TAG + " <<< HTTP " + resp.code() + " len=" + (b ? b.contentLength() : -1));
                            } catch (e2) {}
                        }
                        return resp;
                    };
                    hookedClasses["RealCall"] = true;
                    console.log(TAG + " ✓ RealCall hooked");
                } catch (e) {}
            }
        });
    }, 2000);

    console.log(TAG + " Polling started. Open the app and check for updates.");
    console.log(TAG + " Hooks will auto-install when classes load.");
});
