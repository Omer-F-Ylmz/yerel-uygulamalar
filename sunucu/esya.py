"""Çanta işlemleri: eşya kullanma (1/102) ve satma (1/103).

data_item_usage.use_type: 1 = düşüş listesi (param = droplist id), 2/4 = enerji, 3 = takım deneyimi;
diğerleri yalnızca eşyayı harcar.
"""
from cekirdek import basarili, hata
from elite import MAC_VERI as MV
import mac


def kur(yon, durum):
    def kayit():
        return durum.hesap_ac(durum.veri["hesap"] if durum.veri else "")

    def harca(k, eid, adet):
        canta = k.setdefault("canta", {})
        var = int(canta.get(str(eid), 0))
        if var < adet:
            return False
        canta[str(eid)] = var - adet
        return True

    def birlestir(updatelist, eid, fark):
        liste = updatelist["paramlist"].setdefault("item_list", [])
        for e in liste:
            if e["id"] == eid:
                e["count"] += fark
                return
        liste.append({"id": eid, "count": fark})

    @yon.proto(1, 102)
    def kullan(param, **_):
        eid = int(param.get("id") or 0)
        adet = max(1, int(param.get("count") or 1))
        tur, deger = MV["esya_kullanim"].get(eid, [0, 0])
        with durum.kilit:
            k = kayit()
            if not harca(k, eid, adet):
                return hata("HintNotEnoughItem")
            odul = {"exp": 0, "exp_team": 0, "gold": 0, "gem": 0, "star": 0, "esyalar": {}}
            if tur == 1:
                odul = mac.odul_topla([mac.dusus_coz(deger) for _ in range(min(adet, 999))])
            elif tur == 3:
                odul["exp_team"] = int(deger) * adet
            elif tur in (2, 4):
                k["stamina"] = int(k.get("stamina", 0)) + int(deger) * adet
            updatelist, _, _ = mac.odul_uygula(k, odul, [])
            birlestir(updatelist, eid, -adet)
            durum.kaydet()
        return basarili({"updatelist": updatelist})

    @yon.proto(1, 103)
    def sat(param, **_):
        liste = param.get("paramlist") or []
        if len(liste) < 2:
            return hata("HintNotEnoughItem")
        eid, adet = int(liste[0]), max(1, int(liste[1]))
        with durum.kilit:
            k = kayit()
            if not harca(k, eid, adet):
                return hata("HintNotEnoughItem")
            kazanc = int(MV["esya_fiyat"].get(eid, 0)) * adet
            odul = {"exp": 0, "exp_team": 0, "gold": kazanc, "gem": 0, "star": 0, "esyalar": {}}
            updatelist, _, _ = mac.odul_uygula(k, odul, [])
            birlestir(updatelist, eid, -adet)
            durum.kaydet()
        return basarili({"updatelist": updatelist})
