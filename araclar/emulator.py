"""Emülatör işlemleri: adb'yi bul, bağlan, APK kur, OBB kopyala, port yönlendir.

Kullanım:
  python emulator.py kur      -> OBB'yi yamalar, APK'yı kurar, yamalı OBB'yi kopyalar (bir kez)
  python emulator.py baglan   -> emülatörün 127.0.0.1:8881'ini bilgisayardaki sunucuya yönlendirir
  python emulator.py teshis   -> oyunu yeniden başlatıp 45 sn'lik emülatör kaydını teshis.txt'ye yazar
"""
import glob
import os
import shutil
import subprocess
import sys
import tempfile

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAKET = "com.seastar.gpplay.streetball"
PORT = 8881
YAMA_KLASORU = "/sdcard/Android/data/%s/files!/assets/" % PAKET
ADB_ADAYLARI = [
    r"C:\LDPlayer\LDPlayer9\adb.exe",
    r"C:\LDPlayer\LDPlayer4.0\adb.exe",
    r"C:\LDPlayer\LDPlayer64\adb.exe",
    r"C:\Program Files\BlueStacks_nxt\HD-Adb.exe",
    r"C:\Program Files\BlueStacks\HD-Adb.exe",
    r"C:\Program Files\Netease\MuMuPlayer-12.0\shell\adb.exe",
    r"C:\Program Files\Netease\MuMu Player 12\shell\adb.exe",
    r"C:\Program Files\Nox\bin\nox_adb.exe",
    r"C:\Program Files (x86)\Nox\bin\nox_adb.exe",
    r"C:\platform-tools\adb.exe",
]
ADB_PORTLARI = [5555, 5556, 5557, 5565, 7555, 16384, 62001]


def hata(mesaj):
    print("\n[HATA] " + mesaj)
    sys.exit(1)


def adb_bul():
    adb = shutil.which("adb")
    if adb:
        return adb
    for aday in ADB_ADAYLARI:
        if os.path.exists(aday):
            return aday
    for desen in (r"C:\LDPlayer\*\adb.exe", r"D:\LDPlayer\*\adb.exe", os.path.join(KOK, "platform-tools", "adb.exe")):
        bulunan = glob.glob(desen)
        if bulunan:
            return bulunan[0]
    hata("adb bulunamadi. Emulatorun (LDPlayer onerilir) kurulu oldugundan emin ol, ya da\n"
         "Google'in platform-tools paketini indirip 'platform-tools' klasorunu bu klasore koy.")


def adb(adb_yolu, *arg, kontrol=True):
    sonuc = subprocess.run([adb_yolu, *arg], capture_output=True, text=True, encoding="utf-8", errors="replace")
    cikti = ((sonuc.stdout or "") + (sonuc.stderr or "")).strip()
    if kontrol and sonuc.returncode != 0:
        hata("adb %s basarisiz:\n%s" % (" ".join(arg), cikti))
    return cikti


def cihaz_sec(adb_yolu):
    def cihazlar():
        satirlar = adb(adb_yolu, "devices").splitlines()[1:]
        return [s.split()[0] for s in satirlar if s.strip().endswith("device")]
    bulunan = cihazlar()
    if not bulunan:
        for port in ADB_PORTLARI:
            adb(adb_yolu, "connect", "127.0.0.1:%d" % port, kontrol=False)
        bulunan = cihazlar()
    if not bulunan:
        hata("Acik bir emulator bulunamadi. Emulatoru ac, ana ekran gelince tekrar dene.\n"
             "LDPlayer'da Ayarlar > Diger > ADB hata ayiklama = 'Yerel baglantiyi ac' olmali.")
    print("Emulator:", bulunan[0])
    return bulunan[0]


def dosya_bul(desen, haric=None):
    for yol in glob.glob(os.path.join(KOK, "apk", "**", desen), recursive=True):
        if haric is None or haric not in os.path.basename(yol):
            return yol
    return None


