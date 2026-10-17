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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import conf_yamala  # noqa: E402  (eksik buff tanımlarının Lua tarafı)

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
    "\t-- Tablolar eszamanli yuklenir (ConfManager.loadJsonFile); kare basina tek tablo yerine 80 tablo:\r\n"
    "\t-- lobi yukleme ekrani ~12 saniyeden birkac kareye iner.\r\n"
    "\tlocal bitti = yerel_yukle()\r\n"
    "\tlocal yerel_adim = 0\r\n"
    "\twhile bitti ~= true and yerel_adim < 80 do\r\n"
    "\t\tbitti = yerel_yukle()\r\n"
    "\t\tyerel_adim = yerel_adim + 1\r\n"
    "\tend\r\n"
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
# Her iz eşzamanlı bir HTTP isteği (Luahttp.PostC2S) -> maç sırasında saniyede onlarca "nitelik" izi oyunu
# takılttığından izler varsayılan kapalı; yalnız HATA içerenler gider. Yükleme sorununu incelemek için True yap.
IZ_ACIK = False
MAC_IZ_TANIM = (
    "\r\nYEREL_IZ_ACIK = %s\r\n" % ("true" if IZ_ACIK else "false") +
    "local function YEREL_IZ(s)\r\n"
    "\ts = string.gsub(tostring(s), \"[\\r\\n\\t]\", \" \")\r\n"
    "\ts = string.gsub(s, \"[^%w%s%.:=/%-%(%)%[%]_,]\", \"\")\r\n"
    "\tif not YEREL_IZ_ACIK and not string.find(s, \"HATA\", 1, true) then return end\r\n"
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


# ---------------------------------------------------------------- Efsane Modu (Aomine, Kise)
# Yeni pasif beceri (conf_yamala.EK_BECERILER, id 90001) ve player_formula.lua yaması. Oyun formülleri Lua'da:
# getBlockRate / getMultiBlockResult / getTriggerBlockRate (blok) ve getStealSuccessResult (top çalma).
# Dayanıklılık ("体力") C# attackPressure: 70'i geçince oyuncu yorulur; attackPressureChangeCoe/Abs alanları
# Lua'ya açık, 0 yapılınca sıradan hareketler ve beceriler dayanıklılık tüketmez.
FORMUL_YOLU = "assets/Lua/player_formula.lua"
EFSANE_YOLU = "Lua/Skill_QTE/Skill_Yerel_Efsane.lua"
EFSANE_BUFF = conf_yamala.EFSANE_BUFF
# Skill_Passive_MV3 (Wade'in arkadan bloğu) 1133 "MY HOUSE" buff'ı varken her dış şutta tetiklenir.
EFSANE_LUA = (
    'module("Skill_QTE/Skill_Yerel_Efsane", package.seeall)\r\n'
    '\r\n'
    'require "functions"\r\n'
    'require "player_formula"\r\n'
    'require "PlayerAttribute"\r\n'
    '\r\n'
    '-- Yerel sunucu: Efsane Modu. Isaret buff %(buff)d player_formula yamasinda okunur.\r\n'
    'local YEREL_BUFF = %(buff)d\r\n'
    'local YEREL_YUKSELIS = %(yukselis)d\r\n'
    'local YEREL_YUKSELIS_AOMINE = %(yukselis_aomine)d\r\n'
    'local YEREL_AOMINE = 1011\r\n'
    'local YEREL_EK_ULTILER = {10071, 10020}  -- Rukawa "突击暴扣", Kagami "流星灌篮" (ulti zinciri icin gecici beceri)\r\n'
    'local YEREL_UYANIS = 1133\r\n'
    '-- Maliyeti sifirlanan beceriler: blok/calma + ultiler (kendi + zincir): bekleme 0, enerji 0, dayaniklilik 0.\r\n'
    'local SIFIR_MALIYET = {30089, 30063, 30005, 20136, 10026, 10090, 10048, 10071, 10020}\r\n'
    '\r\n'
    'function getAvailableState()\r\n'
    '\treturn {0, 24, 45, 52}  -- GameStart, Goal, TurnStart, PlayerEnergyChanged\r\n'
    'end\r\n'
    '\r\n'
    '-- Zone (buff tipi 4: 1036, 20037 varsa 1037) hic kapanmasin: her tur yeniden eklenir, suresi sifirlanir.\r\n'
    '-- 20038 "终结者" varsa Zone ile gelen gecici beceri 20001 de takili kalir (Skill_Active_ZiWoYiZhi ile ayni).\r\n'
    'local function zone_koru(p)\r\n'
    '\tif p:luaHasSkill(10026) == false and p:luaHasSkill(10090) == false then return end\r\n'
    '\tif p:luaHasSkill(20037) then\r\n'
    '\t\tPlayerBuffManager.luaInstance:addBuff(p, 1037)\r\n'
    '\telse\r\n'
    '\t\tPlayerBuffManager.luaInstance:addBuff(p, 1036)\r\n'
    '\tend\r\n'
    '\tif p:luaHasSkill(20038) and p:luaHasSkill(20001) == false then\r\n'
    '\t\tp:addSkillTemp(20001)\r\n'
    '\tend\r\n'
    'end\r\n'
    '\r\n'
    '-- addCoolDownCalc/addEnergyCalc carpani 0 yapar; setCoolDownRestTime(0) mac basindaki ilk beklemeyi de siler.\r\n'
    'local function maliyet_sifirla(p)\r\n'
    '\tfor _, id in ipairs(SIFIR_MALIYET) do\r\n'
    '\t\tif p:luaHasSkill(id) then\r\n'
    '\t\t\tp:luaChangeSkillCoolDown(id, 0, 0)\r\n'
    '\t\t\tp:luaChangeSkillEnergyCost(id, 0, 0)\r\n'
    '\t\t\tp:luaChangeSkillAtkPressure(id, 0, 0)\r\n'
    '\t\t\tlocal d = p:luaFindSkillData(id)\r\n'
    '\t\t\tif d ~= nil then d:setCoolDownRestTime(0) end\r\n'
    '\t\tend\r\n'
    '\tend\r\n'
    'end\r\n'
    '\r\n'
    'local function dayaniklilik_kilitle(p)\r\n'
    '\tp.attackPressureChangeCoe = 0\r\n'
    '\tp.attackPressureChangeAbs = 0\r\n'
    '\tp.attackPressureChangeExtraCoe = 0\r\n'
    '\tp.attackPressureChangeExtraAbs = 0\r\n'
    '\tif p.attackPressure > 0 then\r\n'
    '\t\tp:luaAddAttackPressure(-p.attackPressure)\r\n'
    '\tend\r\n'
    'end\r\n'
    '\r\n'
    'function effect_GameStart(p_player, p_skillId)\r\n'
    '\tif p_player:luaHasBuff(YEREL_BUFF) == false then\r\n'
    '\t\tPlayerBuffManager.luaInstance:addBuff(p_player, YEREL_BUFF)\r\n'
    '\tend\r\n'
    '\tif p_player:luaHasBuff(YEREL_UYANIS) == false then\r\n'
    '\t\tPlayerBuffManager.luaInstance:addBuff(p_player, YEREL_UYANIS)\r\n'
    '\tend\r\n'
    '\tfor _, id in ipairs(YEREL_EK_ULTILER) do\r\n'
    '\t\tif p_player:luaHasSkill(id) == false then p_player:addSkillTemp(id) end\r\n'
    '\tend\r\n'
    '\tmaliyet_sifirla(p_player)\r\n'
    '\tdayaniklilik_kilitle(p_player)\r\n'
    '\tzone_koru(p_player)\r\n'
    '\tpcall(function() Luahttp.PostC2S("", 999, 2, \'{"m":"EFSANE %(surum)s basladi id=\' .. p_player.playerId .. \'"}\') end)\r\n'
    'end\r\n'
    '\r\n'
    '-- Her tur: saldiri ve savunma x1.5 (yigilir), Zone tazelenir.\r\n'
    'function effect_TurnStart(p_player, p_skillId)\r\n'
    '\tif p_player.playerId == YEREL_AOMINE then\r\n'
    '\t\tPlayerBuffManager.luaInstance:addBuff(p_player, YEREL_YUKSELIS_AOMINE)\r\n'
    '\telse\r\n'
    '\t\tPlayerBuffManager.luaInstance:addBuff(p_player, YEREL_YUKSELIS)\r\n'
    '\tend\r\n'
    '\tzone_koru(p_player)\r\n'
    '\tdayaniklilik_kilitle(p_player)\r\n'
    '\tmaliyet_sifirla(p_player)\r\n'
    'end\r\n'
    '\r\n'
    '-- C# effect cagrisi: (oyuncu, olay parametreleri..., beceriId); beceri id en sonda gelir.\r\n'
    'function effect_PlayerEnergyChanged(p_player, degisen, fark, p_skillId)\r\n'
    '\tif degisen == p_player then\r\n'
    '\t\tdayaniklilik_kilitle(p_player)\r\n'
    '\tend\r\n'
    'end\r\n'
    '\r\n'
    '-- Sayi atinca takim caninin %%20\'si dolar (Skill_Gift_BuQuYiZhi ile ayni yol: luaDoCure).\r\n'
    'function effect_Goal(p_player, p_goalInfo, p_skillId)\r\n'
    '\tlocal takim = p_player.selfTeam\r\n'
    '\tif takim ~= nil and takim.TeamHpMax ~= nil then\r\n'
    '\t\tp_player:luaDoCure(takim.TeamHpMax * 0.2)\r\n'
    '\tend\r\n'
    'end\r\n'
) % {"buff": EFSANE_BUFF, "yukselis": conf_yamala.EFSANE_YUKSELIS,
       "yukselis_aomine": conf_yamala.EFSANE_YUKSELIS_AOMINE, "surum": "v5"}

# player_formula.lua: fonksiyon başlığından hemen sonra eklenen satırlar
FORMUL_IZLERI = (
    ("function getBlockRate(p_blocker, p_shooter, shotType)\r\n",
     "\tif p_shooter:luaHasBuff(%d) then return 0 end\r\n" % EFSANE_BUFF),
    ("function getMultiBlockResult(p_blockerList, p_shooter, shotType)\r\n",
     "\tif p_shooter:luaHasBuff(%d) then return p_shooter end\r\n"
     "\tfor yerel_i = 0, p_blockerList.Count - 1 do\r\n"
     "\t\tif p_blockerList[yerel_i]:luaHasBuff(%d) then return p_blockerList[yerel_i] end\r\n"
     "\tend\r\n" % (EFSANE_BUFF, EFSANE_BUFF)),
    ("function getTriggerBlockRate(p_blockerList, p_shooter)\r\n",
     "\tif p_shooter:luaHasBuff(%d) then return p_shooter end\r\n"
     "\tfor yerel_i = 0, p_blockerList.Count - 1 do\r\n"
     "\t\tif p_blockerList[yerel_i]:luaHasBuff(%d) then return p_blockerList[yerel_i] end\r\n"
     "\tend\r\n" % (EFSANE_BUFF, EFSANE_BUFF)),
    ("function getStealSuccessResult(player, target, paramOne)\r\n",
     "\tif player:luaHasBuff(%d) then return true end\r\n" % EFSANE_BUFF),
    # Top sürerken kendiliğinden çalınma (C# battleStealBall): savunanlardan biri Efsane ise kesin.
    ("function getBeStealRate(p_carryer)\r\n",
     "\tlocal yerel_sav = p_carryer:luaGetDefendSources()\r\n"
     "\tif yerel_sav ~= nil then\r\n"
     "\t\tfor yerel_i = 0, yerel_sav.Count - 1 do\r\n"
     "\t\t\tif yerel_sav[yerel_i]:luaHasBuff(%d) then return 1 end\r\n"
     "\t\tend\r\n"
     "\tend\r\n" % EFSANE_BUFF),
)


# Skill_Passive_MV3 (Wade'in arkadan bloğu): normalde yalnız eşleşmediği oyuncunun şutunda ve belli durumlarda
# tetiklenir. Efsane oyuncusu savunmadayken her rakip şutunda tetiklensin (blok sonucu player_formula'da kesin).
MV3_YOLU = "assets/Lua/Skill_QTE/Skill_Passive_MV3.lua"
MV3_CAPA = "function isCastAvailable(p_player, blocktarget)\r\n"
MV3_EK = ("\tif blocktarget ~= nil and p_player:luaHasBuff(%d) and p_player:luaIsSkillAvailable(30089) then\r\n"
          "\t\treturn true\r\n"
          "\tend\r\n" % EFSANE_BUFF)


# Ulti zinciri: Aomine (超越, Skill_Active_ZiWoYiZhi) ve Kise (完美无缺的模仿, Skill_Active_WanMeiWuQue) ultisi
# başlarken Efsane oyuncusu 1/3 Rukawa "突击暴扣", 1/3 Kagami "流星灌篮" ultisine geçer (Kise'nin 模仿术 betiğiyle
# aynı yol: luaStartActionScript mevcut aksiyonu bırakıp diğer betiği başlatır). Geçici beceriler GameStart'ta eklenir.
ULTI_YOLLARI = ("assets/Lua/Skill_QTE/Skill_Active_ZiWoYiZhi.lua", "assets/Lua/Skill_QTE/Skill_Active_WanMeiWuQue.lua")
ULTI_CAPA = "function start(p_player,p_skillId)\r\n"
ULTI_EK = (
    "\tif p_player:luaHasBuff(%(b)d) then\r\n"
    "\t\t-- Efsane: 1 kendi ultisi, 2 Rukawa, 3 Kagami; bir onceki secim haric rastgele (ust uste ayni ulti olmaz).\r\n"
    "\t\tlocal yerel_sec = {{nil, 0}, {\"Skill_QTE/Skill_Active_TuRuBaoKou\", 10071}, {\"Skill_QTE/Skill_Active_LiuXingGuanLan\", 10020}}\r\n"
    "\t\tif _G.YEREL_SON_ULTI == nil then _G.YEREL_SON_ULTI = {} end\r\n"
    "\t\tlocal yerel_son = _G.YEREL_SON_ULTI[p_player.playerId]\r\n"
    "\t\tlocal yerel_adaylar = {}\r\n"
    "\t\tfor yerel_i = 1, 3 do\r\n"
    "\t\t\tif yerel_i ~= yerel_son then table.insert(yerel_adaylar, yerel_i) end\r\n"
    "\t\tend\r\n"
    "\t\tlocal yerel_secim = yerel_adaylar[RandomManager.luaInstance:luaRangeInt(1, #yerel_adaylar + 1)]\r\n"
    "\t\t_G.YEREL_SON_ULTI[p_player.playerId] = yerel_secim\r\n"
    "\t\tlocal yerel_adlar = {\"kendi\", \"Rukawa\", \"Kagami\"}\r\n"
    "\t\tpcall(function() p_player:luaShowTalk(\"Ulti: \" .. yerel_adlar[yerel_secim]) end)\r\n"
    "\t\tpcall(function() Luahttp.PostC2S(\"\", 999, 2, '{\"m\":\"ULTI \" .. p_player.playerId .. \" \" .. yerel_adlar[yerel_secim] .. \" (onceki \" .. tostring(yerel_son) .. \")\"}') end)\r\n"
    "\t\tif yerel_secim ~= 1 then\r\n"
    "\t\t\tlocal yerel_b = yerel_sec[yerel_secim]\r\n"
    "\t\t\tif p_player:luaHasSkill(yerel_b[2]) == false then p_player:addSkillTemp(yerel_b[2]) end\r\n"
    "\t\t\tp_player:luaStartActionScript(yerel_b[1], yerel_b[2])\r\n"
    "\t\t\treturn\r\n"
    "\t\tend\r\n"
    "\tend\r\n" % {"b": EFSANE_BUFF})


# Zincirlenen ultiler (Rukawa 10071, Kagami 10020) Efsane oyuncusuna geçici beceri olarak ekli; bu betiklerin kendi
# effect_PressSkillBtn'leri de ulti düğmesine cevap verip asıl ulti betiğini bastırıyordu (listede sonuncu olan Kagami
# hep kazanıyordu, kayıt 15:19-15:22: ULTI izi yok). Efsane oyuncusunda düğmeye tepki vermesinler; seçici başlatır.
ZINCIR_YOLLARI = ("assets/Lua/Skill_QTE/Skill_Active_TuRuBaoKou.lua", "assets/Lua/Skill_QTE/Skill_Active_LiuXingGuanLan.lua")
ZINCIR_CAPA = "function effect_PressSkillBtn(p_player,p_skillId)\r\n"
ZINCIR_EK = "\tif p_player:luaHasBuff(%d) then return end\r\n" % EFSANE_BUFF


def zincir_yamala(metin, yol):
    if metin.count(ZINCIR_CAPA) != 1:
        raise SystemExit("%s beklenen effect_PressSkillBtn satirini icermiyor" % yol)
    return metin.replace(ZINCIR_CAPA, ZINCIR_CAPA + ZINCIR_EK, 1)


def ulti_yamala(metin, yol):
    if metin.count(ULTI_CAPA) != 1:
        raise SystemExit("%s beklenen start satirini icermiyor" % yol)
    return metin.replace(ULTI_CAPA, ULTI_CAPA + ULTI_EK, 1)


def mv3_yamala(metin):
    if metin.count(MV3_CAPA) != 1:
        raise SystemExit("Skill_Passive_MV3.lua beklenen satiri icermiyor")
    return metin.replace(MV3_CAPA, MV3_CAPA + MV3_EK, 1)


def formul_yamala(metin):
    """player_formula.lua: Efsane Modu kontrolleri. Çapa yoksa hata verir (OBB sürümü değişmiş demektir)."""
    for capa, ek in FORMUL_IZLERI:
        if metin.count(capa) != 1:
            raise SystemExit("player_formula.lua beklenen satiri icermiyor: %r" % capa.strip())
        metin = metin.replace(capa, capa + ek, 1)
    return metin


def lua_yamalari(kaynak, ip="127.0.0.1", port=8881):
    """{'Lua/...lua': şifreli bayt} sözlüğü döner; OBB'ye dokunmaz."""
    cikti = {}
    with zipfile.ZipFile(kaynak) as giris:
        metin = xor(giris.read(XML_YOLU)).decode("utf-8")
        if XML_CAPA not in metin:
            raise SystemExit("XmlReadInAdvanceManager.lua beklenen satiri icermiyor")
        cikti[XML_YOLU] = xor(metin.replace(XML_CAPA, XML_CAPA + XML_EK, 1).encode("utf-8"))
        cikti[CDN_YOLU] = xor(CDN_SABLON.replace("IP_PORT", "%s:%d" % (ip, port)).encode("utf-8"))
        cikti[CONF_YOLU] = xor(xor(giris.read(CONF_YOLU)) + (CONF_EK + conf_yamala.buff_lua_eki()).encode("utf-8"))
        cikti[MAC_YOLU] = xor(mac_izi(xor(giris.read(MAC_YOLU)).decode("utf-8")).encode("utf-8"))
        cikti[NITELIK_YOLU] = xor(izli(xor(giris.read(NITELIK_YOLU)).decode("utf-8"), NITELIK_IZLERI,
                                       "PlayerAttribute dosyasi yuklendi", NITELIK_SON).encode("utf-8"))
        cikti[FORMUL_YOLU] = xor(formul_yamala(xor(giris.read(FORMUL_YOLU)).decode("utf-8")).encode("utf-8"))
        cikti["assets/" + EFSANE_YOLU] = xor(EFSANE_LUA.encode("utf-8"))
        cikti[MV3_YOLU] = xor(betik_koruma(mv3_yamala(xor(giris.read(MV3_YOLU)).decode("utf-8"))).encode("utf-8"))
        for yol in ULTI_YOLLARI:
            cikti[yol] = xor(betik_koruma(ulti_yamala(xor(giris.read(yol)).decode("utf-8"), yol)).encode("utf-8"))
        for yol in ZINCIR_YOLLARI:
            cikti[yol] = xor(betik_koruma(zincir_yamala(xor(giris.read(yol)).decode("utf-8"), yol)).encode("utf-8"))
    if os.path.exists(CEVIRI_JSON):
        with open(CEVIRI_JSON, encoding="utf-8") as f:
            cikti["assets/Lua/Ceviri.lua"] = xor(ceviri_lua(json.load(f)).encode("utf-8"))
    return {ad[len("assets/"):]: veri for ad, veri in cikti.items()}


# Beceri ve maç betikleri C#'tan doğrudan çağrılır (enterStart -> skillEffect -> effect_GameStart vb.). OBB'deki
# veri tabloları Lua betiklerinden eski olduğundan bazı betikler tabloda olmayan buff/işlev id'leriyle hata
# veriyor; hata C# tarafındaki adımı (maç başlatma, dalga geçişi...) yarıda bırakıyor ve maç takılıyor.
# Bu ek, modülün her fonksiyonunu pcall ile sarar: hata veren beceri atlanır, bir kez sunucuya bildirilir.
KORUNAN_KLASORLER = ("Lua/Skill_QTE/", "Lua/Skill/", "Lua/Battle/")
# Betikler modül düzeyinde durum tutar (ör. TuJinBaoKou'daki rate) ve Kise'nin kopyalama becerisi rakibin betiğini
# Kise'ye çalıştırır: betik, sahibinde olup kopyalayanda olmayan bir beceriyi luaFindSkillData ile ister, nil döner,
# luaDoShotSkill(…, nil, …) C# içinde patlar ve loglanmayan donma olur (14:45:08 "Can NOT find skillData 1012/30073").
# yerel_bul: beceri yoksa oyuncunun kendi hücum becerisinin verisini kullanır.
KORUMA_BAS = (
    "local yerel_G = _G\r\n"
    "local function yerel_bul(p, id)\r\n"
    "\tlocal d = p:luaFindSkillData(id)\r\n"
    "\tif d == nil then\r\n"
    "\t\tfor _, c in yerel_G.ipairs({2, 1, 3, 5}) do\r\n"
    "\t\t\tlocal bilgi = p:luaGetSkillByClass(c)\r\n"
    "\t\t\tif bilgi ~= nil then d = p:luaFindSkillData(bilgi.skillId) end\r\n"
    "\t\t\tif d ~= nil then break end\r\n"
    "\t\tend\r\n"
    "\tend\r\n"
    "\treturn d\r\n"
    "end\r\n"
)
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
    metin = metin.replace("player:luaFindSkillData(", "yerel_bul(player, ")
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
                veri = xor(xor(veri) + (CONF_EK + conf_yamala.buff_lua_eki()).encode("utf-8"))
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
