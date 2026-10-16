"""Orijinal OBB'den, oyunu yerel sunucuya yönlendiren yamalı bir OBB üretir.

Değişen yalnızca iki Lua betiği (OBB içinde XOR 0xFF ile şifreli):
  - XmlReadInAdvanceManager.lua: HTTPS'i ve Seastar SDK girişini kapatır.
  - Utils/CdnPathUtils.lua: açılıştaki CDN adresini yerel sunucuya çevirir.
Oyun sunucusunun adresi sunucunun verdiği GatewayList.xml'den gelir.

Kullanım: python obb_yamala.py <orijinal.obb> <cikis.obb> <ip> [port]
"""
import sys
import zipfile

XML_YOLU = "assets/Lua/XmlReadInAdvanceManager.lua"
CDN_YOLU = "assets/Lua/Utils/CdnPathUtils.lua"
XML_CAPA = 'DemoManager.luaInstance.XmlConfigPlatName = "seastar_mix";'
XML_EK = (
    "\r\n\t-- yerel sunucu yamasi\r\n"
    "\tDemoManager.luaInstance.isHttps = false;\r\n"
    "\tDemoManager.luaInstance.IsUserSdk = false;\r\n"
)
CDN_SABLON = (
    'module("CdnPathUtils", package.seeall)\r\n'
    "luanet.load_assembly('UnityEngine');\r\n"
    "CdnPathUtils = {}\r\n"
    "-- yerel sunucu yamasi\r\n"
    "function GetPath()\r\n"
    '\treturn "http://IP_PORT/";\r\n'
    "end\r\n"
)


def xor(veri):
    return bytes(b ^ 0xFF for b in veri)


def yamala(kaynak, hedef, ip, port):
    with zipfile.ZipFile(kaynak) as giris, zipfile.ZipFile(hedef, "w") as cikis:
        bulunan = set()
        for bilgi in giris.infolist():
            veri = giris.read(bilgi)
            if bilgi.filename == XML_YOLU:
                metin = xor(veri).decode("utf-8")
                if XML_CAPA not in metin:
                    raise SystemExit("XmlReadInAdvanceManager.lua beklenen satiri icermiyor")
                veri = xor(metin.replace(XML_CAPA, XML_CAPA + XML_EK, 1).encode("utf-8"))
                bulunan.add(XML_YOLU)
            elif bilgi.filename == CDN_YOLU:
                veri = xor(CDN_SABLON.replace("IP_PORT", "%s:%d" % (ip, port)).encode("utf-8"))
                bulunan.add(CDN_YOLU)
            yeni = zipfile.ZipInfo(bilgi.filename, bilgi.date_time)
            yeni.compress_type = bilgi.compress_type
            yeni.external_attr = bilgi.external_attr
            cikis.writestr(yeni, veri)
    eksik = {XML_YOLU, CDN_YOLU} - bulunan
    if eksik:
        raise SystemExit("OBB icinde bulunamadi: %s" % ", ".join(sorted(eksik)))


if __name__ == "__main__":
    if len(sys.argv) < 4:
        raise SystemExit(__doc__)
    yamala(sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else 8881)
    print("Yamali OBB yazildi:", sys.argv[2])
