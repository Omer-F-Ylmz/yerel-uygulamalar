"""Maç (PvE savaş) için sunucunun ihtiyaç duyduğu oyun verisini çıkarır -> sunucu/veri/mac_verisi.json

Kaynak iki türlü olabilir:
  - OBB içindeki assets/Android klasörü (conf_json_qte / conf_luatab_qte paketleri, UnityPy gerekir)
  - Tabloların önceden çıkarılmış JSON dosyalarının bulunduğu klasör (dosya adı = tablo adı)

Kullanım: python mac_verisi_cikar.py <assets/Android | tablo klasörü> <cikis.json>

Çıktı kısa anahtarlıdır; açıklamalar sunucu/mac.py içindeki VERI okuyucusundadır.
"""
import json
import os
import sys

TABLOLAR = ["PlayerBaseInfo", "PlayerGrowUpValue", "PlayerStarUpValue", "PlayerDressEquip", "item_compound",
            "playerGrowUpCnts", "PlayerSkillInfo", "starUpBaseInfo", "SkillInfo", "CheerLeaderLevelUp",
            "CheerLeaderLevelUpLimit", "data_battle", "data_team", "data_enemy", "data_enemy_skill",
            "data_droplist", "data_droplist_item", "data_droplist_item_odds", "data_droplist_item_weight",
            "data_elite_stage", "data_elite_stage_chests", "data_elite_stage_battle_chests",
            "data_elite_sweep_droplist", "data_story_stage", "PlayerExperienceInfo", "TeamExperience",
            "ItemBaseInfo", "data_item_usage"]

# Oyuncu nitelikleri, PlayerAttributeLua.lua'daki sırayla (attrFind dizisi)
NITELIK = ["morale", "attackMorale", "defendMorale", "shot", "dribble", "rebound", "block", "defend",
           "noBallAbility", "crossOver"]
BUYUME = [n + "GrowUp" for n in NITELIK]
GIYSI = [n + "Basic" for n in NITELIK]
DUSMAN = ["MoraleBasic", "AttackMoraleBasic", "DefendMoraleBasic", "ShotBasic", "DribbleBasic", "ReboundBasic",
          "BlockBasic", "DefendBasic", "NoBallAbilityBasic", "CrossOverBasic"]


def _coz(ham):
    if isinstance(ham, str):
        ham = ham.encode("utf-8", "surrogateescape")
    veri = json.loads(ham.decode("utf-8-sig"))
    return veri["data"] if isinstance(veri, dict) and "data" in veri else veri


def klasorden_oku(klasor):
    t = {}
    for ad in TABLOLAR:
        yol = os.path.join(klasor, ad)
        if not os.path.exists(yol) and os.path.exists(yol + ".json"):
            yol += ".json"
        if os.path.exists(yol):
            with open(yol, "rb") as f:
                t[ad] = _coz(f.read())
    return t


def paketten_oku(paket_yolu, istenen):
    import UnityPy
    t = {}
    for nesne in UnityPy.load(paket_yolu).objects:
        if nesne.type.name != "TextAsset":
            continue
        varlik = nesne.read()
        ad = getattr(varlik, "m_Name", None) or varlik.name
        if ad not in istenen or ad in t:
            continue
        ham = varlik.m_Script if hasattr(varlik, "m_Script") else varlik.script
        try:
            t[ad] = _coz(ham)
        except ValueError:
            continue
    return t


def tablolari_oku(kaynak):
    t = klasorden_oku(kaynak)
    for paket in ("conf_json_qte.assetbundle", "conf_luatab_qte.assetbundle"):
        eksik = set(TABLOLAR) - set(t)
        yol = os.path.join(kaynak, paket)
        if eksik and os.path.exists(yol):
            t.update(paketten_oku(yol, eksik))
    eksik = set(TABLOLAR) - set(t)
    if eksik:
        sys.exit("eksik tablolar: %s" % ", ".join(sorted(eksik)))
    return t


def sayi(x):
    """3.0 -> 3; JSON'u küçük tutar."""
    if isinstance(x, float) and x.is_integer():
        return int(x)
    return x