def kur():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from obb_yamala import lua_yamalari

    apk = os.path.join(KOK, "apk", PAKET + ".apk")
    if not os.path.exists(apk):
        apk = dosya_bul("*1.1.8*.apk") or dosya_bul(PAKET + "*.apk", haric="1.1.7")
    obb = dosya_bul("main.*.obb", haric="yamali")
    if not apk or not obb:
        hata("apk klasorunde 1.1.8 APK'si veya OBB bulunamadi.")
    obb_adi = os.path.basename(obb)

    adb_yolu = adb_bul()
    cihaz = cihaz_sec(adb_yolu)
    a = lambda *x, kontrol=True: adb(adb_yolu, "-s", cihaz, *x, kontrol=kontrol)
    print("APK kuruluyor...")
    a("install", "-r", apk)
    # OBB orijinal kalmali: Unity dosya sonunun MD5'ini APK kimligiyle karsilastiriyor.
    hedef = "/sdcard/Android/obb/%s/" % PAKET
    a("shell", "mkdir -p '%s'" % hedef)
    uzak_boyut = a("shell", "stat -c %%s '%s'" % (hedef + obb_adi), kontrol=False).strip()
    if uzak_boyut == str(os.path.getsize(obb)):
        print("Orijinal OBB zaten emulatorde, atlaniyor.")
    else:
        print("Orijinal OBB emulatore kopyalaniyor (bir dakika surebilir)...")
        a("push", obb, hedef + obb_adi)
    print("Yerel sunucu yamalari kopyalaniyor...")
    with tempfile.TemporaryDirectory() as gecici:
        for ad, veri in lua_yamalari(obb, "127.0.0.1", PORT).items():
            yerel = os.path.join(gecici, ad.replace("/", "_"))
            with open(yerel, "wb") as f:
                f.write(veri)
            uzak = YAMA_KLASORU + ad
            a("shell", "mkdir -p '%s'" % uzak.rsplit("/", 1)[0])
            a("push", yerel, uzak)
            print("  ", ad)
    print("\nKurulum tamam. Artik baslat.bat ile sunucuyu acip oyunu baslatabilirsin.")


def baglan():
    adb_yolu = adb_bul()
    cihaz = cihaz_sec(adb_yolu)
    adb(adb_yolu, "-s", cihaz, "reverse", "tcp:%d" % PORT, "tcp:%d" % PORT)
    print("Emulator sunucuya baglandi (127.0.0.1:%d)." % PORT)


def anlik_kayit():
    """Oyunu yeniden başlatmadan şu anki emülatör kaydını teshis.txt'ye yazar (takıldığı anda)."""
    adb_yolu = adb_bul()
    cihaz = cihaz_sec(adb_yolu)
    kayit = adb(adb_yolu, "-s", cihaz, "logcat", "-d", "-v", "time", "-t", "4000", kontrol=False)
    yol = os.path.join(KOK, "teshis.txt")
    with open(yol, "w", encoding="utf-8", errors="replace") as f:
        f.write("== anlik kayit\n" + kayit)
    print("Kayit yazildi:", yol)


def teshis():
    import time
    adb_yolu = adb_bul()
    cihaz = cihaz_sec(adb_yolu)
    a = lambda *x: adb(adb_yolu, "-s", cihaz, *x, kontrol=False)
    a("reverse", "tcp:%d" % PORT, "tcp:%d" % PORT)
    a("shell", "am", "force-stop", PAKET)
    a("logcat", "-c")
    print("Oyun baslatiliyor, 45 saniye bekleniyor...")
    a("shell", "monkey", "-p", PAKET, "-c", "android.intent.category.LAUNCHER", "1")
    time.sleep(45)
    bilgi = [
        "== cihaz: " + a("shell", "getprop", "ro.product.model") + " android " + a("shell", "getprop", "ro.build.version.release"),
        "== abi: " + a("shell", "getprop", "ro.product.cpu.abilist"),
        "== obb klasoru:\n" + a("shell", "ls", "-la", "/sdcard/Android/obb/%s/" % PAKET),
        "== paket:\n" + a("shell", "dumpsys", "package", PAKET),
        "== reverse:\n" + a("reverse", "--list"),
        "== veri klasoru:\n" + a("shell", "ls -laR '/sdcard/Android/data/%s/' | head -80" % PAKET),
        "== logcat:\n" + a("logcat", "-d", "-v", "time"),
    ]
    yol = os.path.join(KOK, "teshis.txt")
    with open(yol, "w", encoding="utf-8", errors="replace") as f:
        f.write("\n\n".join(bilgi))
    print("Kayit yazildi:", yol)


if __name__ == "__main__":
    komut = sys.argv[1] if len(sys.argv) > 1 else ""
    if komut == "kur":
        kur()
    elif komut == "baglan":
        baglan()
    elif komut == "teshis":
        teshis()
    elif komut == "kayit":
        anlik_kayit()
    else:
        hata(__doc__)
