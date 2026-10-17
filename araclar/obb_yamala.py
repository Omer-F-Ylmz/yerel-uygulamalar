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
    "-- Hata yakalayici: sunucu cevabini isleyen OnReceive hata verirse ayrinti sunucuya gonderilir\r\n"
    "local function yerel_hata_gonder(ad, hata)\r\n"
    "\tlocal metin = string.sub(string.gsub(tostring(hata), '[&=%c\"\\\\]', ' '), 1, 1500)\r\n"
    "\tpcall(Luahttp.PostC2S, \"\", 999, 1, '{\"m\":\"' .. tostring(ad) .. ': ' .. metin .. '\"}')\r\n"
    "end\r\n"
    "local yerel_sarili = {}\r\n"
    "local yerel_require = require\r\n"
    "function require(ad)\r\n"
    "\tlocal m = yerel_require(ad)\r\n"
    "\tif type(m) == \"table\" and type(rawget(m, \"OnReceive\")) == \"function\" and not yerel_sarili[m] then\r\n"
    "\t\tyerel_sarili[m] = true\r\n"
    "\t\tlocal asil = m.OnReceive\r\n"
    "\t\tm.OnReceive = function(...)\r\n"
    "\t\t\tlocal a = {...}\r\n"
    "\t\t\tlocal n = select(\"#\", ...)\r\n"
    "\t\t\tlocal r = {xpcall(function() return asil(unpack(a, 1, n)) end, debug.traceback)}\r\n"
    "\t\t\tif not r[1] then yerel_hata_gonder(ad, r[2]) return end\r\n"
    "\t\t\treturn unpack(r, 2, table.maxn(r))\r\n"
    "\t\tend\r\n"
    "\tend\r\n"
    "\treturn m\r\n"
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


MAC_YOLU = "assets/Lua/MatchLoader.lua"
# Maç yüklemesine iz noktaları: her adım logcat'e (print) ve sunucuya (999/2, kayit/mac_izi.txt) yazılır.
MAC_IZ_TANIM = (
    "\r\nlocal function YEREL_IZ(s)\r\n"
    "\ts = string.gsub(tostring(s), \"[\\r\\n\\t]\", \" \")\r\n"
    "\ts = string.gsub(s, \"[^%w%s%.:=/%-%(%)%[%]_,]\", \"\")\r\n"
    "\tprint(\"YEREL_IZ \" .. s)\r\n"
    "\tpcall(function() Luahttp.PostC2S(\"\", 999, 2, '{\"m\":\"' .. string.sub(s, 1, 600) .. '\"}') end)\r\n"
    "end\r\n"
)
MAC_IZLERI = [  # (çapa, önüne eklenecek, arkasına eklenecek)
    ("function battleBeginBattleId(battleId)\r\n", "", "\tYEREL_IZ(\"705 gonderiliyor id=\" .. tostring(battleId))\r\n"),
    ("if(protocolsub == EnumProtocolSub.BattleBegin or protocolsub == EnumProtocolSub.BattleBeginEx) then\r\n", "",
     "\t\tYEREL_IZ(\"705 cevabi geldi sonuc=\" .. tostring(result))\r\n"),
    ("MatchManager.luaInstance:initBattleInfo(dataobj", "YEREL_IZ(\"initBattleInfo\") ", ""),
    ("\t\t\tMatchManager.luaInstance:initPlayerInfo(_isSelf",
     "\t\t\tYEREL_IZ(\"oyuncu \" .. tostring(_isSelf) .. \" dalga=\" .. waveIndex .. \" id=\" .. tostring(_player['id']) .. \" beceri=\" .. tostring(#_player['skill_list']))\r\n", ""),
    ("TeamManager.RedTeam:setCheerLeaderInfo", "YEREL_IZ(\"amigo \" .. tostring(cheer['id'])) ", ""),
    ('InitBattleTeamInfo(dataobj["data"]["battlemsg"]["battle_player_self"], true);', "YEREL_IZ(\"kendi takim\") ", ""),
    ('InitBattleTeamInfo(dataobj["data"]["battlemsg"]["battle_player_enemy"], false);', "YEREL_IZ(\"rakip takim\") ", ""),
    ("MatchManager.luaInstance:initPlayerTeam(isHomeTeam)", "YEREL_IZ(\"initPlayerTeam\") ", ""),
    ("MatchManager.luaInstance:initSceneId(sceneId)", "YEREL_IZ(\"sahne \" .. tostring(sceneId)) ", ""),
    ("MatchManager.luaInstance:battleBeginOver(true)", "YEREL_IZ(\"battleBeginOver basliyor\") ",
     " YEREL_IZ(\"battleBeginOver bitti - bundan sonrasi oyunun kendi yuklemesi\")"),
]
MAC_IZ_SON = (
    "\r\nlocal yerel_asil_onreceive = OnReceive\r\n"
    "function OnReceive(...)\r\n"
    "\tlocal a = {...}\r\n"
    "\tlocal n = select(\"#\", ...)\r\n"
    "\tlocal ok, hata = xpcall(function() return yerel_asil_onreceive(unpack(a, 1, n)) end, debug.traceback)\r\n"
    "\tif not ok then YEREL_IZ(\"HATA \" .. tostring(hata)) error(hata, 0) end\r\n"
    "end\r\n"
)


