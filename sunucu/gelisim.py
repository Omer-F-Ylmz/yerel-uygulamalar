"""Oyuncu gelişimi ve takım özellikleri: işe alma, yıldız, renk (ilerleme), giysi, antrenman, top stili,
beceri, sihir/mücevher, ekipman (48/480x), amigolar (18/180x), eşya birleştirme (1/101), takım ikonu ve
takım seviye ödülü.

Kullanım (sunucu.py, esya.kur'dan SONRA; /cheer_leader ve /ball_team kayıtlarının yerine geçer):
    import gelisim; gelisim.kur(yon, durum)

Her işleyici istemcinin OnReceive'de okuduğu alanları döner (çoğunlukla data.team + data.backpack +
data.updatelist). Bedeller düşülür ama yetersiz altın/elmas/eşya hiçbir zaman hata değildir: değer 0'da kalır.

Kayda (durum.veri["oyuncular"][pid]) eklenen isteğe bağlı alanlar; yoksa sunucu.oyuncu_json'un tam değerleri:
  beceri_ozel       {"<skillId>": seviye}         beceri ve top stili seviyeleri
  ekipman           {"<no>": {"lv","blv","wlv"}}  ekipman yuvaları 1-6
  giyili            [index, ...]                  ilerleme için giyilmiş eşyalar (0-5)
  antrenman_dallar  [5 seviye]                    "train" de en düşük dala eşitlenir (mac.py için)
  buyume            int                           grow_up_cnts (antrenman tavanı = buyume tablosu)
  magics            [{magic_index, magic_id, ...}] yalnızca varsa gönderilir
Hesap düzeyi: amigo_kademe {"<id>": 1-6}, amigo_exp {"<id>": exp}, takim["ikon"].

sunucu.oyuncu_json, kur() sırasında bu alanları da ekleyen bir sarmalayıcıyla değiştirilir; böylece
/get_user_info ve 12/1201 gibi tüm takım cevapları aynı veriyi gösterir.

Veri: sunucu/veri/gelisim_verisi.json (araclar/gelisim_verisi_cikar.py).
"""
import json
import logging
import os
import random
import sys
import time

from cekirdek import basarili, hata
from durum import CANTA_TURU, ESYA_VERI, OYUNCU_VERI, SINIR, full_oyuncu
from elite import MAC_VERI as MV
import mac

log = logging.getLogger("sunucu")
KOK = os.path.dirname(os.path.abspath(__file__))

EVRENSEL_PARCA = 26000      # 万能碎片 (Window_ClipExchange)
STIL_PUANI = 30             # sunucu.STIL_PUANI ile aynı; puan hiç azalmaz
STIL_TAVAN = 99             # StyleSkillBaseInfo son satırı
AMIGO_TAVAN = 50
AMIGO_KADEME_TAVAN = 6      # 6 = beş kırılmanın hepsi açık (Window_OuendanLvUp index < 6)


def _int_anahtar(nesne):
    if isinstance(nesne, dict):
        anahtar_sayi = all(k.lstrip("-").isdigit() for k in nesne)
        return {(int(k) if anahtar_sayi else k): _int_anahtar(v) for k, v in nesne.items()}
    if isinstance(nesne, list):
        return [_int_anahtar(x) for x in nesne]
    return nesne


def veri_yukle(yol=os.path.join(KOK, "veri", "gelisim_verisi.json")):
    with open(yol, encoding="utf-8") as f:
        return _int_anahtar(json.load(f))


GV = veri_yukle()


# ---------------------------------------------------------------- yardımcılar

def sunucu_modulu():
    """oyuncu_json/takim_json/canta_json'ı tanımlayan modül (doğrudan çalıştırılınca __main__)."""
    for ad in ("sunucu", "__main__"):
        m = sys.modules.get(ad)
        if m is not None and hasattr(m, "takim_json") and hasattr(m, "oyuncu_json"):
            return m
    import sunucu  # noqa: F401  (testler)
    return sys.modules["sunucu"]


def sayi(x, varsayilan=0):
    try:
        return int(x)
    except (TypeError, ValueError):
        try:
            return int(float(x))
        except (TypeError, ValueError):
            return varsayilan


def paramlist(param):
    liste = param.get("paramlist") if isinstance(param, dict) else None
    return [sayi(x) for x in (liste or [])]


