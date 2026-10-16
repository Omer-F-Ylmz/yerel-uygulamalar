"""Oyunu yerel sunucuya yönlendiren yamalı Lua dosyalarını üretir.

ÖNEMLİ: OBB'nin kendisi değiştirilmemeli. Unity, OBB'nin son 65558 baytının MD5'ini
APK'daki settings.xml kimliğiyle karşılaştırıyor; değişen OBB reddediliyor. Bunun yerine
yamalı Lua'lar oyunun üzerine yazma klasörüne konur (LuaScriptMgr.LoaderSuperStar önce
<persistentDataPath>!/assets/Lua/<ad>.lua dosyasına bakar):
  /sdcard/Android/data/com.seastar.gpplay.streetball/files!/assets/Lua/

Değişen Lua betikleri (OBB içinde XOR 0xFF ile şifreli):
  - XmlReadInAdvanceManager.lua: HTTPS'i ve Seastar SDK girişini kapatır.
  - Utils/CdnPathUtils.lua: açılıştaki CDN adresini yerel sunucuya çevirir.
  - Conf/LuaConfManager.lua: istemcinin kendi paketinde olmayan yapılandırma tablolarını
    boş tanımlar ve eksik data_scene_config satırları için varsayılan döner
    (orijinal istemci bunlar yüzünden lobide Lua hatası veriyor).
Oyun sunucusunun adresi sunucunun verdiği GatewayList.xml'den gelir.

Kullanım: python obb_yamala.py <orijinal.obb> <cikis.obb> <ip> [port]
"""
import json
import os
import sys
import zipfile

XML_YOLU = "assets/Lua/XmlReadInAdvanceManager.lua"
CDN_YOLU = "assets/Lua/Utils/CdnPathUtils.lua"
CONF_YOLU = "assets/Lua/Conf/LuaConfManager.lua"
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

