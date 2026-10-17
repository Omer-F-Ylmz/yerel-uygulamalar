"""Yönetim paneli: http://localhost:8881/panel

Kayıttaki her şeyi tarayıcıdan değiştirir. Oyun verileri girişte yüklediği için
değişiklikler oyunda bir sonraki girişte (veya lobiye dönüşte) görünür.
"""
import json
import os

from cekirdek import Ham, json_yaz
from durum import ESYA_VERI, OYUNCU_VERI, SINIR, VERI, full_oyuncu

_CEVIRI_YOLU = os.path.join(os.path.dirname(os.path.abspath(__file__)), "veri", "ceviri_tr.json")
CEVIRI = json.load(open(_CEVIRI_YOLU, encoding="utf-8")) if os.path.exists(_CEVIRI_YOLU) else {}
SAYFA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "panel.html")
SAYI_ALANLARI = ("gold", "gem", "star", "stamina", "vip", "rm_ticket")
POZISYON = {1: "Pivot", 2: "Skorer", 3: "Oyun kurucu"}


def _sayi(deger, en_az=0, en_cok=2_000_000_000):
    return max(en_az, min(en_cok, int(deger)))


def kur(yon, durum):
    def ozet():
        k = durum.hesap_ac(durum.veri["hesap"] if durum.veri else "")
        return {
            "hesap": k["hesap"],
            "takim": k["takim"],
            "kaynak": {a: k[a] for a in SAYI_ALANLARI},
            "secili": k["secili"],
            "oyuncular": [
                dict(id=o["id"], ad=CEVIRI.get(o["ad"], o["ad"]), pozisyon=POZISYON.get(o["pozisyon"], "?"),
                     sahip=str(o["id"]) in k["oyuncular"], **k["oyuncular"].get(str(o["id"]), {}))
                for o in VERI["oyuncular"]
            ],
            "esyalar": [dict(id=e["id"], ad=CEVIRI.get(e["ad"], e["ad"]), tur=e["tur"], adet=k["canta"].get(str(e["id"]), 0))
                        for e in VERI["esyalar"] if e["cantada"]],
            "sinir": SINIR,
            "guc_carpani": k.get("guc_carpani", 2.5),
            "mac_modu": k.get("mac_modu") or ("sade" if k.get("sade_mac") else "normal"),
            "efsane": bool(k.get("efsane", True)),
        }

    def islem(veri):
        ad = veri.get("islem")
        with durum.kilit:
            k = durum.hesap_ac("")
            if ad == "kaynak":
                for a in SAYI_ALANLARI:
                    if a in veri:
                        k[a] = _sayi(veri[a])
                if "takim_seviye" in veri:
                    k["takim"]["seviye"] = _sayi(veri["takim_seviye"], 1, SINIR["takim_seviye"])
                if veri.get("mac_modu") in ("normal", "sade", "teshis"):
                    k["mac_modu"] = veri["mac_modu"]
                    k.pop("sade_mac", None)
                if "guc_carpani" in veri:
                    k["guc_carpani"] = max(0.1, min(20.0, float(veri["guc_carpani"])))
                if "efsane" in veri:
                    k["efsane"] = bool(veri["efsane"])
                if veri.get("takim_adi"):
                    k["takim"]["ad"] = str(veri["takim_adi"])[:20]
            elif ad == "hepsini_fulle":
                for o in VERI["oyuncular"]:
                    k["oyuncular"][str(o["id"])] = full_oyuncu()
            elif ad == "oyuncu":
                pid = str(int(veri["id"]))
                if int(pid) not in OYUNCU_VERI:
                    return {"hata": "boyle bir oyuncu yok"}
                o = k["oyuncular"].setdefault(pid, full_oyuncu())
                for alan, ust in (("level", "oyuncu_seviye"), ("break_level", "yildiz"), ("color", "renk"),
                                  ("beceri", "beceri_seviye"), ("train", "antrenman")):
                    if alan in veri:
                        o[alan] = _sayi(veri[alan], 1 if alan != "break_level" else 0, SINIR[ust])
            elif ad == "oyuncu_kaldir":
                pid = int(veri["id"])
                if any(s["id"] == pid for s in k["secili"]):
                    return {"hata": "kadrodaki oyuncu kaldirilamaz, once kadroyu degistir"}
                k["oyuncular"].pop(str(pid), None)
            elif ad == "kadro":
                idler = [int(x) for x in veri["idler"]]
                if len(idler) != 3 or len(set(idler)) != 3:
                    return {"hata": "3 farkli oyuncu sec"}
                if any(str(i) not in k["oyuncular"] for i in idler):
                    return {"hata": "secilen oyunculardan biri sende yok"}
                k["secili"] = [{"pos": p, "id": i} for p, i in zip((1, 2, 3), idler)]
            elif ad == "esyalari_doldur":
                adet = _sayi(veri.get("adet", 999), 0, 99999)
                for e in VERI["esyalar"]:
                    if e["cantada"] and e["tur"] in (1, 2, 4):
                        k["canta"][str(e["id"])] = adet
            elif ad == "esya":
                eid = int(veri["id"])
                if eid not in ESYA_VERI:
                    return {"hata": "boyle bir esya yok"}
                k["canta"][str(eid)] = _sayi(veri.get("adet", 0), 0, 99999)
            elif ad == "elite_full":
                k["elite"] = {str(b): 3 for e in VERI["elite"] for b in e["maclar"]}
            elif ad == "elite_sifirla":
                k["elite"] = {}
            elif ad == "sifirla":
                durum.sifirla()
                return {"tamam": True}
            else:
                return {"hata": "bilinmeyen islem"}
            durum.kaydet()
        return {"tamam": True}

    def panel(yol, istek, govde=""):
        yol = yol.split("?")[0].strip("/")
        if yol in ("", "index.html"):
            with open(SAYFA, encoding="utf-8") as f:
                return Ham(f.read(), "text/html; charset=utf-8")
        if yol == "api/durum":
            return Ham(json_yaz(ozet()), "application/json; charset=utf-8")
        if yol == "api/islem":
            try:
                cevap = islem(json.loads(govde or "{}"))
            except (ValueError, KeyError, TypeError) as e:
                cevap = {"hata": "gecersiz istek: %s" % e}
            return Ham(json_yaz(cevap), "application/json; charset=utf-8")
        if yol == "api/yedek":
            with durum.kilit:
                return Ham(json.dumps(durum.veri, ensure_ascii=False, indent=1), "application/json; charset=utf-8")
        return Ham("", durum=404)

    panel.govde_ister = True
    yon.onekler.insert(0, ("/panel", panel))