def mac_izi(metin):
    """MatchLoader.lua'ya iz noktaları ekler; çapa bulunamazsa hata verir (oyun sürümü farklı demektir)."""
    ilk = metin.index("\r\n") + 2
    metin = metin[:ilk] + MAC_IZ_TANIM + metin[ilk:]
    for capa, once, sonra in MAC_IZLERI:
        if metin.count(capa) != 1:
            raise SystemExit("MatchLoader.lua beklenen satiri icermiyor: " + capa.strip())
        metin = metin.replace(capa, once + capa + sonra, 1)
    # Donmanın asıl sebebi: kod her oyuncuya 99999 "ortak becerisi" ekliyor ama OBB'deki SkillInfo tablosunda
    # bu beceri yok (canlı sunucunun güncel tablosunda vardı). C# tarafı tabloda olmayan beceride null'a
    # erişip çöküyor; çökme Lua->C#->Lua iç içe çağrının ortasında olduğundan hata yerine donma görünüyor.
    # Tabloda olmayan beceriler listeden çıkarılır (ileride başka eksik çıkarsa da donmaz, iz bırakır).
    capa = "\t\t\ttable.insert(_player['skill_list'], commonSkill)\r\n"
    if metin.count(capa) != 1:
        raise SystemExit("MatchLoader.lua beklenen satiri icermiyor: " + capa.strip())
    metin = metin.replace(capa, (
        "\t\t\tif LuaConfManager.getSkillInfo(commonSkill.skill_id) ~= nil then table.insert(_player['skill_list'], commonSkill) end\r\n"
        "\t\t\tlocal yerel_temiz = {}\r\n"
        "\t\t\tfor _, yerel_s in ipairs(_player['skill_list']) do\r\n"
        "\t\t\t\tif LuaConfManager.getSkillInfo(yerel_s.skill_id) ~= nil then table.insert(yerel_temiz, yerel_s)\r\n"
        "\t\t\t\telse YEREL_IZ(\"beceri tabloda yok, atlandi: \" .. tostring(yerel_s.skill_id)) end\r\n"
        "\t\t\tend\r\n"
        "\t\t\t_player['skill_list'] = yerel_temiz\r\n"), 1)
    # Oyuncu yüklemesi bitti izi: initPlayerInfo satırının sonuna
    bas = metin.index("\t\t\tMatchManager.luaInstance:initPlayerInfo(_isSelf")
    son = metin.index("\r\n", bas)
    metin = metin[:son] + " YEREL_IZ(\"oyuncu bitti\")" + metin[son:]
    return metin + MAC_IZ_SON


NITELIK_YOLU = "assets/Lua/PlayerAttribute.lua"
NITELIK_IZLERI = [
    ("function initDataWithLuaTable(playerId, attrTable, playerAttributeCalc)\r\n", "",
     "\tYEREL_IZ(\"nitelik basladi id=\" .. tostring(playerId))\r\n"),
    ("function initCommonAttr(playerId, playerAttributeCalc)\r\n", "",
     "\tYEREL_IZ(\"ortak nitelik id=\" .. tostring(playerId))\r\n"),
    ("\tplayerAttributeCalc:setBaseValue(Enum_Attr_Mastery, 1) --\u4f53\u529b\u5145\u6c9b\u9636\u6bb5\u4f24\u5bb3\u7cfb\u6570\r\n", "",
     "\tYEREL_IZ(\"ortak nitelik bitti\")\r\n"),
]
# C#'tan çağrılan Lua'da çıkan hata, iç içe çağrı yüzünden oyunu dondurur; burada yakalanıp iz olarak gönderilir
NITELIK_SON = (
    "\r\nlocal yerel_asil_nitelik = initDataWithLuaTable\r\n"
    "function initDataWithLuaTable(playerId, attrTable, playerAttributeCalc)\r\n"
    "\tlocal ok, hata = xpcall(function() yerel_asil_nitelik(playerId, attrTable, playerAttributeCalc) end, debug.traceback)\r\n"
    "\tif not ok then YEREL_IZ(\"NITELIK HATA \" .. tostring(hata)) end\r\n"
    "end\r\n"
)