class Guncelleme:
    """updatelist.paramlist biriktirici: gold/gem/star farkları ve item_list değişimleri."""

    def __init__(self, k):
        self.k = k
        self.para = {}
        self.esya = {}

    def harca_para(self, ad, miktar):
        miktar = max(0, int(miktar))
        var = int(self.k.get(ad, 0))
        dus = min(var, miktar)
        if dus:
            self.k[ad] = var - dus
            self.para[ad] = self.para.get(ad, 0) - dus

    def harca(self, eid, adet):
        """Eşyayı düşer; yetmezse 0'da kalır (hiç hata yok)."""
        eid, adet = int(eid), max(0, int(adet))
        if not eid or not adet:
            return
        canta = self.k.setdefault("canta", {})
        var = int(canta.get(str(eid), 0))
        dus = min(var, adet)
        if dus:
            canta[str(eid)] = var - dus
            self.esya[eid] = self.esya.get(eid, 0) - dus

    def ekle(self, eid, adet):
        eid, adet = int(eid), int(adet)
        bilgi = ESYA_VERI.get(eid)
        if adet <= 0 or bilgi is None or bilgi.get("tur") not in CANTA_TURU:
            return
        canta = self.k.setdefault("canta", {})
        var = int(canta.get(str(eid), 0))
        yeni = min(mac.ESYA_SINIR, var + adet)
        if yeni != var:
            canta[str(eid)] = yeni
            self.esya[eid] = self.esya.get(eid, 0) + (yeni - var)

    def json(self):
        p = {ad: f for ad, f in self.para.items() if f}
        liste = [{"id": e, "count": f} for e, f in self.esya.items() if f]
        if liste:
            p["item_list"] = liste
        return {"op_flag": 1, "paramlist": p}


# ---------------------------------------------------------------- oyuncu JSON eklentisi

def stil_varsayilan(o):
    return max(1, min(STIL_TAVAN, int(o.get("level", 1))))


def beceri_tavani(pid, sid):
    if sid in GV["stil"].get(int(pid), {}):
        return STIL_TAVAN
    return SINIR["beceri_seviye"]


def acik_stiller(pid, o):
    yildiz = int(o.get("break_level", 0))
    return [sid for sid, gerek in sorted(GV["stil"].get(int(pid), {}).items(), key=lambda x: (x[1], x[0]))
            if yildiz >= gerek]


