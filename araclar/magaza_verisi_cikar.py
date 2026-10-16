"""Mağaza (Store/çekiliş, VIP, kara borsa, banka, sınırlı satış, takas) verisini çıkarır -> sunucu/veri/magaza_verisi.json

Kaynak: tabloların önceden çıkarılmış JSON dosyalarının bulunduğu klasör (dosya adı = tablo adı,
içerik {"data": [...]}), örn. çalışma alanındaki cj/ klasörü.

Kullanım: python magaza_verisi_cikar.py <tablo klasörü> [cikis.json]

Çıktı sunucu/magaza.py tarafından okunur; alan açıklamaları orada.
"""
import json
import os
import sys

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VARSAYILAN_CIKIS = os.path.join(KOK, "sunucu", "veri", "magaza_verisi.json")


def oku(klasor, ad):
    yol = os.path.join(klasor, ad)
    if not os.path.exists(yol) and os.path.exists(yol + ".json"):
        yol += ".json"
    if not os.path.exists(yol):
        print("uyari: tablo yok:", ad)
        return []
    with open(yol, "rb") as f:
        veri = json.loads(f.read().decode("utf-8-sig"))
    return veri["data"] if isinstance(veri, dict) and "data" in veri else veri


def aralik(satirlar):
    """[level_min, level_max, draw_min, draw_max, droplist_id]"""
    return [[r["level_min"], r["level_max"], r["draw_min"], r["draw_max"], r["droplist_id"]] for r in satirlar]


def ust_aralik(satirlar):
    """{index: [[level_min, level_max, draw_min, draw_max, droplist_id], ...]}"""
    sonuc = {}
    for r in satirlar:
        sonuc.setdefault(r["index"], []).append(
            [r["level_min"], r["level_max"], r["draw_min"], r["draw_max"], r["droplist_id"]])
    return sonuc


