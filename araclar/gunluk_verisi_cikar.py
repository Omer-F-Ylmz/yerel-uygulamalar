"""Günlük/meta özellikler (sunucu/gunluk.py) için oyun verisini çıkarır -> sunucu/veri/gunluk_verisi.json

Kaynak: tabloların JSON dosyalarının bulunduğu klasör (dosya adı = tablo adı) ya da OBB'nin assets/Android
klasörü (conf_json_qte / conf_luatab_qte paketleri, UnityPy gerekir).

Kullanım: python gunluk_verisi_cikar.py <tablo klasörü | assets/Android> <cikis.json>

Bazı tablolarda baştaki sıfırlı sayılar var (MissionBaseInfo "urlParam":[0,03]); okuyucu bunları düzeltir.
"""
import json
import os
import re
import sys

TABLOLAR = ["PlayerMonthCheckInConfig", "PlayerMonthCheckInPrize", "PlayerSevenCheckInConfig",
            "PlayerOnlinePackageConfig", "StrengthConfig", "MissionBaseInfo", "ActivityTwoWeekMission",
            "ActivityTwoWeekRewardInfo", "ActivityBaseInfo", "RechargeActivity0Info", "RechargeActivity1Info",
            "data_recharge", "data_rechargeInfo", "data_store_recharge", "SuperConfig", "ItemBaseInfo",
            "data_droplist", "data_droplist_item", "data_droplist_item_odds", "data_droplist_item_weight"]

# trailer_info (yalnızca istemcinin LuaTab paketinde): tür -> (oy, kazanan, kaybeden) düşüş listesi
FRAGMAN = {1: [149011, 149012, 149013], 2: [149021, 149022, 149023]}
GUNLUK_GOREV_TURLERI = (1, 5)  # EnumTaskType_0.DailyTask / SpecialTask: her gün sıfırlanır


def _coz(ham):
    if isinstance(ham, bytes):
        ham = ham.decode("utf-8-sig", "replace")
    try:
        veri = json.loads(ham)
    except ValueError:
        veri = json.loads(re.sub(r"([\[,:])(\s*)0+(\d)", r"\1\2\3", ham))
    return veri["data"] if isinstance(veri, dict) and "data" in veri else veri


def tablolari_oku(kaynak):
    t = {}
    for ad in TABLOLAR:
        for yol in (os.path.join(kaynak, ad), os.path.join(kaynak, ad + ".json")):
            if os.path.exists(yol):
                with open(yol, "rb") as f:
                    t[ad] = _coz(f.read())
                break
    eksik = set(TABLOLAR) - set(t)
    for paket in ("conf_json_qte.assetbundle", "conf_luatab_qte.assetbundle"):
        yol = os.path.join(kaynak, paket)
        if eksik and os.path.exists(yol):
            import UnityPy
            for nesne in UnityPy.load(yol).objects:
                if nesne.type.name != "TextAsset":
                    continue
                varlik = nesne.read()
                ad = getattr(varlik, "m_Name", None) or varlik.name
                if ad in eksik:
                    ham = varlik.m_Script if hasattr(varlik, "m_Script") else varlik.script
                    try:
                        t[ad] = _coz(ham.encode("utf-8", "surrogateescape") if isinstance(ham, str) else ham)
                        eksik.discard(ad)
                    except ValueError:
                        continue
    if eksik:
        sys.exit("eksik tablolar: %s" % ", ".join(sorted(eksik)))
    return t