CONF_EK = (
    "\r\n-- yerel sunucu yamasi: pakette olmayan tablolar ve eksik sahne ayarlari\r\n"
    "local yerel_eksik_tablolar = {\r\n"
    "	\"ActivityFacebookGift\", \"BossMovieInfo\", \"CheerLuaForQuality\", \"Cheerquality\",\r\n"
    "	\"EliteNpcInfo\", \"GrowthFundCondition\", \"GrowthFundDayAddBuyCount\", \"GrowthFundReward\",\r\n"
    "	\"SupremeMonthCardGift\", \"UnlockStrInfo\", \"andoid_gem\", \"data_elite_tips_stage\",\r\n"
    "	\"data_exchange_convert\", \"data_illustrated_arrt\", \"data_illustrated_grade_cost\", \"data_illustrated_level\",\r\n"
    "	\"data_illustrated_level_cost\", \"data_illustrated_player\", \"data_ladder_new_range\", \"data_ladder_new_range_detail\",\r\n"
    "	\"data_new_store_draw_player_config\", \"data_open_match_reset_cost\", \"data_player_book_active_circle_attr\", \"data_player_book_colour_attr\",\r\n"
    "	\"data_player_book_colour_skill\", \"data_player_book_line\", \"data_player_book_player_attr\", \"data_player_book_player_colour\",\r\n"
    "	\"data_player_book_point\", \"data_qualifiy_attr_param\", \"data_qualifiy_battleinfo\", \"data_qualifiy_formula\",\r\n"
    "	\"data_qualifiy_icon\", \"data_qualifiy_level_cost\", \"data_qualifiy_player_skill\", \"data_qualifiy_skill_cost\",\r\n"
    "	\"data_qualifiy_skill_info\", \"data_qualifiy_trial_config\", \"data_qualifiy_trial_droplist\", \"data_store_draw_player_s\",\r\n"
    "	\"data_store_draw_player_s_weight\", \"data_store_draw_player_single\", \"equipRecycleCostGemInfo\", \"equipRecycleGainItemInfo\",\r\n"
    "	\"monitoring_items\", \"playerGrowUpSPTrain\", \"playerSPTrainLaterID\", \"time_pay_gift\",\r\n"
    "}\r\n"
    "for _, ad in ipairs(yerel_eksik_tablolar) do\r\n"
    "\tif _G[ad .. \"_data\"] == nil then _G[ad .. \"_data\"] = {} end\r\n"
    "\tif _G[ad .. \"_keydata\"] == nil then _G[ad .. \"_keydata\"] = {} end\r\n"
    "end\r\n"
    "local yerel_sahne = LuaConfManager.getdata_scene_config\r\n"
    "function LuaConfManager.getdata_scene_config(id)\r\n"
    "\tlocal satir = yerel_sahne(id)\r\n"
    "\tif satir == nil then\r\n"
    "\t\tsatir = {id = tonumber(id) or 0, unLockLv = 0, isLvReward = 0, name = \"\", sceneName = \"\", describe = \"\", btType = 0, icon = \"\"}\r\n"
    "\tend\r\n"
    "\treturn satir\r\n"
    "end\r\n"
    "-- data_store_draw_limit'te dl_MiddleTenGem yok; DrawDataManager.GetDrawPlayerGemLimitCount(2) nil doner ve\r\n"
    "-- CardStage.InitUI / Window_DrawResult.UpdateBt nil aritmetiginde durur (Gem/Token 0, VIP5 maskesi, arama takilir)\r\n"
    "local yerel_cekilis_siniri = LuaConfManager.getdata_store_draw_limit\r\n"
    "function LuaConfManager.getdata_store_draw_limit(index)\r\n"
    "\tlocal satir = yerel_cekilis_siniri(index)\r\n"
    "\tif satir ~= nil and satir.dl_MiddleTenGem == nil then\r\n"
    "\t\tsatir.dl_MiddleTenGem = satir.dl_gem or 40\r\n"
    "\tend\r\n"
    "\treturn satir\r\n"
    "end\r\n"
    "-- Turkce ceviri: tum tablolar yuklendiginde Ceviri.lua sozlugu bir kez uygulanir\r\n"
    "local function yerel_cevir(t, gorulen)\r\n"
    "\tif gorulen[t] then return end\r\n"
    "\tgorulen[t] = true\r\n"
    "\tfor k, v in pairs(t) do\r\n"
    "\t\tif type(v) == \"string\" then\r\n"
    "\t\t\tlocal c = CEVIRI[v]\r\n"
    "\t\t\tif c ~= nil then t[k] = c end\r\n"
    "\t\telseif type(v) == \"table\" then\r\n"
    "\t\t\tyerel_cevir(v, gorulen)\r\n"
    "\t\tend\r\n"
    "\tend\r\n"
    "end\r\n"
    "local yerel_yukle = LuaConfManager.updateLoad\r\n"
    "function LuaConfManager.updateLoad()\r\n"
    "\tlocal bitti = yerel_yukle()\r\n"
    "\tif bitti == true and YEREL_CEVIRI_TAMAM ~= true then\r\n"
    "\t\tYEREL_CEVIRI_TAMAM = true\r\n"
    "\t\tif CEVIRI == nil then pcall(require, \"Ceviri\") end\r\n"
    "\t\tif type(CEVIRI) == \"table\" then\r\n"
    "\t\t\tlocal gorulen = {}\r\n"
    "\t\t\tfor ad, t in pairs(_G) do\r\n"
    "\t\t\t\tif type(ad) == \"string\" and type(t) == \"table\" and (string.sub(ad, -5) == \"_data\" or string.sub(ad, -8) == \"_keydata\") then\r\n"
    "\t\t\t\t\tyerel_cevir(t, gorulen)\r\n"
    "\t\t\t\tend\r\n"
    "\t\t\tend\r\n"
    "\t\tend\r\n"
    "\tend\r\n"
    "\treturn bitti\r\n"
    "end\r\n"
)