def izli(metin, izler, yukleme_izi, son=""):
    """Lua dosyasına YEREL_IZ tanımı ve iz noktaları ekler; çapa yoksa hata verir."""
    ilk = metin.index("\r\n") + 2
    metin = metin[:ilk] + MAC_IZ_TANIM + "YEREL_IZ(\"%s\")\r\n" % yukleme_izi + metin[ilk:]
    for capa, once, sonra in izler:
        if metin.count(capa) != 1:
            raise SystemExit("Lua dosyasi beklenen satiri icermiyor: " + capa.strip())
        metin = metin.replace(capa, once + capa + sonra, 1)
    return metin + son


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
        cikti[MAC_YOLU] = xor(mac_izi(xor(giris.read(MAC_YOLU)).decode("utf-8")).encode("utf-8"))
        cikti[NITELIK_YOLU] = xor(izli(xor(giris.read(NITELIK_YOLU)).decode("utf-8"), NITELIK_IZLERI,
                                       "PlayerAttribute dosyasi yuklendi", NITELIK_SON).encode("utf-8"))
    if os.path.exists(CEVIRI_JSON):
        with open(CEVIRI_JSON, encoding="utf-8") as f:
            cikti["assets/Lua/Ceviri.lua"] = xor(ceviri_lua(json.load(f)).encode("utf-8"))
    return {ad[len("assets/"):]: veri for ad, veri in cikti.items()}


# Beceri ve maç betikleri C#'tan doğrudan çağrılır (enterStart -> skillEffect -> effect_GameStart vb.). OBB'deki
# veri tabloları Lua betiklerinden eski olduğundan bazı betikler tabloda olmayan buff/işlev id'leriyle hata
# veriyor; hata C# tarafındaki adımı (maç başlatma, dalga geçişi...) yarıda bırakıyor ve maç takılıyor.
# Bu ek, modülün her fonksiyonunu pcall ile sarar: hata veren beceri atlanır, bir kez sunucuya bildirilir.
KORUNAN_KLASORLER = ("Lua/Skill_QTE/", "Lua/Skill/", "Lua/Battle/")
KORUMA_BAS = "local yerel_G = _G\r\n"
KORUMA_SON = (
    "\r\n-- yerel sunucu: betik hatasi maci kilitlemesin (bir kez bildirilir, islev atlanir)\r\n"
    "do\r\n"
    "\tlocal yerel_mod = yerel_G.rawget(yerel_G.getfenv(1), \"_M\")\r\n"
    "\tif yerel_G.type(yerel_mod) == \"table\" and yerel_mod ~= yerel_G then\r\n"
    "\t\tlocal yerel_bildirilen = {}\r\n"
    "\t\tfor yerel_ad, yerel_f in yerel_G.pairs(yerel_mod) do\r\n"
    "\t\t\tif yerel_G.type(yerel_f) == \"function\" and yerel_G.type(yerel_ad) == \"string\" then\r\n"
    "\t\t\t\tyerel_mod[yerel_ad] = function(...)\r\n"
    "\t\t\t\t\tlocal r = {yerel_G.pcall(yerel_f, ...)}\r\n"
    "\t\t\t\t\tif r[1] then return yerel_G.unpack(r, 2, yerel_G.table.maxn(r)) end\r\n"
    "\t\t\t\t\tif not yerel_bildirilen[yerel_ad] then\r\n"
    "\t\t\t\t\t\tyerel_bildirilen[yerel_ad] = true\r\n"
    "\t\t\t\t\t\tlocal s = yerel_G.string.gsub(yerel_G.tostring(r[2]), \"[^%w%s%.:=/%-%(%)%[%]_,]\", \"\")\r\n"
    "\t\t\t\t\t\tyerel_G.pcall(function() yerel_G.Luahttp.PostC2S(\"\", 999, 2, '{\"m\":\"BETIK HATA ' .. yerel_G.tostring(yerel_mod._NAME) .. '.' .. yerel_ad .. ': ' .. yerel_G.string.sub(s, 1, 500) .. '\"}') end)\r\n"
    "\t\t\t\t\tend\r\n"
    "\t\t\t\t\treturn nil\r\n"
    "\t\t\t\tend\r\n"
    "\t\t\tend\r\n"
    "\t\tend\r\n"
    "\tend\r\n"
    "end\r\n"
)


def betik_koruma(metin):
    """Modül fonksiyonlarını pcall ile sarar. Dosya module() kullanmıyorsa ek bir şey yapmaz."""
    if "module(" not in metin:
        return metin
    bom = "\ufeff" if metin.startswith("\ufeff") else ""
    return bom + KORUMA_BAS + metin[len(bom):].rstrip("\r\n") + "\r\n" + KORUMA_SON


def tum_lua(kaynak):
    """OBB'deki bütün Lua dosyaları: {'Lua/...': şifreli bayt}. Beceri/maç betikleri korumayla.
    Oyunun Lua yükleyicisi dosyayı yama klasöründe bulursa diskten okur; bulamazsa OBB'den WWW ile okur."""
    cikti = {}
    with zipfile.ZipFile(kaynak) as giris:
        for ad in giris.namelist():
            if not ad.startswith("assets/Lua/") or ad.endswith("/"):
                continue
            yol, veri = ad[len("assets/"):], giris.read(ad)
            if yol.startswith(KORUNAN_KLASORLER) and yol.endswith(".lua"):
                try:
                    metin = xor(veri).decode("utf-8")
                except UnicodeDecodeError:
                    metin = None  # birkaç betik farklı şifreli (XOR değil); olduğu gibi bırakılır
                if metin is not None:
                    veri = xor(betik_koruma(metin).encode("utf-8"))
            cikti[yol] = veri
    return cikti


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