def derle(t):
    esya_var = {i["id"] for i in t["ItemBaseInfo"]}
    gorevler = {}
    for m in t["MissionBaseInfo"]:
        gorevler[m["id"]] = [m["missionType"], m["condition1"], m["rewardId"]]
    iki_hafta = sorted({r["missionId"] for r in t["ActivityTwoWeekMission"] if r["missionId"] in gorevler})
    odul_bilgi = t["ActivityTwoWeekRewardInfo"][0]

    # Window_WonderfulActiveTask etkinlikleri: görevleri olanlardan her addan ilki (aynı adlı sezonluk kopyalar elenir)
    tur_var = {v[0] for v in gorevler.values()}
    harika, adlar = [], set()
    for a in t["ActivityBaseInfo"]:
        if a["prefabName"] == "Window_WonderfulActiveTask" and a["id"] in tur_var and a["name"] not in adlar:
            adlar.add(a["name"])
            harika.append(a["id"])

    sarj0 = [[r["actId"], r["id"], r["dropId"]] for r in t["RechargeActivity0Info"]]
    sarj1 = [[r["id"], r["rechargeCount"], r["dropId"]] for r in t["RechargeActivity1Info"]]
    super_ayar = {}
    for s in t["SuperConfig"]:
        super_ayar.setdefault(str(s["id"]), s["param1"])

    # ürünler: productId -> [tür, değer]; tür 0 = düşüş listesi, 1 = elmas (gem + gem_ex)
    urunler = {}
    magaza = {r["index"]: r for r in t["data_store_recharge"]}
    paket = {r["id"]: r for r in t["data_recharge"]}
    for r in t["data_store_recharge"]:
        for k in ("productId", "productId_3"):
            if r.get(k):
                urunler[r[k]] = [1, r["gem"] + r["gem_ex"]]
    for r in t["data_recharge"]:
        for k in ("productId", "productId_3"):
            if r.get(k) and r[k] not in urunler:
                urunler[r[k]] = [0, r["droplist"]]
    for r in t["data_rechargeInfo"]:
        if r["productType"] == 1 and r["foreign_key"] in magaza:
            m = magaza[r["foreign_key"]]
            urunler[r["productId"]] = [1, m["gem"] + m["gem_ex"]]
        elif r["productType"] == 0 and r["foreign_key"] in paket:
            urunler[r["productId"]] = [0, paket[r["foreign_key"]]["droplist"]]

    aylik = [[r["checkInCnt"], r["dropListsId"]] for r in t["PlayerMonthCheckInConfig"]]
    aylik_odul = [[r["checkCnts"], r["dropListsId"]] for r in t["PlayerMonthCheckInPrize"]]
    yedi = [[r["day"], r["dropListsId"]] for r in t["PlayerSevenCheckInConfig"]]
    cevrimici = [[r["index"], r["onlineTime"], r["dropListsId"]] for r in t["PlayerOnlinePackageConfig"]]

    gerek = {d for _, d in aylik} | {d for _, d in aylik_odul} | {d for _, d in yedi}
    gerek |= {d for _, _, d in cevrimici} | {v[2] for v in gorevler.values()}
    gerek |= {d for _, _, d in sarj0} | {d for _, _, d in sarj1} | {odul_bilgi["dropId"]}
    gerek |= {v for tur, v in urunler.values() if tur == 0}
    gerek |= {int(super_ayar.get("8", 0))} | {d for l in FRAGMAN.values() for d in l}
    gerek.discard(0)
    dususler = {}
    for d in t["data_droplist"]:
        if d["id"] in gerek:
            dususler[d["id"]] = [d["exp"], d["exp_team"], d["gold"], d["gem"], d["star"],
                                 d["weight_item_count"], [], [], []]
    for r in t["data_droplist_item"]:
        if r["id"] in dususler and r["item_id"] in esya_var:
            dususler[r["id"]][6].append([r["item_id"], r["count"]])
    for r in t["data_droplist_item_odds"]:
        if r["id"] in dususler and r["item_id"] in esya_var:
            dususler[r["id"]][7].append([r["item_id"], r["count"], r["rate"]])
    for r in t["data_droplist_item_weight"]:
        if r["id"] in dususler and r["item_id"] in esya_var:
            dususler[r["id"]][8].append([r["item_id"], r["count"], r["weight"]])

    return {
        "aylik": aylik,
        "aylik_odul": aylik_odul,
        "yedi": yedi,
        "cevrimici": cevrimici,
        "enerji": {str(r["id"]): r["value"] for r in t["StrengthConfig"]},
        "gorev": {str(k): v for k, v in gorevler.items()},
        "gunluk_gorev_turleri": list(GUNLUK_GOREV_TURLERI),
        "iki_hafta": iki_hafta,
        "iki_hafta_odul": [odul_bilgi["dropId"], odul_bilgi["rewardId"], odul_bilgi["chipLimit"]],
        "harika": harika,
        "sarj0": sarj0,
        "sarj1": sarj1,
        "super": super_ayar,
        "urun": urunler,
        "fragman": {str(k): v for k, v in FRAGMAN.items()},
        "dusus": {str(k): v for k, v in dususler.items()},
    }


if __name__ == "__main__":
    veri = derle(tablolari_oku(sys.argv[1]))
    with open(sys.argv[2], "w", encoding="utf-8") as f:
        json.dump(veri, f, ensure_ascii=False, separators=(",", ":"))
    print("yazildi:", sys.argv[2], os.path.getsize(sys.argv[2]), "bayt; harika etkinlikler:", len(veri["harika"]))