def derle(t):
    beceri_var = {s["skillId"] for s in t["SkillInfo"]}
    esya_var = {i["id"] for i in t["ItemBaseInfo"]}

    # ------------------------------------------------ oyuncular
    oyuncular = {}
    giysi_esya = {c["id"]: [sayi(c[k]) for k in GIYSI] for c in t["item_compound"]}
    for p in t["PlayerBaseInfo"]:
        if p.get("isMonster") != 0:
            continue
        oyuncular[p["playerId"]] = {"b": {}, "y": {}, "g": {}, "s": [], "e": [p["entranceEnergy"], p["energyRecoverSpeed"]]}
    for r in t["PlayerGrowUpValue"]:
        if r["playerId"] in oyuncular:
            oyuncular[r["playerId"]]["b"][r["playerStar"]] = [sayi(r[k]) for k in BUYUME]
    for r in t["PlayerStarUpValue"]:
        if r["playerId"] in oyuncular:
            oyuncular[r["playerId"]]["y"][r["playerStar"]] = [sayi(r[k]) for k in NITELIK]
    # PlayerDressEquip: oyuncunun renk (kalite) satırları; PlayerAttributeLua her satırın 6 giysisini *1.5 ekler
    for r in t["PlayerDressEquip"]:
        if r["playerId"] in oyuncular:
            top = [0] * 10
            for i in range(1, 7):
                for j, v in enumerate(giysi_esya.get(r["dressIndex%d" % i], [0] * 10)):
                    top[j] += v
            oyuncular[r["playerId"]]["g"][r["playerColor"]] = top
    # Savaş becerileri: yıldız atlamada açılan tür 1 (aktif/pasif) ve tür 3 (6xxxx) beceriler. Tür 2 SkillInfo'da yok.
    for r in t["starUpBaseInfo"]:
        if r["playerId"] not in oyuncular:
            continue
        for sid, tur, sev in zip(str(r["unlockSkillId"]).split("#"), str(r["skillType"]).split("#"),
                                 str(r["initSkillLv"]).split("#")):
            if sid in ("", "0") or tur not in ("1", "3") or int(sid) not in beceri_var:
                continue
            oyuncular[r["playerId"]]["s"].append([r["starSec"], int(sid), int(sev or 1)])
    for p in t["PlayerSkillInfo"]:
        o = oyuncular.get(p["playerId"])
        if o is not None and p["skillId"] in beceri_var and all(s[1] != p["skillId"] for s in o["s"]):
            o["s"].append([0, p["skillId"], 1])
    for o in oyuncular.values():
        for k in ("b", "y", "g"):
            o[k] = [o[k][i] for i in sorted(o[k])]

    # ------------------------------------------------ amigolar (CheerLeaderLevelUp: seviye başına nitelik)
    amigolar = {}
    for r in t["CheerLeaderLevelUp"]:
        amigolar.setdefault(r["cheerId"], {"s": {}, "l": []})["s"][r["level"]] = [sayi(r[k]) for k in NITELIK]
    for r in t["CheerLeaderLevelUpLimit"]:
        if r["id"] in amigolar:
            amigolar[r["id"]]["l"].append([r["limit_lv"], r["attribute_plus"]])
    for a in amigolar.values():
        a["s"] = [a["s"][i] for i in sorted(a["s"])]

    # ------------------------------------------------ maçlar, takımlar, rakipler
    maclar = {}
    takim_gerek = set()
    for b in t["data_battle"]:
        takimlar = [int(x) for x in str(b["team_list"]).split("#") if x not in ("", "0")] or [b["team_id"]]
        maclar[b["id"]] = [b["battle_type"], b["scene"], b["droplist_id"], takimlar, b["name"]]
        takim_gerek.update(takimlar)
    takimlar = {}
    dusman_gerek = set()
    for tm in t["data_team"]:
        if tm["id"] in takim_gerek:
            takimlar[tm["id"]] = [tm["player1"], tm["player2"], tm["player3"]]
            dusman_gerek.update(takimlar[tm["id"]])
    dusman_beceri = {}
    for s in t["data_enemy_skill"]:
        if s["id"] in dusman_gerek and s["skillId"] in beceri_var:
            liste = dusman_beceri.setdefault(s["id"], [])
            if all(x[0] != s["skillId"] for x in liste):
                liste.append([s["skillId"], s["skillLv"]])
    dusmanlar = {}
    for e in t["data_enemy"]:
        if e["id"] in dusman_gerek:
            dusmanlar[e["id"]] = [e["playerid"], e["level"], [sayi(e[k]) for k in DUSMAN],
                                  e["Energy"], e["EnergyRecoverSpeed"], dusman_beceri.get(e["id"], [])]

    # ------------------------------------------------ elite / hikaye
    elite_mac_sandik = {c["battle_id"]: c["droplist_id"] for c in t["data_elite_stage_battle_chests"]}
    elite_yildiz_sandik = {}
    for c in t["data_elite_stage_chests"]:
        elite_yildiz_sandik.setdefault(c["id"], {})[c["star_count"]] = c["droplist_id"]
    elite_supurme = {c["battle_id"]: c["droplist_id"] for c in t["data_elite_sweep_droplist"]}
    hikaye = {s["id"]: [int(x) for x in str(s["battle"]).split("#") if x] for s in t["data_story_stage"]}

    # ------------------------------------------------ düşüş listeleri (yalnızca kullanılanlar)
    dusus_gerek = {m[2] for m in maclar.values() if m[0] in (2, 6)}
    dusus_gerek |= set(elite_mac_sandik.values()) | set(elite_supurme.values())
    for s in elite_yildiz_sandik.values():
        dusus_gerek |= set(s.values())
    kullanim = {u["id"]: [u["use_type"], u["param"]] for u in t["data_item_usage"]}
    dusus_gerek |= {p for tur, p in kullanim.values() if tur == 1}
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

    return {
        "oyuncu": oyuncular,
        "egitim_dugum": {r["growUpCnts"]: r["lastnodelevel"] for r in t["playerGrowUpCnts"]},
        "amigo": amigolar,
        "mac": maclar,
        "takim": takimlar,
        "dusman": dusmanlar,
        "dusus": dususler,
        "elite_mac_sandik": elite_mac_sandik,
        "elite_yildiz_sandik": elite_yildiz_sandik,
        "elite_supurme": elite_supurme,
        "hikaye": hikaye,
        "oyuncu_exp": {r["level"]: r["experience"] for r in t["PlayerExperienceInfo"]},
        "takim_exp": {r["level"]: r["exp"] for r in t["TeamExperience"]},
        "esya_kullanim": kullanim,
        "esya_fiyat": {i["id"]: i.get("price", 0) for i in t["ItemBaseInfo"]},
    }


if __name__ == "__main__":
    veri = derle(tablolari_oku(sys.argv[1]))
    with open(sys.argv[2], "w", encoding="utf-8") as f:
        json.dump(veri, f, ensure_ascii=False, separators=(",", ":"))
    print("yazildi:", sys.argv[2], os.path.getsize(sys.argv[2]), "bayt")