def lua_metni(s):
    """Lua 5.1 / LuaJIT için güvenli tırnaklı metin."""
    ozel = {"\\": "\\\\", '"': '\\"', "\n": "\\n", "\r": "\\r", "\t": "\\t", "\0": "\\0"}
    return '"' + "".join(ozel.get(c, c) for c in s) + '"'


def ceviri_lua(sozluk):
    satirlar = ["-- Turkce ceviri sozlugu (araclar/obb_yamala.py uretir)", "CEVIRI = {"]
    for kaynak, hedef in sorted(sozluk.items()):
        if isinstance(hedef, str) and hedef and hedef != kaynak:
            satirlar.append("[%s]=%s," % (lua_metni(kaynak), lua_metni(hedef)))
    satirlar.append("}")
    return "\r\n".join(satirlar) + "\r\n"


CEVIRI_JSON = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sunucu", "veri", "ceviri_tr.json")


def xor(veri):
    return bytes(b ^ 0xFF for b in veri)


def lua_yamalari(kaynak, ip="127.0.0.1", port=8881):
    """{'Lua/...lua': şifreli bayt} sözlüğü döner; OBB'ye dokunmaz."""
    cikti = {}
    with zipfile.ZipFile(kaynak) as giris:
        metin = xor(giris.read(XML_YOLU)).decode("utf-8")
        if XML_CAPA not in metin:
            raise SystemExit("XmlReadInAdvanceManager.lua beklenen satiri icermiyor")
        cikti[XML_YOLU] = xor(metin.replace(XML_CAPA, XML_CAPA + XML_EK, 1).encode("utf-8"))
        cikti[CDN_YOLU] = xor(CDN_SABLON.replace("IP_PORT", "%s:%d" % (ip, port)).encode("utf-8"))
        cikti[CONF_YOLU] = xor(xor(giris.read(CONF_YOLU)) + CONF_EK.encode("utf-8"))
    if os.path.exists(CEVIRI_JSON):
        with open(CEVIRI_JSON, encoding="utf-8") as f:
            cikti["assets/Lua/Ceviri.lua"] = xor(ceviri_lua(json.load(f)).encode("utf-8"))
    return {ad[len("assets/"):]: veri for ad, veri in cikti.items()}


def yamala(kaynak, hedef, ip, port):
    """Eski yöntem: yamalı OBB yazar. Unity kimlik kontrolü yüzünden cihazda KULLANILMAZ."""
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
            elif bilgi.filename == CONF_YOLU:
                veri = xor(xor(veri) + CONF_EK.encode("utf-8"))
                bulunan.add(CONF_YOLU)
            elif bilgi.filename == CDN_YOLU:
                veri = xor(CDN_SABLON.replace("IP_PORT", "%s:%d" % (ip, port)).encode("utf-8"))
                bulunan.add(CDN_YOLU)
            yeni = zipfile.ZipInfo(bilgi.filename, bilgi.date_time)
            yeni.compress_type = bilgi.compress_type
            yeni.external_attr = bilgi.external_attr
            cikis.writestr(yeni, veri)
    eksik = {XML_YOLU, CDN_YOLU, CONF_YOLU} - bulunan
    if eksik:
        raise SystemExit("OBB icinde bulunamadi: %s" % ", ".join(sorted(eksik)))


if __name__ == "__main__":
    # Kullanım: python obb_yamala.py <orijinal.obb> <cikis klasoru> [ip] [port]
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    ip = sys.argv[3] if len(sys.argv) > 3 else "127.0.0.1"
    port = int(sys.argv[4]) if len(sys.argv) > 4 else 8881
    for ad, veri in lua_yamalari(sys.argv[1], ip, port).items():
        yol = os.path.join(sys.argv[2], ad)
        os.makedirs(os.path.dirname(yol), exist_ok=True)
        open(yol, "wb").write(veri)
        print("yazildi:", yol)
