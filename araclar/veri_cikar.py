"""OBB'deki conf_luatab_qte.assetbundle'dan sunucunun kullandığı oyun verisini çıkarır.

Gerekenler: pip install UnityPy
Kullanım: python veri_cikar.py <obb icindeki assets/Android klasoru> <cikis.json>
"""
import json
import os
import sys

import UnityPy

TABLOLAR = ["PlayerBaseInfo", "PlayerSkillInfo", "starUpBaseInfo", "ItemBaseInfo",
            "CheerLeaderBaseInfo", "TeamExperience", "PlayerExperienceInfo", "SkillUpLevel",
            "data_elite_stage", "data_elite_stage_chests"]


def tablolari_oku(paket_yolu):
    tablolar = {}
    for nesne in UnityPy.load(paket_yolu).objects:
        if nesne.type.name != "TextAsset":
            continue
        varlik = nesne.read()
        ad = getattr(varlik, "m_Name", None) or varlik.name
        if ad not in TABLOLAR:
            continue
        ham = varlik.m_Script if hasattr(varlik, "m_Script") else varlik.script
        if isinstance(ham, str):
            ham = ham.encode("utf-8", "surrogateescape")
        veri = json.loads(ham.decode("utf-8-sig"))
        tablolar[ad] = veri["data"] if isinstance(veri, dict) and "data" in veri else veri
    return tablolar


def derle(t):
    beceriler = {}
    for s in t["PlayerSkillInfo"]:
        beceriler.setdefault(s["playerId"], []).append(s["skillId"])
    diger = {}
    for y in t["starUpBaseInfo"]:
        idler = str(y["unlockSkillId"]).split("#")
        turler = str(y["skillType"]).split("#")
        seviyeler = str(y["initSkillLv"]).split("#")
        for sid, tur, sev in zip(idler, turler, seviyeler):
            if sid not in ("", "0") and tur == "2":
                diger.setdefault(y["playerId"], {})[int(sid)] = int(sev or 1)
    oyuncular = []
    for p in t["PlayerBaseInfo"]:
        if p.get("isMonster") != 0:
            continue
        pid = p["playerId"]
        oyuncular.append({
            "id": pid,
            "ad": p["name"],
            "pozisyon": p["position"],
            "beceriler": beceriler.get(pid, []),
            "diger_beceriler": [{"skill_id": k, "skill_level": v} for k, v in sorted(diger.get(pid, {}).items())],
        })
    esyalar = [{"id": i["id"], "ad": i["name"], "tur": i["itemType"], "cantada": i.get("isShowInBag", 1)}
               for i in t["ItemBaseInfo"]]
    sandiklar = {}
    for c in t["data_elite_stage_chests"]:
        sandiklar.setdefault(c["id"], []).append(c["star_count"])
    elite = [{"id": e["id"], "ad": e["name"], "maclar": e["battle"], "sandiklar": sorted(sandiklar.get(e["id"], []))}
             for e in t["data_elite_stage"]]
    return {
        "oyuncular": oyuncular,
        "elite": elite,
        "esyalar": esyalar,
        "amigolar": [c["cheerId"] for c in t["CheerLeaderBaseInfo"]],
        "sinirlar": {
            "takim_seviye": max(x["level"] for x in t["TeamExperience"]),
            "oyuncu_seviye": max(x["level"] for x in t["PlayerExperienceInfo"]),
            "yildiz": max(x["starSec"] for x in t["starUpBaseInfo"]),
            "beceri_seviye": max(x["level"] for x in t["SkillUpLevel"]),
            "renk": 20,
            "antrenman": 100,
        },
    }


if __name__ == "__main__":
    tablolar = tablolari_oku(os.path.join(sys.argv[1], "conf_luatab_qte.assetbundle"))
    eksik = set(TABLOLAR) - set(tablolar)
    if eksik:
        # luatab paketinde JSON yerine Lua tablosu varsa json paketinden oku
        tablolar.update({k: v for k, v in tablolari_oku(os.path.join(sys.argv[1], "conf_json_qte.assetbundle")).items() if k in eksik})
    with open(sys.argv[2], "w", encoding="utf-8") as f:
        json.dump(derle(tablolar), f, ensure_ascii=False, separators=(",", ":"))
    print("yazildi:", sys.argv[2])
