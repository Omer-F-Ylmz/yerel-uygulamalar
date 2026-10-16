"""Diğer oyun modları (sunucu/modlar.py) için oyun verisini çıkarır -> sunucu/veri/modlar_verisi.json

Kaynak mac_verisi_cikar.py ile aynıdır: tabloların JSON dosyalarının bulunduğu klasör (dosya adı = tablo adı)
ya da OBB içindeki assets/Android klasörü (UnityPy gerekir).

Kullanım: python modlar_verisi_cikar.py <tablo klasörü | assets/Android> <cikis.json>

Çıktı kısa anahtarlıdır; her anahtarın anlamı sunucu/modlar.py başındaki açıklamada.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mac_verisi_cikar import DUSMAN, _coz, paketten_oku, sayi  # noqa: E402

TABLOLAR = ["data_battle", "data_droplist", "data_droplist_item", "data_droplist_item_odds",
            "data_droplist_item_weight", "ItemBaseInfo", "SkillInfo", "data_enemy", "data_enemy_skill",
            "data_trial_config", "data_trial_base", "data_trial_court", "data_trial_street", "data_trial_allstar",
            "data_trial_droplist", "data_league_stage", "data_league_battle",
            "rm_battle_data", "rm_item_data", "rm_map", "rm_settlement", "rm_history_award", "rm_action",
            "rm_config", "rm_difficulty",
            "data_wanted_config", "data_wanted_bounty", "data_ladder_config", "data_ladder_task",
            "data_master_match_rule", "data_master_match_combo", "data_master_match_task",
            "data_master_match_config", "masterMatchBaseDataInfo",
            "data_open_match_node", "data_open_match_battle", "data_open_match_chest", "data_open_match_task",
            "data_open_match_support_pool", "data_open_match_support_param",
            "data_arena_config", "data_arena_player", "data_arena_chest",
            "FightingRankRewards", "LevelRankRewards", "CostRankRewards"]
DENEME_TABLOLARI = ["data_trial_base", "data_trial_court", "data_trial_street", "data_trial_allstar"]


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


def derle(t):
    esya_var = {i["id"] for i in t["ItemBaseInfo"]}
    beceri_var = {s["skillId"] for s in t["SkillInfo"]}
    savas = {b["id"]: b for b in t["data_battle"]}
    dusus_gerek = set()

    # ------------------------------------------------ Deneme (Trial, 10/10xx)
    deneme = {"ayar": [], "seviye": {}, "dusus": {}}
    for c in t["data_trial_config"]:
        deneme["ayar"].append([c["trial_type"], c["limit"]])
    for tur, ad in enumerate(DENEME_TABLOLARI, 1):
        deneme["seviye"][tur] = [[r["level"], r["battle_id"], r["player_level"]] for r in t[ad]]
    for r in t["data_trial_droplist"]:
        deneme["dusus"].setdefault(r["battle_id"], {})[r["win"]] = r["droplist_id"]
        dusus_gerek.add(r["droplist_id"])

    # ------------------------------------------------ Lig / parça bölümleri (47/47xx)
    lig = []
    for s in t["data_league_stage"]:
        maclar = [[b["battle_index"], b["battle_id"], b["battle_times"]] for b in t["data_league_battle"]
                  if b["stage_id"] == s["stage_id"]]
        lig.append([s["stage_id"], maclar])
        for _, bid, _ in maclar:
            if bid in savas:
                dusus_gerek.add(savas[bid]["droplist_id"])

    # ------------------------------------------------ Sokak macerası (14/14xx, /op_rewardmatch)
    rm = {
        "savas": [[r["id"], r["battle_id"], r["fee"], r["type"], savas.get(r["battle_id"], {}).get("advise_teamPower", 0)]
                  for r in t["rm_battle_data"] if r["battle_id"] in savas],
        "esya": [[r["id"], r["itemid"], r["itemcount"], r["cost"], r["teamlevel_min"], r["teamlevel_max"], r["weight"]]
                 for r in t["rm_item_data"] if r["itemid"] in esya_var],
        "harita": {r["index"]: r["type"] for r in t["rm_map"]},
        "hesap": [[r["fee_min"], r["fee_max"], r["droplist"]] for r in t["rm_settlement"]],
        "gecmis": [[r["id"], r["streetBallCoin"], r["dropListId"]] for r in t["rm_history_award"]],
        "aksiyon": max(r["point"] for r in t["rm_action"]),
        "zorluk": [r["id"] for r in t["rm_difficulty"]],
        "bilet": t["rm_config"][0]["item_id_ticket"],
    }
    for r in rm["savas"]:
        dusus_gerek.add(savas[r[1]]["droplist_id"])
    dusus_gerek |= {r[2] for r in rm["hesap"]} | {r[2] for r in rm["gecmis"]}

    # ------------------------------------------------ Aranan (24), sıralama (21), usta (52)
    aranan = {"gunluk": t["data_wanted_config"][0]["daily_count"],
              "odul": [[r["str_min"], r["str_max"], r["bounty"]] for r in t["data_wanted_bounty"]]}
    lc = t["data_ladder_config"][0]
    merdiven = {"gorev": [[r["id"], r["progress"], r["dropListId"]] for r in t["data_ladder_task"]],
                "ucretsiz": lc["count_free"], "tesvik": lc["encourage_gold"]}
    dusus_gerek |= {r[2] for r in merdiven["gorev"]}
    usta = {"kural": [[r["score"], r["min"], r["max"]] for r in t["data_master_match_rule"]],
            "seri": {r["combo"]: r["score"] for r in t["data_master_match_combo"]},
            "gorev": [[r["id"], r["progress"], r["dropListId"]] for r in t["data_master_match_task"]],
            "kayip": t["data_master_match_config"][0]["lose_score"],
            "sahne": [r["id"] for r in t["masterMatchBaseDataInfo"]]}
    dusus_gerek |= {r[2] for r in usta["gorev"]}

    # ------------------------------------------------ Açık turnuva (2059)
    acik = {"dugum": [[r["index"], r["ntype"], r["nid"]] for r in t["data_open_match_node"]],
            "savas": {r["nid"]: [r["fan_low"], r["shot_low"], r["fan_mid"], r["shot_mid"], r["fan_high"],
                                 r["shot_high"], r["param_min_low"], r["param_max_low"], r["param_min_mid"],
                                 r["param_max_mid"], r["param_min_high"], r["param_max_high"]]
                      for r in t["data_open_match_battle"]},
            "sandik": [[r["nid"], r["level_min"], r["level_max"], r["droplist"], r["droplist_ex"]]
                       for r in t["data_open_match_chest"]],
            "gorev": [[r["id"], r["progress"], r["dropListId"]] for r in t["data_open_match_task"]],
            "destek": {}, "destek_deger": {}}
    for r in t["data_open_match_support_pool"]:
        acik["destek"].setdefault(r["nid"], []).append([r["level"], r["eid"], r["weight"]])
    for r in t["data_open_match_support_param"]:
        acik["destek_deger"]["%d_%d" % (r["eid"], r["level"])] = [r["param_min"], r["param_max"]]
    for r in acik["sandik"]:
        dusus_gerek |= {r[3], r[4]}
    dusus_gerek |= {r[2] for r in acik["gorev"]}

    # ------------------------------------------------ Arena (32)
    ac = t["data_arena_config"][0]
    arena = {"oyuncu": [r["enemy"] for r in t["data_arena_player"]],
             "sandik": {r["win"]: r["droplist"] for r in t["data_arena_chest"]},
             "max_win": ac["max_win"], "max_lose": ac["max_lose"]}
    dusus_gerek |= set(arena["sandik"].values())
    dusman_gerek = set(arena["oyuncu"])
    dusman_beceri = {}
    for s in t["data_enemy_skill"]:
        if s["id"] in dusman_gerek and s["skillId"] in beceri_var:
            liste = dusman_beceri.setdefault(s["id"], [])
            if all(x[0] != s["skillId"] for x in liste):
                liste.append([s["skillId"], s["skillLv"]])
    dusman = {e["id"]: [e["playerid"], e["level"], [sayi(e[k]) for k in DUSMAN], e["Energy"],
                        e["EnergyRecoverSpeed"], dusman_beceri.get(e["id"], [])]
              for e in t["data_enemy"] if e["id"] in dusman_gerek}

    # ------------------------------------------------ Etkinlik sıralaması ödülleri (40/400x): 1 seviye, 2 güç, 3 harcama
    sira_odul = {1: [[r["rank_min"], r["rank_max"], r["itemId"], r["num"]] for r in t["LevelRankRewards"]],
                 2: [[r["rank_min"], r["rank_max"], r["itemId"], r["num"]] for r in t["FightingRankRewards"]],
                 3: [[r["rank_min"], r["rank_max"], r["itemId"], r["num"]] for r in t["CostRankRewards"]]}

    # ------------------------------------------------ düşüş listeleri
    dusus_gerek.discard(0)
    dususler = {}
    for d in t["data_droplist"]:
        if d["id"] in dusus_gerek:
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

    return {"deneme": deneme, "lig": lig, "rm": rm, "aranan": aranan, "merdiven": merdiven, "usta": usta,
            "acik": acik, "arena": arena, "sira_odul": sira_odul, "dusman": dusman, "dusus": dususler}


if __name__ == "__main__":
    veri = derle(tablolari_oku(sys.argv[1]))
    with open(sys.argv[2], "w", encoding="utf-8") as f:
        json.dump(veri, f, ensure_ascii=False, separators=(",", ":"))
    print("yazildi:", sys.argv[2], os.path.getsize(sys.argv[2]), "bayt")
