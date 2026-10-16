"""Oyuncu gelişimi ve takım özellikleri için oyun verisini çıkarır -> sunucu/veri/gelisim_verisi.json

Kaynak mac_verisi_cikar.py ile aynıdır: tabloların JSON dosyalarının bulunduğu klasör (dosya adı = tablo adı)
ya da OBB içindeki assets/Android klasörü (UnityPy gerekir).

Kullanım: python gelisim_verisi_cikar.py <tablo klasörü | assets/Android> <cikis.json>

Çıktı kısa anahtarlıdır; her anahtarın anlamı sunucu/gelisim.py başındaki açıklamada.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mac_verisi_cikar import _coz, paketten_oku  # noqa: E402

TABLOLAR = ["PlayerCompound", "starUpBaseInfo", "StyleSkillBaseInfo", "StyleSkillInfo", "PlayerTrainLevelUp",
            "playerGrowUpCnts", "PlayerDressEquip", "data_item_compound", "item_compound", "equipMaxConfig",
            "equipStrengthInfo", "equipBreakInfo", "equipWakeInfo", "CheerLeaderBaseInfo", "CheerLeaderCompound",
            "CheerLeaderLevelUpLimit", "CheerLeaderLevelUpExp", "CheerLeaderItemList", "PlayerMagicBaseInfo",
            "MagicMaxLvInfo", "MagicBreakInfo", "MagicSkillRandomAndFreshInfo", "TeamLevelUpPrize",
            "data_droplist", "data_droplist_item", "PointConfig", "PointBuyConfig", "ItemBaseInfo"]


def tablolari_oku(kaynak):
    t = {}
    for ad in TABLOLAR:
        for yol in (os.path.join(kaynak, ad), os.path.join(kaynak, ad + ".json")):
            if os.path.exists(yol):
                with open(yol, "rb") as f:
                    t[ad] = _coz(f.read())
                break
    for paket in ("conf_json_qte.assetbundle", "conf_luatab_qte.assetbundle"):
        eksik = set(TABLOLAR) - set(t)
        yol = os.path.join(kaynak, paket)
        if eksik and os.path.exists(yol):
            t.update(paketten_oku(yol, eksik))
    eksik = set(TABLOLAR) - set(t)
    if eksik:
        sys.exit("eksik tablolar: %s" % ", ".join(sorted(eksik)))
    return t


def _bol(metin):
    return [x for x in str(metin).split("#")]


def derle(t):
    esya_var = {i["id"] for i in t["ItemBaseInfo"]}

    # yıldız (break_level) kademeleri: starSec -> [altın, parça]; skillType 3 = top stili becerisi
    yildiz, stil_acilis = {}, {}
    for r in t["starUpBaseInfo"]:
        yildiz.setdefault(r["playerId"], {})[r["starSec"]] = [r["cunsumeCoin"], r["cunsumeNum"]]
        for sid, tur, sev in zip(_bol(r["unlockSkillId"]), _bol(r["skillType"]), _bol(r["initSkillLv"])):
            if sid not in ("", "0") and tur == "3":
                stil_acilis.setdefault(r["playerId"], {})[int(sid)] = r["starSec"]
    stil_var = {}
    for r in t["StyleSkillInfo"]:
        stil_var.setdefault(r["playerId"], set()).add(int(r["skillId"]))
    # yalnızca StyleSkillInfo'da da bulunan stil becerileri (istemci PlayerStyleSkill'i oradan kurar)
    stil = {pid: {s: y for s, y in d.items() if s in stil_var.get(pid, ())} for pid, d in stil_acilis.items()}

    esya_birlesim = {}
    for r in t["data_item_compound"]:
        esya_birlesim.setdefault(r["id"], []).append([r["material"], r["count"]])
    esya_birlesim_altin = {r["id"]: [r["gold"], r["cost_item_id"], r["cost_item_count"]] for r in t["item_compound"]}

    ekipman_sinir = {r["id"]: r["maxLv"] for r in t["equipMaxConfig"]}
    guclendirme = {r["lv"]: [r["gold"], r["itemId"], r["itemNum"], r["needBreakLv"]] for r in t["equipStrengthInfo"]}
    kirilma = {}
    for r in t["equipBreakInfo"]:
        kirilma.setdefault(r["type"], {})[r["breakLv"]] = [r["itemId"], r["itemNum"], r["gold"]]
    uyanis = {}
    for r in t["equipWakeInfo"]:
        uyanis.setdefault(r["equipId"], {})[r["wakeLv"]] = [r["itemId"], r["itemNum"], r["itemId2"], r["itemNum2"],
                                                            r["gold"]]

    amigo_esya = {r["needItemIndex"]: [r["itemId"], r["num"]] for r in t["CheerLeaderItemList"]}
    amigo_sinir = {}
    for r in t["CheerLeaderLevelUpLimit"]:
        amigo_sinir.setdefault(r["id"], []).append([r["limit_lv"], r["need_item"]])

    sihir_tur = {r["magicId"]: r["type"] for r in t["PlayerMagicBaseInfo"]}
    sihir_kirilma = {}
    for r in t["MagicBreakInfo"]:
        sihir_kirilma.setdefault(r["type"], {})[r["level"]] = r["needGold"]
    ozellik_havuzu = {}
    for r in t["MagicSkillRandomAndFreshInfo"]:
        havuz = ozellik_havuzu.setdefault(r["start"], [])
        if r["characterId"] not in havuz:
            havuz.append(r["characterId"])

    # takım seviye ödülü: data_droplist sabit değerleri + kesin eşyalar
    odul_dusus = {r["level"]: r["dropId"] for r in t["TeamLevelUpPrize"]}
    dususler = {}
    for d in t["data_droplist"]:
        if d["id"] in odul_dusus.values():
            dususler[d["id"]] = [d["gold"], d["gem"], d["star"], []]
    for r in t["data_droplist_item"]:
        if r["id"] in dususler and r["item_id"] in esya_var:
            dususler[r["id"]][3].append([r["item_id"], r["count"]])
    takim_odul = {sv: dususler[d] for sv, d in odul_dusus.items() if d in dususler}

    return {
        "parca": {r["playerId"]: [r["playerPiece"], r["count"]] for r in t["PlayerCompound"]},
        "yildiz": yildiz,
        "stil": stil,
        "stil_bedel": {r["skillLv"]: [r["cunsumeGold"], r["cunsumePoint"]] for r in t["StyleSkillBaseInfo"]},
        "puan": {r["id"]: r["value"] for r in t["PointConfig"]},
        "puan_satin": {r["buyCnts"]: r["cunsumeGem"] for r in t["PointBuyConfig"]},
        "antrenman": {r["level"]: [r["needGold"], r["itemId"], r["itemCount"]] for r in t["PlayerTrainLevelUp"]},
        "buyume": {r["growUpCnts"]: r["nextNodelevel"] for r in t["playerGrowUpCnts"]},
        "giysi": {"%d_%d" % (r["playerId"], r["playerColor"]): [r["dressIndex%d" % i] for i in range(1, 7)]
                  for r in t["PlayerDressEquip"]},
        "esya_birlesim": esya_birlesim,
        "esya_birlesim_bedel": esya_birlesim_altin,
        "ekipman_sinir": {"guc": ekipman_sinir.get(1, 100), "kirilma": ekipman_sinir.get(2, 19) - 1,
                          "uyanis": ekipman_sinir.get(3, 5)},
        "guclendirme": guclendirme,
        "kirilma": kirilma,
        "uyanis": uyanis,
        "amigo_tur": {r["cheerId"]: r["type"] for r in t["CheerLeaderBaseInfo"]},
        "amigo_parca": {r["cheerId"]: [r["cheerPiece"], r["num"]] for r in t["CheerLeaderCompound"]},
        "amigo_sinir": amigo_sinir,
        "amigo_esya": amigo_esya,
        "amigo_exp": {r["level"]: r["exp"] for r in t["CheerLeaderLevelUpExp"]},
        "sihir_tur": sihir_tur,
        "sihir_max": {r["type"]: r["maxLv"] for r in t["MagicMaxLvInfo"]},
        "sihir_kirilma": sihir_kirilma,
        "ozellik_havuzu": ozellik_havuzu,
        "takim_odul": takim_odul,
    }


if __name__ == "__main__":
    veri = derle(tablolari_oku(sys.argv[1]))
    with open(sys.argv[2], "w", encoding="utf-8") as f:
        json.dump(veri, f, ensure_ascii=False, separators=(",", ":"))
    print("yazildi:", sys.argv[2], os.path.getsize(sys.argv[2]), "bayt")
