"""Elite (Street Fight) şehir listesi ve maç verisi yükleyici; sunucu.py ile mac.py'nin ortak yardımcısı.

Kayıtta tutulanlar (durum.veri):
  elite          {"<battleId>": yıldız}         oynanmamış maç VARSAYILAN_YILDIZ ile gösterilir
  elite_sandik   {"mac": [battleId, ...],        açılmış maç sandıkları (battle_status 2)
                  "yildiz": {"<stageId>": [star_count, ...]}}   açılmış yıldız sandıkları (status 1)
"""
import json
import os

from durum import VERI

KOK = os.path.dirname(os.path.abspath(__file__))
VARSAYILAN_YILDIZ = 3


def _int_anahtar(d):
    return {int(k): v for k, v in d.items()}


def mac_verisi_yukle(yol=os.path.join(KOK, "veri", "mac_verisi.json")):
    """araclar/mac_verisi_cikar.py çıktısı; JSON'un metin anahtarlarını sayıya çevirir."""
    with open(yol, encoding="utf-8") as f:
        v = json.load(f)
    for ad in ("oyuncu", "egitim_dugum", "amigo", "mac", "takim", "dusman", "dusus", "elite_mac_sandik",
               "elite_supurme", "hikaye", "oyuncu_exp", "takim_exp"):
        v[ad] = _int_anahtar(v[ad])
    v["elite_yildiz_sandik"] = {int(s): _int_anahtar(c) for s, c in v["elite_yildiz_sandik"].items()}
    return v


MAC_VERI = mac_verisi_yukle()


def sandiklar(k):
    s = k.setdefault("elite_sandik", {})
    s.setdefault("mac", [])
    s.setdefault("yildiz", {})
    return s


def mac_yildizi(k, battle_id):
    return int(k.get("elite", {}).get(str(battle_id), VARSAYILAN_YILDIZ))


def elite_json(k):
    """Tüm şehirler açık ve tamamlanmış, her maç tekrar oynanabilir, sınırsız deneme."""
    k.setdefault("elite", {})
    acilan = sandiklar(k)
    acilan_mac = set(acilan["mac"])
    sehirler = []
    for e in VERI["elite"]:
        maclar = []
        for b in e["maclar"]:
            durum_ = 2 if b in acilan_mac else 1
            maclar.append({"battle_id": b, "star": mac_yildizi(k, b), "count": 0, "supply_times": 0,
                           "battle_status": durum_})
        acilan_yildiz = set(acilan["yildiz"].get(str(e["id"]), []))
        sehirler.append({
            "stage_id": e["id"],
            "stage_status": 2,
            "star_all": sum(m["star"] for m in maclar),
            "chests_list": [{"star_count": s, "status": 1 if s in acilan_yildiz else 0} for s in e["sandiklar"]],
            "stage_status_ex": 2,
            "battle_list": maclar,
        })
    return {"pi_s": 0, "pi_b": 0, "stage_list": sehirler}


def elite_yildiz_json(k):
    data = elite_json(k)
    data.update({"su_t_s": 0, "pi_ss": 0, "pi_bs": 0, "pi_ss_h": 0, "pi_bs_h": 0,
                 "st_s_s": 0, "ts_ss": 0, "ts_ss_e": 0, "h_r": 0})
    return data
