"""Emülatör işlemleri: adb'yi bul, bağlan, APK kur, OBB kopyala, port yönlendir.

Kullanım:
  python emulator.py kur      -> OBB'yi yamalar, APK'yı kurar, yamalı OBB'yi kopyalar (bir kez)
  python emulator.py baglan   -> emülatörün 127.0.0.1:8881'ini bilgisayardaki sunucuya yönlendirir
"""
import glob
import os
import shutil
import subprocess
import sys

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAKET = "com.seastar.gpplay.streetball"
PORT = 8881
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
    sonuc = subprocess.run([adb_yolu, *arg], capture_output=True, text=True)
    cikti = (sonuc.stdout + sonuc.stderr).strip()
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
    from obb_yamala import yamala

    apk = os.path.join(KOK, "apk", PAKET + ".apk")
    if not os.path.exists(apk):
        apk = dosya_bul("*1.1.8*.apk") or dosya_bul(PAKET + "*.apk", haric="1.1.7")
    obb = dosya_bul("main.*.obb", haric="yamali")
    if not apk or not obb:
        hata("apk klasorunde 1.1.8 APK'si veya OBB bulunamadi.")
    obb_adi = os.path.basename(obb)
    yamali = os.path.join(KOK, "apk", "yamali_" + obb_adi)
    print("OBB yamalaniyor (bir dakika surebilir)...")
    yamala(obb, yamali, "127.0.0.1", PORT)

    adb_yolu = adb_bul()
    cihaz = cihaz_sec(adb_yolu)
    print("APK kuruluyor...")
    adb(adb_yolu, "-s", cihaz, "install", "-r", apk)
    hedef = "/sdcard/Android/obb/%s/" % PAKET
    adb(adb_yolu, "-s", cihaz, "shell", "mkdir", "-p", hedef)
    print("Yamali OBB emulatore kopyalaniyor...")
    adb(adb_yolu, "-s", cihaz, "push", yamali, hedef + obb_adi)
    print("\nKurulum tamam. Artik baslat.bat ile sunucuyu acip oyunu baslatabilirsin.")


def baglan():
    adb_yolu = adb_bul()
    cihaz = cihaz_sec(adb_yolu)
    adb(adb_yolu, "-s", cihaz, "reverse", "tcp:%d" % PORT, "tcp:%d" % PORT)
    print("Emulator sunucuya baglandi (127.0.0.1:%d)." % PORT)


if __name__ == "__main__":
    komut = sys.argv[1] if len(sys.argv) > 1 else ""
    if komut == "kur":
        kur()
    elif komut == "baglan":
        baglan()
    else:
        hata(__doc__)