def derle(k):
    t = lambda ad: oku(k, ad)  # noqa: E731
    ayar = (t("data_store_draw") or [{}])[0]
    sinir = (t("data_store_draw_limit") or [{}])[0]

    havuz = {}
    for r in t("data_store_draw_player"):
        havuz.setdefault(r["star"], []).append(r["player_id"])
    sureli_havuz = {}
    for r in t("data_store_draw_time_player_player"):
        sureli_havuz.setdefault(r["star"], []).append(r["player_id"])

    cekilis = {
        "ayar": ayar,
        "sinir": sinir,
        "oyuncu": {
            "havuz": havuz,
            "dugum": [[r["count"], r["star"], r["chip"]] for r in t("data_store_draw_node")],
            "rehber": {r["index"]: [r["level"], r["id"]] for r in t("data_store_draw_guide_player")},
            "tek": aralik(t("data_store_draw_droplist_single")),
            "on": ust_aralik(t("data_store_draw_droplist_top")),
        },
        "amigo": {
            "havuz": [r["cheer_id"] for r in t("data_store_draw_cheer")],
            "dugum": [[r["count"], r["index"], r["chip"]] for r in t("data_store_draw_node_cheer")],
            "tek": aralik(t("data_store_draw_droplist_single_cheer")),
            "on": ust_aralik(t("data_store_draw_droplist_top_cheer")),
        },
        "beceri": {
            "tek": aralik(t("data_store_draw_droplist_single_magic")),
            "on": ust_aralik(t("data_store_draw_droplist_top_magic")),
        },
        "yildiz": {
            "tek": aralik(t("data_store_draw_droplist_single_star")),
            "on": ust_aralik(t("data_store_draw_droplist_top_star")),
        },
        "altin": {
            "parca": [[r["player_id"], r["weight"]] for r in t("data_store_draw_gold")],
            "parca_adet": [[r["count_chip"], r["weight"]] for r in t("data_store_draw_chip_weight")],
            "tek": aralik(t("data_store_draw_droplist_single_gold")),
            "on": ust_aralik(t("data_store_draw_droplist_top_gold")),
        },
        "sureli": {
            "havuz": sureli_havuz,
            "dugum": [[r["count"], r["star"], r["chip"]] for r in t("data_store_draw_time_player_node")],
            "tek": aralik(t("data_store_draw_time_player_droplist_single")),
            "sans": [[r["count"], r["weight"]] for r in t("data_store_draw_time_player_weight")],
        },
    }

    vip = [{"level": r["level"], "recharge_gem": r["recharge_gem"], "vip_package": r["vip_package"],
            "vip_package_gem": r["vip_package_gem"]} for r in t("data_vip")]

    banka = {
        "kademe": [[r["min"], r["max"], r["cost"]] for r in t("data_store_exchange")],
        "kritik": [[r["times"], r["weight"]] for r in t("data_store_exchange_critical")],
        "formul": (t("data_store_exchange_formula") or [{}])[0],
    }

    yukleme = [{"index": r["index"], "gem": r["gem"], "gem_ex": r["gem_ex"], "rmb": r["rmb"],
                "droplist_id_ex": r.get("droplist_id_ex", 0)} for r in t("data_store_recharge")]

    kara_borsa = {
        "izgara": {r["shopTab"]: r["num"] for r in t("PlayerShopGridNumConfig")},
        "para": {r["id"]: [r["propId"], r["attachType"]] for r in t("PlayerShopUseCoinType")},
        "esya": {},
        "yenileme": {},
    }
    for r in t("PlayerShopItemConfig"):
        if r.get("valid", 1) != 1:
            continue
        kara_borsa["esya"].setdefault(r["shopTab"], {}).setdefault(r["grid"], []).append(
            [r["itemId"], r["itemCount"], r["costStar"], max(1, r.get("random", 1))])
    for r in t("PlayerShopManualPropertyConfig"):
        kara_borsa["yenileme"].setdefault(r["shopTab"], {})[r["num"]] = r["costCoin"]

    kisitli = {r["index"]: [r["droplist_id"], r["cost_gem"], r["limit"], r["vip_level"], r["day"]]
               for r in t("data_restriction_product")}

    takas = {}
    for r in t("data_exchange_group"):
        takas[r["eid"]] = {"aid": r["aid"], "ecount": r["ecount"], "maliyet": [], "urun": []}
    for r in t("data_exchange_cost"):
        if r["eid"] in takas:
            takas[r["eid"]]["maliyet"].append([r["ctype"], r["item_id"], r["count"]])
    for r in t("data_exchange_product"):
        if r["eid"] in takas:
            takas[r["eid"]]["urun"].append([r["ctype"], r["item_id"], r["count"]])

    resimli = {
        "hedef": {r["index"]: [r["itemId"], r["itemCount"]] for r in t("data_illustratedhandbook_exchange")},
        "maliyet": {},
        "elmas": {r["num"]: r["gem"] for r in t("data_illustratedhandbook_exchange_gem")},
    }
    for r in t("data_illustratedhandbook_exchange_cost"):
        resimli["maliyet"].setdefault(r["index"], []).append([r["itemId"], r["itemCount"]])

    parca = {r["playerId"]: [r["playerPiece"], r["count"]] for r in t("PlayerCompound")}
    amigo_parca = {r["cheerId"]: [r["cheerPiece"], r["num"]] for r in t("CheerLeaderCompound")}

    # gereken düşüş listeleri (mac_verisi.json'daki "dusus" ile aynı biçim)
    gerek = set()
    for tur in cekilis.values():
        if not isinstance(tur, dict):
            continue
        for satir in tur.get("tek", []):
            gerek.add(satir[4])
        for satirlar in tur.get("on", {}).values():
            gerek.update(s[4] for s in satirlar)
    gerek.update(v["vip_package"] for v in vip)
    gerek.update(v[0] for v in kisitli.values())
    gerek.update(y["droplist_id_ex"] for y in yukleme)
    gerek.discard(0)
    dusus = {}
    for d in t("data_droplist"):
        if d["id"] in gerek:
            dusus[d["id"]] = [d["exp"], d["exp_team"], d["gold"], d["gem"], d["star"],
                              d["weight_item_count"], [], [], []]
    for r in t("data_droplist_item"):
        if r["id"] in dusus:
            dusus[r["id"]][6].append([r["item_id"], r["count"]])
    for r in t("data_droplist_item_odds"):
        if r["id"] in dusus:
            dusus[r["id"]][7].append([r["item_id"], r["count"], r["rate"]])
    for r in t("data_droplist_item_weight"):
        if r["id"] in dusus:
            dusus[r["id"]][8].append([r["item_id"], r["count"], r["weight"]])
    eksik = sorted(gerek - set(dusus))
    if eksik:
        print("uyari: %d düşüş listesi tabloda yok: %s" % (len(eksik), eksik[:10]))

    return {"cekilis": cekilis, "vip": vip, "banka": banka, "yukleme": yukleme, "kara_borsa": kara_borsa,
            "kisitli": kisitli, "takas": takas, "resimli": resimli, "parca": parca,
            "amigo_parca": amigo_parca, "dusus": dusus}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    cikis = sys.argv[2] if len(sys.argv) > 2 else VARSAYILAN_CIKIS
    veri = derle(sys.argv[1])
    with open(cikis, "w", encoding="utf-8") as f:
        json.dump(veri, f, ensure_ascii=False, separators=(",", ":"))
    print("yazildi:", cikis, os.path.getsize(cikis), "bayt")
