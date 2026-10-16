"""Elite (Street Fight) şehir listesi ve maç verisi yükleyici; sunucu.py ile mac.py'nin ortak yardımcısı.

Kayıtta tutulanlar (durum.veri):
  elite          {"<battleId>": yıldız}         yalnızca kazanılmış maçlar; şehirler sırayla açılır
  elite_sandik   {"mac": [battleId, ...],        açılmış maç sandıkları (battle_status 2)
                  "yildiz": {"<stageId>": [star_count, ...]}}   açılmış yıldız sandıkları (status 1)
"""
import json
import os

from durum import VERI

KOK = os.path.dirname(os.path.abspath(__file__))


def _int_anahtar(d):
    return {int(k): v for k, v in d.items()}


def mac_verisi_yukle(yol=os.path.join(KOK, "veri", "mac_verisi.json")):
    """araclar/mac_verisi_cikar.py çıktısı; JSON'un metin anahtarlarını sayıya çevirir."""
    with open(yol, encoding="utf-8") as f:
        v = json.load(f)
    for ad in ("oyuncu", "egitim_dugum", "amigo", "mac", "takim", "dusman", "dusus", "elite_mac_sandik",
               "elite_supurme", "hikaye", "oyuncu_exp", "takim_exp", "esya_kullanim", "esya_fiyat"):
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
    """Kazanılmış maçın yıldızı; hiç kazanılmamışsa 0."""
    return int(k.get("elite", {}).get(str(battle_id), 0))


def elite_json(k):
    """Şehirler sırayla açılır: kazanılan maçlar 1, ilk kazanılmamış maç oynanabilir (0),
    önceki şehir bitmeden sonraki şehir kapalıdır. Panelden hepsi açılabilir."""
    kazanilan = k.setdefault("elite", {})
    acilan = sandiklar(k)
    acilan_yildiz_tum = acilan["yildiz"]
    acilan_mac = set(acilan["mac"])
    sehirler = []
    pi_s, pi_b = 0, 0
    onceki_bitti = True
    for e in sorted(VERI["elite"], key=lambda x: x["id"]):
        maclar = []
        for b in e["maclar"]:
            temiz = str(b) in kazanilan
            maclar.append({"battle_id": b, "star": mac_yildizi(k, b) if temiz else 0, "count": 0,
                           "supply_times": 0,
                           "battle_status": (2 if b in acilan_mac else 1) if temiz else 0})
        bitti = all(m["battle_status"] for m in maclar)
        if not onceki_bitti:
            durum_ = 0
        elif bitti:
            durum_ = 2
        else:
            durum_ = 1
            pi_s = e["id"]
            pi_b = next(m["battle_id"] for m in maclar if not m["battle_status"])
        onceki_bitti = onceki_bitti and bitti
        toplam = sum(m["star"] for m in maclar)
        acilan_yildiz = set(acilan_yildiz_tum.get(str(e["id"]), []))
        sehirler.append({
            "stage_id": e["id"],
            "stage_status": durum_,
            "star_all": toplam,
            "chests_list": [{"star_count": s, "status": 2 if s in acilan_yildiz else (1 if toplam >= s else 0)}
                            for s in e["sandiklar"]],
            "stage_status_ex": durum_,
            "battle_list": maclar,
        })
    return {"pi_s": pi_s, "pi_b": pi_b, "stage_list": sehirler}


def elite_yildiz_json(k):
    data = elite_json(k)
    data.update({"su_t_s": 0, "pi_ss": 0, "pi_bs": 0, "pi_ss_h": 0, "pi_bs_h": 0,
                 "st_s_s": 0, "ts_ss": 0, "ts_ss_e": 0, "h_r": 0})
    return data