def varsayilan_buyume(o):
    return min(max(GV["buyume"]), max(0, -(-(int(o.get("train", 0)) - 30) // 10)))


def antrenman_dallari(o):
    dallar = o.get("antrenman_dallar")
    if isinstance(dallar, list) and len(dallar) == 5:
        return [int(x) for x in dallar]
    return [int(o.get("train", 0))] * 5


def giysi_idleri(pid, renk):
    return GV["giysi"].get("%d_%d" % (int(pid), int(renk))) or [0] * 6


def oyuncu_ek(pid, o, j):
    """oyuncu_json çıktısına gelişim alanlarını işler (yerinde değiştirir ve döner)."""
    ozel = o.get("beceri_ozel") or {}
    liste = j.setdefault("s_skill_list", [])
    for s in liste:
        if str(s["skill_id"]) in ozel:
            s["skill_level"] = int(ozel[str(s["skill_id"])])
    var = {s["skill_id"] for s in liste}
    for sid in acik_stiller(pid, o):
        if sid not in var:
            liste.append({"skill_id": sid, "skill_level": int(ozel.get(str(sid), stil_varsayilan(o)))})

    ekipman = o.get("ekipman") or {}
    for e in j.get("equip", []):
        d = ekipman.get(str(e["no"]))
        if d:
            e["lv"], e["blv"], e["wlv"] = int(d["lv"]), int(d["blv"]), int(d["wlv"])

    giyili = o.get("giyili") or []
    if giyili:
        idler = giysi_idleri(pid, o.get("color", 1))
        j["s_equipment_list"] = [{"index": i, "uid": int(pid) * 10 + i + 1, "id": idler[i]}
                                 for i in sorted(set(giyili)) if 0 <= i < 6]

    if isinstance(o.get("antrenman_dallar"), list):
        j["train"] = [{"level": x} for x in antrenman_dallari(o)]
    if "buyume" in o:
        j["grow_up_cnts"] = int(o["buyume"])
    if o.get("magics"):
        j["magics"] = o["magics"]
    return j


def oyuncu_json_sar(m):
    asil = m.oyuncu_json
    if getattr(asil, "_gelisim", False):
        return

    def oyuncu_json(pid, o):
        return oyuncu_ek(pid, o, asil(pid, o))

    oyuncu_json._gelisim = True
    oyuncu_json.asil = asil
    m.oyuncu_json = oyuncu_json


# ---------------------------------------------------------------- ekipman

def ekipman_yuvasi(o, no):
    ekipman = o.setdefault("ekipman", {})
    d = ekipman.get(str(no))
    if not d:
        # sunucu.oyuncu_json'un varsayılanı: tam güçlendirilmiş
        d = {"lv": GV["ekipman_sinir"]["guc"], "blv": GV["ekipman_sinir"]["kirilma"],
             "wlv": GV["ekipman_sinir"]["uyanis"]}
        ekipman[str(no)] = d
    return d


def guc_tavani(blv, takim_seviye):
    """EquipDataManager.GetMaxStrengthLv + takım seviyesi sınırı (IsCanStrength)."""
    lvler = [lv for lv, r in GV["guclendirme"].items() if r[3] == blv]
    tavan = max(lvler) + 1 if lvler else 0
    return max(0, min(GV["ekipman_sinir"]["guc"], tavan, int(takim_seviye)))


EKIPMAN_ONEK = (101, 102, 103, 201, 202, 203)  # sunucu.EKIPMAN_ONEK ile aynı


def ekipman_esya_id(pid, no):
    return int("%d%d" % (EKIPMAN_ONEK[no - 1], int(pid)))


# ---------------------------------------------------------------- amigolar

def amigo_seviye(k, aid):
    return int((k.get("amigolar") or {}).get(str(aid), 0) or 0)


def amigo_kademe(k, aid):
    kayitli = (k.get("amigo_kademe") or {}).get(str(aid))
    if kayitli:
        return max(1, min(AMIGO_KADEME_TAVAN, int(kayitli)))
    sv = amigo_seviye(k, aid)
    return min(5, max(1, -(-sv // 10)))  # sunucu.py'deki /cheer_leader ile aynı varsayılan


def amigo_secili_yuvalar(k):
    """select_cheers: 3 yuva, CheerLeaderBaseInfo.type sırasıyla (OuendanListStage.ChangeTeam)."""
    yuvalar = [0, 0, 0]
    for a in k.get("secili_amigolar") or []:
        a = sayi(a)
        tur = GV["amigo_tur"].get(a)
        if tur and 1 <= tur <= 3 and not yuvalar[tur - 1] and str(a) in (k.get("amigolar") or {}):
            yuvalar[tur - 1] = a
    return yuvalar


def amigo_json(k):
    return {
        "cheers": [{"id": int(a), "level": int(sv), "index": amigo_kademe(k, a),
                    "exp": int((k.get("amigo_exp") or {}).get(str(a), 0))}
                   for a, sv in (k.get("amigolar") or {}).items()],
        "select_cheers": [{"id": a} for a in amigo_secili_yuvalar(k)],
    }


def amigo_seviye_tavani(k, aid):
    sinirlar = GV["amigo_sinir"].get(int(aid)) or [[AMIGO_TAVAN, 0]]
    kademe = amigo_kademe(k, aid)
    if kademe > len(sinirlar):
        return AMIGO_TAVAN
    return min(AMIGO_TAVAN, int(sinirlar[kademe - 1][0]))


# ---------------------------------------------------------------- kurulum

def kur(yon, durum):
    m = sunucu_modulu()
    oyuncu_json_sar(m)

    def kayit():
        return durum.hesap_ac(durum.veri["hesap"] if durum.veri else "")

    def oyuncu(k, pid):
        return (k.get("oyuncular") or {}).get(str(int(pid)))

    def takim_cevabi(k, g, **ek):
        data = {"team": m.takim_json(k), "backpack": m.canta_json(k), "updatelist": g.json()}
        data.update(ek)
        return basarili(data)

    def op_kaydet(yol, islevler, varsayilan=None):
        onceki = yon.yollar.get(yol)

        def isle(alanlar, param, oturum=None, istek=None):
            op = alanlar.get("op", "")
            f = islevler.get(op, varsayilan)
            if f is None and onceki is not None:
                return onceki(alanlar=alanlar, param=param, oturum=oturum, istek=istek)
            if f is None:
                log.warning("BILINMEYEN %s op=%s", yol, op)
                return hata("HintBallTeamError")
            return f(alanlar, param)
        yon.yollar[yol] = isle
        return isle

    def tekil(yol):
        def kaydet(f):
            yon.yollar[yol] = lambda alanlar, param, oturum=None, istek=None: f(alanlar, param)
            return f
        return kaydet

    # ------------------------------------------------ 11/1101 işe alma (PanPlayerBag.OnReceive)
    @tekil("/player_compound")
    def ise_al(alanlar, param):
        pid = sayi(alanlar.get("player_id"))
        if pid not in OYUNCU_VERI:
            return hata("HintServerError")
        with durum.kilit:
            k = kayit()
            g = Guncelleme(k)
            if oyuncu(k, pid) is None:
                parca, adet = GV["parca"].get(pid, [0, 0])
                g.harca(parca, adet)
                k["oyuncular"][str(pid)] = full_oyuncu()
            durum.kaydet()
            return takim_cevabi(k, g)

    # ------------------------------------------------ 11/1102 kırılma (eski yıldız sistemi)
    def yildiz_yukselt(k, g, o, pid, hedef):
        hedef = max(int(o["break_level"]), min(SINIR["yildiz"], int(hedef)))
        tablo = GV["yildiz"].get(int(pid), {})
        parca = GV["parca"].get(int(pid), [0, 0])[0]
        for s in range(int(o["break_level"]), hedef):
            altin, adet = tablo.get(s, [0, 0])
            g.harca_para("gold", altin)
            g.harca(parca, adet)
        o["break_level"] = hedef

    @tekil("/player_break")
    def kir(alanlar, param):
        pid = sayi(alanlar.get("player_id"))
        with durum.kilit:
            k = kayit()
            o = oyuncu(k, pid)
            if o is None:
                return hata("HintServerError")
            g = Guncelleme(k)
            yildiz_yukselt(k, g, o, pid, int(o["break_level"]) + 1)
            durum.kaydet()
            return takim_cevabi(k, g)

    # ------------------------------------------------ 11/1103 ilerleme (renk) ve 11/1104 giysi
    @tekil("/player_advance")
    def ilerle(alanlar, param):
        pid = sayi(alanlar.get("player_id"))
        with durum.kilit:
            k = kayit()
            o = oyuncu(k, pid)
            if o is None:
                return hata("HintServerError")
            g = Guncelleme(k)
            if int(o["color"]) < SINIR["renk"]:
                o["color"] = int(o["color"]) + 1
                o["giyili"] = []
            durum.kaydet()
            return takim_cevabi(k, g)

    @tekil("/player_dress_equip")
    def giy(alanlar, param):
        pid = sayi(alanlar.get("player_id"))
        index = sayi(alanlar.get("index"), -1)
        with durum.kilit:
            k = kayit()
            o = oyuncu(k, pid)
            if o is None:
                return hata("HintServerError")
            g = Guncelleme(k)
            if 0 <= index < 6:
                giyili = o.setdefault("giyili", [])
                if index not in giyili:
                    g.harca(giysi_idleri(pid, o["color"])[index], 1)
                    giyili.append(index)
            durum.kaydet()
            return takim_cevabi(k, g)

    # ------------------------------------------------ beceri seviyesi (eski C# yolu, Lua'da çağrılmıyor)
    @tekil("/player_skill_uplevel")
    def beceri(alanlar, param):
        pid, sid = sayi(alanlar.get("player_id")), sayi(alanlar.get("skill_id"))
        with durum.kilit:
            k = kayit()
            o = oyuncu(k, pid)
            if o is None:
                return hata("HintServerError")
            g = Guncelleme(k)
            ozel = o.setdefault("beceri_ozel", {})
            simdiki = int(ozel.get(str(sid), stil_varsayilan(o) if sid in GV["stil"].get(pid, {}) else o["beceri"]))
            ozel[str(sid)] = min(beceri_tavani(pid, sid), simdiki + 1)
            durum.kaydet()
            return takim_cevabi(k, g)

    # ------------------------------------------------ 11/1105 antrenman (Window_PlayerTrain)
    @tekil("/player_train_up")
    def antrenman(alanlar, param):
        pid = sayi(alanlar.get("player_id"))
        tur = sayi(alanlar.get("train_type"))
        buyut = sayi(alanlar.get("isgrowup")) == 1
        with durum.kilit:
            k = kayit()
            o = oyuncu(k, pid)
            if o is None:
                return hata("HintServerError")
            g = Guncelleme(k)
            buyume = int(o.get("buyume", varsayilan_buyume(o)))
            dallar = antrenman_dallari(o)
            if buyut:
                buyume = min(max(GV["buyume"]), buyume + 1)
            else:
                tavan = min(SINIR["antrenman"], GV["buyume"].get(buyume, SINIR["antrenman"]))
                for i in (range(5) if tur not in (1, 2, 3, 4, 5) else [tur - 1]):
                    if dallar[i] < tavan:
                        dallar[i] += 1
                        altin, eid, adet = GV["antrenman"].get(dallar[i], [0, 0, 0])
                        g.harca_para("gold", altin)
                        g.harca(eid, adet)
            o["buyume"] = buyume
            o["antrenman_dallar"] = dallar
            o["train"] = min(dallar)
            durum.kaydet()
            return takim_cevabi(k, g)

    # ------------------------------------------------ 11/1106 yetenek eşitleme (istemcide kapalı)
    op_kaydet("/player_talent", {}, lambda alanlar, param: takim_cevabi(kayit(), Guncelleme(kayit())))

    # ------------------------------------------------ 11/1120 yıldız ve 11/1121 evrensel parça
    def yildiz_ac(alanlar, param):
        pl = paramlist(param)
        if len(pl) < 2:
            return hata("HintServerError")
        pid, hedef = pl[0], pl[1]
        with durum.kilit:
            k = kayit()
            o = oyuncu(k, pid)
            if o is None:
                return hata("HintServerError")
            g = Guncelleme(k)
            yildiz_yukselt(k, g, o, pid, hedef)
            durum.kaydet()
            return takim_cevabi(k, g)

    def parca_degistir(alanlar, param):
        pl = paramlist(param)
        if len(pl) < 2:
            return hata("HintServerError")
        pid, adet = pl[0], max(0, pl[1])
        with durum.kilit:
            k = kayit()
            g = Guncelleme(k)
            parca = GV["parca"].get(pid, [0, 0])[0]
            if parca and adet:
                g.harca(EVRENSEL_PARCA, adet)
                g.ekle(parca, adet)
            durum.kaydet()
            return takim_cevabi(k, g)

    op_kaydet("/player_star", {"star_up": yildiz_ac, "exchange": parca_degistir})

    # ------------------------------------------------ 11/1118-1119 top stili (PanPlayerInfo up_lv/buy_points)
    def stil_json():
        simdi = int(time.time())
        return {"styles_points": STIL_PUANI, "styles_last_update_ts": simdi, "last_update_ts": simdi, "cd": 0}

    def stil_yukselt(alanlar, param):
        pl = paramlist(param)
        if len(pl) < 2:
            return hata("HintServerError")
        pid, sid = pl[0], pl[1]
        with durum.kilit:
            k = kayit()
            o = oyuncu(k, pid)
            if o is None:
                return hata("HintServerError")
            g = Guncelleme(k)
            ozel = o.setdefault("beceri_ozel", {})
            simdiki = int(ozel.get(str(sid), stil_varsayilan(o)))
            tavan = min(STIL_TAVAN, max(1, int(o["level"])))
            if simdiki < tavan:
                g.harca_para("gold", GV["stil_bedel"].get(simdiki + 1, [0, 0])[0])
                ozel[str(sid)] = simdiki + 1
            durum.kaydet()
            return takim_cevabi(k, g, styles=stil_json(), today_buy_num=0)

    def puan_al(alanlar, param):
        with durum.kilit:
            k = kayit()
            g = Guncelleme(k)
            g.harca_para("gem", GV["puan_satin"].get(1, 0))
            durum.kaydet()
            return takim_cevabi(k, g, styles=stil_json(), today_buy_num=0)

    op_kaydet("/player_style", {"up_lv": stil_yukselt, "buy_points": puan_al})

    # ------------------------------------------------ 11/1107-1117 sihir (秘技) ve mücevher
    def sihir_yuvasi(o, index):
        for s in o.get("magics") or []:
            if int(s.get("magic_index", 0)) == int(index):
                return s
        return None

    def sihir_isle(degistir, **ek_cevap):
        """paramlist'i çözer, oyuncunun sihir yuvasına degistir(g, o, yuva, pl) uygular (yuva yoksa dokunmaz)."""
        def isle(alanlar, param):
            pl = paramlist(param)
            pid = pl[0] if pl else 0
            with durum.kilit:
                k = kayit()
                o = oyuncu(k, pid)
                if o is None:
                    return hata("HintServerError")
                g = Guncelleme(k)
                ek = degistir(g, o, pl) or {}
                durum.kaydet()
                return takim_cevabi(k, g, **ek)
        return isle

    def yuva_al(o, pl, sira):
        return sihir_yuvasi(o, pl[sira]) if len(pl) > sira else None

    def s_kirilma(g, o, pl):  # [pid, magicId, index]
        y = yuva_al(o, pl, 2)
        if y is not None:
            tur = GV["sihir_tur"].get(int(y.get("magic_id", 0)), 1)
            if int(y.get("level", 0)) < GV["sihir_max"].get(tur, 10):
                g.harca_para("gold", GV["sihir_kirilma"].get(tur, {}).get(int(y.get("level", 0)), 0))
                y["level"] = int(y.get("level", 0)) + 1
                y["exp"] = 0

    def s_aktif(g, o, pl):  # [pid, magicId, index] varsayımı
        y = yuva_al(o, pl, 2) or yuva_al(o, pl, 1)
        if y is not None:
            y["status"] = 1
            y["unlock"] = 1

    def s_yuceltme(g, o, pl):  # [pid, index, magicId, itemId]
        y = yuva_al(o, pl, 1)
        if len(pl) > 3:
            g.harca(pl[3], 1)
        if y is not None:
            tur = GV["sihir_tur"].get(int(y.get("magic_id", 0)), 1)
            y["level"] = min(GV["sihir_max"].get(tur, 10), int(y.get("level", 0)) + 1)

    def s_genel_rastgele(g, o, pl):
        havuz = [mid for mid, tur in GV["sihir_tur"].items() if tur == 2] or [0]
        return {"magicId": random.choice(havuz)}

    def s_ozel_rastgele(g, o, pl):  # [pid, magicId, index, skillIndex, skillId]
        index = pl[2] if len(pl) > 2 else 3
        havuz = GV["ozellik_havuzu"].get(5 if index == 5 else 3) or GV["ozellik_havuzu"].get(3) or [0]
        return {"skillId": random.choice(havuz)}

    def s_genel_degistir(g, o, pl, yeni_sira=3):  # [pid, magicId, index, yeniId]
        y = yuva_al(o, pl, 2)
        if y is not None and len(pl) > yeni_sira and pl[yeni_sira] in GV["sihir_tur"]:
            y["magic_id"] = pl[yeni_sira]

    def s_ozel_degistir(g, o, pl, index_sira=1, beceri_sira=2, yeni_sira=3):  # [pid, index, skillIndex, yeniId]
        y = yuva_al(o, pl, index_sira)
        if y is not None and len(pl) > yeni_sira:
            beceriler = y.setdefault("skill_list", [])
            i = max(1, pl[beceri_sira]) - 1
            if i < len(beceriler):
                beceriler[i]["skill_id"] = pl[yeni_sira]

    op_kaydet("/player_magic", {
        "magic_activate": sihir_isle(s_aktif),
        "magic_break": sihir_isle(s_kirilma),
        "magic_sublimation": sihir_isle(s_yuceltme),
        "magic_generic_random": sihir_isle(s_genel_rastgele),
        "magic_tx_random": sihir_isle(s_ozel_rastgele),
        "magic_generic_replace": sihir_isle(s_genel_degistir),
        "magic_tx_replace": sihir_isle(s_ozel_degistir),
        # Window_Treasure: [pid, magicId, index, yeniId] / [pid, magicId, index, skillIndex, skillId, yeniId]
        "magic_generic_dingxiang": sihir_isle(s_genel_degistir),
        "magic_tx_dingxiang": sihir_isle(lambda g, o, pl: s_ozel_degistir(g, o, pl, 2, 3, 5)),
    })

    def mucevher_tak(g, o, pl):  # [pid, index, jewelId]
        if len(pl) > 2:
            g.harca(pl[2], 1)
            y = sihir_yuvasi(o, pl[1])
            if y is not None and pl[2] in GV["sihir_tur"]:
                y["magic_id"] = pl[2]
                y["status"] = 1

    op_kaydet("/player_jewel", {
        "dress_jewel": sihir_isle(mucevher_tak),
        "drop_jewel": sihir_isle(lambda g, o, pl: None),
    })

    # ------------------------------------------------ 1/101 eşya birleştirme
    @yon.proto(1, 101)
    def birlestir(param, **_):
        eid = sayi((param or {}).get("id"))
        if eid not in ESYA_VERI:
            return hata("HintNotEnoughItem")
        with durum.kilit:
            k = kayit()
            g = Guncelleme(k)
            for malzeme, adet in GV["esya_birlesim"].get(eid, []):
                g.harca(malzeme, adet)
            altin, bedel_id, bedel_adet = GV["esya_birlesim_bedel"].get(eid, [0, 0, 0])
            g.harca_para("gold", altin)
            g.harca(bedel_id, bedel_adet)
            g.ekle(eid, 1)
            durum.kaydet()
            return takim_cevabi(k, g)

    # ------------------------------------------------ 48/4801-4804 ekipman (EquipInfoStage, Window_DowStar)
    def ekipman_cevabi(k, g, pid):
        j = m.oyuncu_json(pid, k["oyuncular"][str(pid)])
        return basarili({"equip": j["equip"], "updatelist": g.json()})

    def ekipman_isle(degistir):
        def isle(alanlar, param):
            pl = paramlist(param)
            if len(pl) < 2:
                return hata("HintServerError")
            pid, no = pl[0], pl[1]
            with durum.kilit:
                k = kayit()
                o = oyuncu(k, pid)
                if o is None or not 1 <= no <= 6:
                    return hata("HintServerError")
                g = Guncelleme(k)
                degistir(k, g, o, pid, no, pl[2] if len(pl) > 2 else 0)
                durum.kaydet()
                return ekipman_cevabi(k, g, pid)
        return isle

    def grup(no):
        return [1, 2, 3] if no <= 3 else [4, 5, 6]

    def guclendir(k, g, o, pid, no, tur):
        # istemci: 1 = bu yuva gidebildiği yere kadar (UpLvEvent_0), 2 = aynı gruptaki üç yuva; diğer: tek seviye
        hedefler = grup(no) if tur == 2 else [no]
        for n in hedefler:
            d = ekipman_yuvasi(o, n)
            tavan = guc_tavani(int(d["blv"]), k["takim"].get("seviye", 1))
            son = tavan if tur in (1, 2) else min(tavan, int(d["lv"]) + 1)
            for lv in range(int(d["lv"]) + 1, son + 1):
                altin, eid, adet, _ = GV["guclendirme"].get(lv, [0, 0, 0, 0])
                g.harca_para("gold", altin)
                g.harca(eid, adet)
            d["lv"] = max(int(d["lv"]), son)

    def ekipman_kir(k, g, o, pid, no, tur):
        for n in (grup(no) if tur == 2 else [no]):
            d = ekipman_yuvasi(o, n)
            if int(d["blv"]) < GV["ekipman_sinir"]["kirilma"]:
                eid, adet, altin = GV["kirilma"].get(n, {}).get(int(d["blv"]), [0, 0, 0])
                g.harca(eid, adet)
                g.harca_para("gold", altin)
                d["blv"] = int(d["blv"]) + 1

    def uyandir(k, g, o, pid, no, _):
        d = ekipman_yuvasi(o, no)
        if int(d["wlv"]) < GV["ekipman_sinir"]["uyanis"]:
            e1, a1, e2, a2, altin = GV["uyanis"].get(ekipman_esya_id(pid, no), {}).get(int(d["wlv"]), [0] * 5)
            g.harca(e1, a1)
            g.harca(e2, a2)
            g.harca_para("gold", altin)
            d["wlv"] = int(d["wlv"]) + 1

    def geri_al(k, g, o, pid, no, _):
        """Uyanışı sıfırlar, harcanan uyanış malzemelerini geri verir (Window_DowStarSuer)."""
        d = ekipman_yuvasi(o, no)
        tablo = GV["uyanis"].get(ekipman_esya_id(pid, no), {})
        for w in range(int(d["wlv"])):
            e1, a1, e2, a2, _altin = tablo.get(w, [0] * 5)
            g.ekle(e1, a1)
            g.ekle(e2, a2)
        d["wlv"] = 0

    op_kaydet("/player_equip", {
        "strength": ekipman_isle(guclendir),
        "break": ekipman_isle(ekipman_kir),
        "wake": ekipman_isle(uyandir),
        "recycle": ekipman_isle(geri_al),
    })

    # ------------------------------------------------ 18/1801-1805 amigolar
    def amigo_cevabi(k, g, eski_guc):
        return basarili({"cheer_leader": amigo_json(k), "updatelist": g.json(),
                         "fight": {"old": eski_guc, "new": m.takim_gucu(k)}})

    def amigo_isle(degistir):
        def isle(alanlar, param):
            pl = paramlist(param)
            with durum.kilit:
                k = kayit()
                eski = m.takim_gucu(k)
                g = Guncelleme(k)
                k.setdefault("amigolar", {})
                degistir(k, g, pl)
                durum.kaydet()
                return amigo_cevabi(k, g, eski)
        return isle

    def amigo_sec(k, g, pl):
        sahip = k["amigolar"]
        if len(pl) >= 3:
            yuvalar = [a if str(a) in sahip else 0 for a in pl[:3]]
        else:
            yuvalar = amigo_secili_yuvalar(k)
            for a in pl[:1]:
                tur = GV["amigo_tur"].get(a)
                if str(a) in sahip and tur and 1 <= tur <= 3:
                    yuvalar[tur - 1] = a
        k["secili_amigolar"] = [a for a in yuvalar if a] or []

    def amigo_birlestir(k, g, pl):
        for a in pl[:1]:
            if a in GV["amigo_tur"] and str(a) not in k["amigolar"]:
                parca, adet = GV["amigo_parca"].get(a, [0, 0])
                g.harca(parca, adet)
                k["amigolar"][str(a)] = 1
                k.setdefault("amigo_kademe", {})[str(a)] = 1
                k.setdefault("amigo_exp", {})[str(a)] = 0

    def amigo_seviye_atla(k, g, pl):  # [amigoId, esyaId, adet]
        if len(pl) < 3 or str(pl[0]) not in k["amigolar"]:
            return
        aid, eid, adet = pl[0], pl[1], max(0, pl[2])
        tur, deger = MV["esya_kullanim"].get(eid, [0, 0])
        g.harca(eid, adet)
        kazanc = int(deger) * adet if tur == 6 else 0
        exp_tablo = k.setdefault("amigo_exp", {})
        sv = amigo_seviye(k, aid)
        exp = int(exp_tablo.get(str(aid), 0)) + kazanc
        tavan = amigo_seviye_tavani(k, aid)
        while sv < tavan and exp >= GV["amigo_exp"].get(sv, 1 << 60):
            exp -= GV["amigo_exp"][sv]
            sv += 1
        if sv >= tavan:
            exp = 0
        k["amigolar"][str(aid)] = sv
        exp_tablo[str(aid)] = exp

    def amigo_aktif(k, g, pl):
        for aid in pl[:1]:
            if str(aid) not in k["amigolar"]:
                continue
            kademe = amigo_kademe(k, aid)
            if kademe >= AMIGO_KADEME_TAVAN:
                continue
            sinirlar = GV["amigo_sinir"].get(aid, [])
            if kademe <= len(sinirlar):
                eid, adet = GV["amigo_esya"].get(sinirlar[kademe - 1][1], [0, 0])
                g.harca(eid, adet)
            k.setdefault("amigo_kademe", {})[str(aid)] = kademe + 1

    op_kaydet("/cheer_leader", {
        "get_cheer_info": lambda alanlar, param: basarili({"cheer_leader": amigo_json(kayit())}),
        "change_cheer": amigo_isle(amigo_sec),
        "compound_cheer": amigo_isle(amigo_birlestir),
        "levelup_cheer": amigo_isle(amigo_seviye_atla),
        "active_cheer": amigo_isle(amigo_aktif),
    }, lambda alanlar, param: basarili({"cheer_leader": amigo_json(kayit())}))

    # ------------------------------------------------ 15/150x takım: ikon ve seviye ödülü (get/rename sunucu.py'de)
    def ikon_degistir(alanlar, param):
        pl = paramlist(param)
        with durum.kilit:
            k = kayit()
            if pl and pl[0] > 0:
                k["takim"]["ikon"] = pl[0]
                durum.kaydet()
            return basarili(m.ballteam_json(k))

    def seviye_odulu(alanlar, param):
        pl = paramlist(param)
        with durum.kilit:
            k = kayit()
            sv = pl[0] if pl else int(k["takim"].get("seviye", 1))
            altin, elmas, yildiz, esyalar = GV["takim_odul"].get(sv, [0, 0, 0, []])
            odul = {"exp": 0, "exp_team": 0, "gold": altin, "gem": elmas, "star": yildiz,
                    "esyalar": {e: a for e, a in esyalar}}
            updatelist, _, _ = mac.odul_uygula(k, odul, [])
            durum.kaydet()
            data = m.ballteam_json(k)
            data["updatelist"] = updatelist
            return basarili(data)

    op_kaydet("/ball_team", {"reicon": ikon_degistir, "get_prize": seviye_odulu})
