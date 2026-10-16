"""Diğer oyun modları: tek oyunculu, yapay zekâ rakiplere karşı.

  Deneme (Trial)        10/1000-1005   maç: 7/705 (data_battle tür 5)   sonuç: kazanılan dalga sayısına göre data_trial_droplist
  Lig / parça bölümleri 47/4700-4704   maç: 7/705 (tür 9), sonuç mac.py'de (düşüş listeleri bu modülden eklenir)
  Sokak macerası        14/1400-1410 (Lua) ve /op_rewardmatch?op=... (C# BuntryPrepareStage)
                        maç: 7/705 (tür 3), sonuç: 7/702 + data.rm, ardından op=battle_result
  Aranan (Wanted)       24/2400-2401   maç: 7/701 [8, uin, 0, 100]
  Canlı yayın           8/800-806      istemcide arayüzü yok; yalnızca boş "live_show" döner
  Özel antrenman        60/6001-6005   (data_qualifiy_* tabloları OBB'de yok; yalnızca cevap şekilleri)
  Sıralama (Ladder)     21/2101-2113   maç: 7/701 [7, uin, 0, 0]; sonuç: data.ladder
  Usta maçı (Master)    52/5203-5215   maç: 7/701 [12, uin, 0, 0]; sonuç: data.master
  Açık turnuva          2059/205901-205917  maç: 7/701 [13, uin, 0, 0]; sonuç: data.open (+ 205915)
  Arena                 32/3200-3208   ArenaStage "maç ara" sonrası TCP yerine HTTP 7/701 [11, 0, 0, 0] gönderir;
                        3208 (gerçek zamanlı TCP maç) kibar bir hata döner.
  Etkinlik sıralaması   40/4001, 4002, 4004, 4005

7/701, 7/702 ve 7/705 mac.py'nin işleyicilerini sarar: yukarıdaki maç türleri burada, geri kalanı mac.py'de işlenir.
Bu yüzden kur() mac.kur()'dan SONRA çağrılmalıdır.

Rakipler: sıralama listelerindeki takımlar oyuncunun gücüne göre ölçeklenen yapay zekâ takımlarıdır. Takım "no"
numarasından belirlenimci üretilir (ad, ikon, oyuncular); nitelikler mac.nitelik_hesapla ile kurulup hedef güce
ölçeklenir. Kayıtta yalnızca oyuncunun sıralaması ve yer değiştiren yapay zekâlar tutulur.

Kayıt (durum.veri["modlar"]):
  merdiven {r, rh, c, ta, yer{"sıra": no}, takim[pid*3], dc, log[], en_l[]}
  aranan {kazanma, tohum}        usta {sr, com, ta, takimlar[[pid*3]*3], cl, tohum}
  acik {st, stsh, ta, f, gs, tl[[pid*3]*3], kilit[], cl[], chl{"adım": adet}, tohum, rcr}
  arena {st, pl[], sec[], tl[[eid*3]*3], c_w, c_l, tohum}
  rm {status, level, fee, fee_temp, ... kartlar[], bag{}, settlement[], bekleyen{}}
  nitelik {"pid": [lv, skillLv]}

Veri: araclar/modlar_verisi_cikar.py -> veri/modlar_verisi.json
"""
import json
import logging
import math
import os
import random
import time

import mac
from cekirdek import basarili, hata
from durum import VERI
from elite import MAC_VERI as MV

log = logging.getLogger("sunucu")
KOK = os.path.dirname(os.path.abspath(__file__))

AI_UIN = 2000000            # < 1400000000: istemci robot saymaz, takım ikonunu gösterir
MERDIVEN_N = 1000           # sıralamadaki takım sayısı
MERDIVEN_BASLANGIC = 800
IKONLAR = [1, 2, 8, 11] + list(range(15, 37))   # TeamPlayerIcon'daki oyuncu dışı ikonlar
ISIM_A = ["Street", "Night", "Urban", "Iron", "Golden", "Silver", "Thunder", "Shadow", "Blaze", "Rapid", "Royal",
          "Wild", "Neon", "Storm", "Steel", "Red", "Blue", "Black", "White", "Crimson", "Cosmic", "Desert",
          "Frozen", "Electric", "Savage", "Midnight", "Turbo", "Ghost", "Atomic", "Vortex"]
ISIM_B = ["Kings", "Hawks", "Wolves", "Tigers", "Ballers", "Dunkers", "Ravens", "Sharks", "Bulls", "Eagles",
          "Panthers", "Vipers", "Titans", "Rebels", "Rockets", "Giants", "Falcons", "Lions", "Dragons", "Bandits",
          "Knights", "Phantoms", "Hornets", "Cobras", "Spartans"]
BOS_ODUL = {"exp": 0, "exp_team": 0, "gold": 0, "gem": 0, "star": 0}


# ---------------------------------------------------------------- veri

def _int(d):
    return {int(a): v for a, v in d.items()}


def veri_yukle(yol=os.path.join(KOK, "veri", "modlar_verisi.json")):
    with open(yol, encoding="utf-8") as f:
        v = json.load(f)
    v["dusus"] = _int(v["dusus"])
    v["dusman"] = _int(v["dusman"])
    v["deneme"]["seviye"] = _int(v["deneme"]["seviye"])
    v["deneme"]["dusus"] = {int(b): _int(w) for b, w in v["deneme"]["dusus"].items()}
    v["rm"]["harita"] = _int(v["rm"]["harita"])
    v["usta"]["seri"] = _int(v["usta"]["seri"])
    v["acik"]["savas"] = _int(v["acik"]["savas"])
    v["acik"]["destek"] = _int(v["acik"]["destek"])
    v["arena"]["sandik"] = _int(v["arena"]["sandik"])
    v["sira_odul"] = _int(v["sira_odul"])
    # mac.py'nin dusus_coz / rakip kurucusu bu modülün düşüş listelerini ve arena oyuncularını da görsün
    for a, d in v["dusus"].items():
        MV["dusus"].setdefault(a, d)
    for a, d in v["dusman"].items():
        MV["dusman"].setdefault(a, d)
    return v


MD = veri_yukle()


def _gruplar():
    """Takım yuvaları: 1 pota altı (position 4), 2 kanat (2/3), 3 oyun kurucu (1)."""
    g = {1: [], 2: [], 3: []}
    for o in VERI["oyuncular"]:
        if o["id"] not in MV["oyuncu"]:
            continue
        p = o["pozisyon"]
        g[1 if p == 4 else 3 if p == 1 else 2].append(o["id"])
    for s in g:
        g[s] = sorted(g[s]) or sorted(MV["oyuncu"])
    return g


GRUP = _gruplar()


# ---------------------------------------------------------------- yardımcılar

def simdi():
    return int(time.time())


def sayi(x, varsayilan=0):
    try:
        return int(x)
    except (TypeError, ValueError):
        return varsayilan


def sinirla(x, alt, ust):
    return max(alt, min(ust, x))


def paramlist(param):
    if isinstance(param, list):
        return param
    liste = (param or {}).get("paramlist") if isinstance(param, dict) else None
    return liste if isinstance(liste, list) else []


def odul(gold=0, gem=0, exp=0, exp_team=0, star=0, esyalar=None):
    return {"exp": exp, "exp_team": exp_team, "gold": gold, "gem": gem, "star": star, "esyalar": dict(esyalar or {})}


def dusus(dusus_id):
    return mac.dusus_coz(dusus_id or 0)


def secim(rnd, liste, agirlik):
    return rnd.choices(liste, weights=[max(0.0001, w) for w in agirlik])[0]


# ---------------------------------------------------------------- yapay zekâ takımları

def ai_adi(no):
    n = len(ISIM_A) * len(ISIM_B)
    idx = (no * 37 + 11) % n
    ad = "%s %s" % (ISIM_A[idx // len(ISIM_B)], ISIM_B[idx % len(ISIM_B)])
    return ad if no < n else "%s %d" % (ad, no // n + 1)


def ai_ozet(no, guc, seviye):
    return {"uin": AI_UIN + no, "id": no, "name": ai_adi(no), "icon": IKONLAR[no % len(IKONLAR)],
            "level": int(sinirla(seviye, 1, 100)), "strength": int(guc)}


def olcek(ham, hedef):
    """Ham nitelikleri, toplam savaş gücü hedefe ulaşacak şekilde ölçekleyen çarpan (ikiye bölme)."""
    hedef = max(int(hedef), 60)

    def toplam(s):
        return sum(mac.guc_hesapla([max(1, int(math.ceil(x * s))) for x in h]) for h in ham)

    alt, ust = 1e-4, 1e4
    for _ in range(60):
        orta = math.sqrt(alt * ust)
        if toplam(orta) < hedef:
            alt = orta
        else:
            ust = orta
    return ust


def ai_oyuncular(rnd, hedef, seviye):
    pids = []
    for yuva in (1, 2, 3):
        aday = [p for p in GRUP[yuva] if p not in pids] or [p for p in sorted(MV["oyuncu"]) if p not in pids]
        pids.append(rnd.choice(aday))
    seviye = sinirla(int(seviye), 1, 100)
    yildiz = sinirla(seviye * 30 // 100 + rnd.randint(-2, 2), 1, 30)
    renk = sinirla(seviye * 20 // 100 + rnd.randint(-2, 1), 1, 20)
    o = {"level": seviye, "break_level": yildiz, "color": renk, "train": seviye,
         "grow_up_cnts": sinirla((seviye - 21) // 10, 0, 7), "beceri": max(1, seviye // 10)}
    ham = [mac.nitelik_hesapla(p, o) for p in pids]
    s = olcek(ham, hedef)
    oyuncular = []
    for i, (pid, h) in enumerate(zip(pids, ham)):
        deger = [max(1, int(math.ceil(x * s))) for x in h]
        enerji = MV["oyuncu"][pid]["e"]
        oyuncular.append({"id": pid, "enemy_id": 0, "level": seviye, "break_level": yildiz, "color": renk,
                          "pos": i + 1, "skill_list": mac.beceri_listesi(pid, o),
                          "attr": mac.attr_json(deger, enerji[0], enerji[1])})
    return oyuncular


_ai_onbellek = {}


def ai_dalgalar(no, guc, seviye, dalga=1):
    anahtar = (no, int(guc), int(seviye), dalga)
    if anahtar not in _ai_onbellek:
        if len(_ai_onbellek) > 256:
            _ai_onbellek.clear()
        rnd = random.Random(no * 1000003 + dalga)
        _ai_onbellek[anahtar] = [ai_oyuncular(rnd, guc / dalga, seviye) for _ in range(dalga)]
    return _ai_onbellek[anahtar]


def ai_amigo(no):
    ids = sorted(MV["amigo"]) or [0]
    return {"id": ids[no % len(ids)], "level": 50, "gears": 6}


def oyuncu_ozet(p):
    return {"id": p["id"], "level": p["level"], "break_level": p["break_level"], "pos": p["pos"], "color": p["color"]}


# ---------------------------------------------------------------- kendi takımımız

def biz_takim(k, pids=None):
    """mac.kendi_takim; pids verilirse seçili kadro yerine o oyuncular (eksikler sahip olunanlardan)."""
    if pids:
        kk = dict(k)
        kk["secili"] = [{"pos": i + 1, "id": int(p)} for i, p in enumerate(pids) if p and str(p) in k["oyuncular"]]
        return mac.kendi_takim(kk)
    return mac.kendi_takim(k)


def takim_gucu(k, pids=None):
    return sum(p["attr"]["fight"] for p in biz_takim(k, pids)[0])


def plist(pids):
    return [{"pos": i + 1, "id": int(p)} for i, p in enumerate(pids) if p]


def varsayilan_takimlar(k, adet=3):
    """Her yuva grubundan sahip olunan oyunculardan adet takım; ilk takım seçili kadrodur."""
    sahip = {int(p) for p in k["oyuncular"]}
    secili = [int(s["id"]) for s in sorted(k.get("secili") or [], key=lambda s: s["pos"])][:3]
    takimlar = [secili] if len(secili) == 3 else []
    kullanilan = set(sum(takimlar, []))
    while len(takimlar) < adet:
        t = []
        for yuva in (1, 2, 3):
            aday = [p for p in GRUP[yuva] if p in sahip and p not in kullanilan and p not in t]
            aday = aday or [p for p in sorted(sahip) if p not in kullanilan and p not in t]
            if aday:
                t.append(aday[0])
        kullanilan |= set(t)
        takimlar.append(t)
    return takimlar


def takim_yerlestir(takimlar, ti, pos, pid):
    """takimlar[ti][pos] = pid; pid başka bir yuvadaysa yer değiştirir. pid 0 ise yuvayı boşaltır."""
    if not (0 <= ti < len(takimlar)) or not (0 <= pos < 3):
        return
    for t in takimlar:
        while len(t) < 3:
            t.append(0)
    eski = takimlar[ti][pos]
    if pid:
        for t in takimlar:
            for i, p in enumerate(t):
                if p == pid:
                    t[i] = eski
    takimlar[ti][pos] = pid


def tam_takimlar(takimlar):
    return [[p for p in t if p] for t in takimlar if len([p for p in t if p]) == 3]


# ---------------------------------------------------------------- maç mesajı

def mesaj_kur(k, tur, biz, rakip, ozet, sahne=100, bid=0):
    """biz: [(oyuncular, amigo)], rakip: [oyuncular]; şekil mac.battlemsg ile aynı (MatchLoader.lua:32)."""
    t = k["takim"]
    return {
        "ts_begin": simdi(), "ladder_count": 0, "battle_type": int(tur), "battle_id": int(bid), "droplist_id": 0,
        "enemy_uin": int(ozet.get("uin", 0)), "scene": int(sahne or 100), "status": 1, "is_home_team": 1,
        "possession": 0, "remaining_time": 0,
        "self_hp": sum(p["attr"]["morale"] for p in biz[0][0]),
        "enemy_hp": sum(p["attr"]["morale"] for p in rakip[0]),
        "battle_player_self": [mac.dalga(o, a) for o, a in biz],
        "battle_player_enemy": [mac.dalga(d, dict(mac.BOS_AMIGO)) for d in rakip],
        "cheer_self": [biz[0][1]], "cheer_enemy": [dict(mac.BOS_AMIGO)],
        "team_level_self": int(t.get("seviye", 1)), "team_level_enemy": int(ozet.get("level", 1)),
        "team_icon_self": int(t.get("ikon", 1)), "team_icon_enemy": int(ozet.get("icon", 1)),
        "team_name_self": t.get("ad", ""), "team_name_enemy": ozet.get("name", ""),
        "skill_cd": [{"id": 0, "ts": 0} for _ in range(3)],
    }


def dusman_dalgasi(eidler):
    """data_enemy kimliklerinden takım (arena: hem bizim hem rakip oyuncular data_enemy kaydıdır)."""
    oyuncular = []
    for i, eid in enumerate(eidler):
        e = MV["dusman"].get(int(eid))
        if e is None:
            continue
        pid, seviye, degerler, enerji, enerji_hiz, beceriler = e
        oyuncular.append({
            "id": pid, "enemy_id": int(eid), "level": seviye, "break_level": 1, "color": 1, "pos": i + 1,
            "skill_list": [{"skill_id": s, "skill_level": sv} for s, sv in beceriler],
            "attr": mac.attr_json(degerler, enerji, enerji_hiz)})
    return oyuncular


# ---------------------------------------------------------------- kur

def kur(yon, durum):
    baglam = {}   # sürmekte olan maç: tur, bid, ozet, idler, tm_s, tm_e, ...
    onceki = {s: yon.protolar.get((7, s)) for s in (701, 702, 705)}

    def kayit():
        return durum.hesap_ac(durum.veri["hesap"] if durum.veri else "")

    def modlar(k):
        return k.setdefault("modlar", {})

    def isleyici(proto, *altlar, kaydet=True):
        """f(k, param) -> data sözlüğü (ya da hazır zarf); kilit altında çağrılır."""
        def sar(f):
            def cagri(param=None, **_):
                with durum.kilit:
                    k = kayit()
                    sonuc = f(k, param if isinstance(param, (dict, list)) else {})
                    if kaydet:
                        durum.kaydet()
                if isinstance(sonuc, dict) and "result" in sonuc:
                    return sonuc
                return basarili(sonuc)
            for alt in altlar:
                yon.protolar[(proto, alt)] = cagri
            return f
        return sar

    def odul_ver(k, o, idler=()):
        return mac.odul_uygula(k, o, list(idler))

    def bitis(k, tur, bid, kazandi, o, idler, ek=None, yildiz=0):
        guncel, eski, yeni = odul_ver(k, o, idler)
        msg = {"battle_type": int(tur), "battle_id": int(bid), "win": 1 if kazandi else 0, "result_star": yildiz,
               "exp": o["exp"], "gold": o["gold"], "gem": o["gem"], "star": o["star"], "exp_team": o["exp_team"],
               "item_list": mac._esya_listesi(o["esyalar"]), "player_exp_old": eski, "player_exp_new": yeni}
        data = {"battlemsg": msg, "updatelist": guncel}
        data.update(ek or {})
        return data

    def savas_baslat(k, tur, biz_takimlari, ozet, rakip, ek=None, sahne=100, bid=0):
        biz = [biz_takim(k, p) for p in biz_takimlari]
        msg = mesaj_kur(k, tur, biz, rakip, ozet, sahne, bid)
        idler = []
        for o, _ in biz:
            idler += [p["id"] for p in o if p["id"] not in idler]
        baglam.clear()
        baglam.update({"tur": tur, "bid": bid, "ozet": ozet, "idler": idler,
                       "tm_s": [[p["id"] for p in o] for o, _ in biz], "tm_e": [[p["id"] for p in d] for d in rakip]})
        baglam.update(ek or {})
        log.info("mod maçı: tür=%s rakip=%s güç=%s dalga=%d", tur, ozet.get("name"), ozet.get("strength"), len(rakip))
        return basarili({"battlemsg": msg})

    def takim_ek(k, ctx):
        return {"n_s": k["takim"].get("ad", ""), "n_e": ctx["ozet"].get("name", ""),
                "tm_s": ctx["tm_s"], "tm_e": ctx["tm_e"]}

    BASLAT, BITIR = {}, {}

    # ================================================================ 7/701, 7/702, 7/705 sarmalayıcıları
    def battle_begin(param=None, **kw):
        liste = paramlist(param) + [0, 0, 0, 0]
        tur = sayi(liste[0])
        f = BASLAT.get(tur)
        if f is None:
            baglam.clear()
            return onceki[701](param=param, **kw)
        with durum.kilit:
            return f(kayit(), sayi(liste[1]))

    def battle_begin_ex(param=None, **kw):
        cevap = onceki[705](param=param, **kw)
        baglam.clear()
        if cevap.get("result") == 0:
            msg = cevap["data"]["battlemsg"]
            if msg["battle_type"] in (3, 5):
                baglam.update({"tur": msg["battle_type"], "bid": msg["battle_id"], "dusus": msg["droplist_id"]})
        return cevap

    def battle_over(param=None, **kw):
        liste = paramlist(param) + [0] * 8
        ctx = dict(baglam)
        baglam.clear()
        f = BITIR.get(ctx.get("tur"))
        if f is None:
            cevap = onceki[702](param=param, **kw)
            if cevap.get("result") == 0 and cevap["data"]["battlemsg"].get("battle_type") == 14:
                cevap["data"]["act_trial"] = {"trial_count": 0}
            return cevap
        kazandi = sayi(liste[0]) == 1
        with durum.kilit:
            k = kayit()
            data = f(k, ctx, kazandi, liste)
            durum.kaydet()
        log.info("mod maçı bitti: tür=%s kazandı=%s", ctx.get("tur"), kazandi)
        return basarili(data)

    yon.protolar[(7, 701)] = battle_begin
    yon.protolar[(7, 702)] = battle_over
    yon.protolar[(7, 705)] = battle_begin_ex

    # ================================================================ Deneme (Trial) 10
    def deneme_json():
        liste = []
        for tur, _limit in MD["deneme"]["ayar"]:
            win = [{"level": lv, "win": len((MV["mac"].get(bid) or [0, 0, 0, [0]])[3])}
                   for lv, bid, _ in MD["deneme"]["seviye"].get(tur, [])]
            liste.append({"type": tur, "ts": 0, "count": 0, "win": win})
        return {"trial": {"trial_count": liste}}

    def deneme_mac(tur, seviye):
        for lv, bid, _ in MD["deneme"]["seviye"].get(tur, []):
            if lv == seviye:
                return bid
        return 0

    isleyici(10, 1000, 1001, 1002, 1003, 1004, kaydet=False)(lambda k, p: deneme_json())

    @isleyici(10, 1005, kaydet=False)
    def deneme_supur(k, param):
        tur, seviye = (paramlist(param) + [0, 0])[:2]
        bid = deneme_mac(sayi(tur), sayi(seviye))
        baglam.clear()
        baglam.update({"tur": 5, "bid": bid, "supurme": True})
        return deneme_json()

    def deneme_bitir(k, ctx, kazandi, liste):
        bid = ctx.get("bid", 0)
        n = len((MV["mac"].get(bid) or [0, 0, 0, [0]])[3]) or 1
        kazanilan = n if (ctx.get("supurme") or kazandi) else sinirla(sayi(liste[2]), 0, n)
        o = dusus(MD["deneme"]["dusus"].get(bid, {}).get(kazanilan)) if kazanilan else odul()
        return bitis(k, 5, bid, kazanilan > 0, o, ctx.get("idler") or [p["id"] for p in biz_takim(k)[0]])

    BITIR[5] = deneme_bitir

    # ================================================================ Lig / parça bölümleri 47
    def lig_json():
        return {"league": {"stage_list": [
            {"stage_id": sid, "stage_status": 2,
             "battle_list": [{"battle_index": i, "battle_status": 1, "count": 0, "supply_times": 0} for i, _, _ in maclar]}
            for sid, maclar in MD["lig"]]}}

    isleyici(47, 4700, 4701, 4702, 4703, kaydet=False)(lambda k, p: lig_json())

    @isleyici(47, 4704)
    def lig_supur(k, param):
        p = param if isinstance(param, dict) else {}
        bid = 0
        for sid, maclar in MD["lig"]:
            if sid == sayi(p.get("stage")):
                bid = next((b for i, b, _ in maclar if i == sayi(p.get("battle_index"))), 0)
        adet = sinirla(sayi(p.get("count"), 1), 1, 50)
        oduller = [dusus((MV["mac"].get(bid) or [0, 0, 0])[2]) for _ in range(adet)]
        guncel = odul_ver(k, mac.odul_topla(oduller), [p_["id"] for p_ in biz_takim(k)[0]])[0]
        data = lig_json()
        data["resultlist"] = [{"gold": o["gold"], "gem": o["gem"], "star": o["star"], "exp": o["exp"],
                               "exp_team": o["exp_team"], "item_list": mac._esya_listesi(o["esyalar"])}
                              for o in oduller]
        data["updatelist"] = guncel
        return data

    # ================================================================ Canlı yayın 8 / Özel antrenman 60
    isleyici(8, *range(800, 807), kaydet=False)(lambda k, p: {"live_show": {
        "status": 1, "count": 0, "cd": 0, "ts": 0, "enemy_list": [], "chests": []}})
    isleyici(60, 6003, 6004, 6005, kaydet=False)(lambda k, p: {"act_trial": {"trial_count": 0}})

    def nitelik_artir(alt):
        """PanPlayerInfo: data.qualifiy.lv / lvTime / skillLv (resmi tablo OBB'de yok; seviye 4, beceri 10 tavan)."""
        @isleyici(60, alt)
        def f(k, param):
            pid = str(sayi((paramlist(param) + [0])[0]))
            d = modlar(k).setdefault("nitelik", {}).setdefault(pid, [1, 0])
            if alt == 6001:
                d[0] = min(d[0] + 1, 4)
            else:
                d[1] = min(d[1] + 1, 10)
            return {"qualifiy": {"lv": d[0], "lvTime": 0, "skillLv": d[1]}}

    nitelik_artir(6001)
    nitelik_artir(6002)

    # ================================================================ Aranan (Wanted) 24
    def aranan_durum(k):
        return modlar(k).setdefault("aranan", {"kazanma": 0, "tohum": 1})

    def aranan_odul(guc):
        for lo, hi, b in MD["aranan"]["odul"]:
            if lo <= guc <= hi:
                return b
        return MD["aranan"]["odul"][-1][2]

    def aranan_listesi(k):
        w = aranan_durum(k)
        p = takim_gucu(k)
        liste = []
        for i in range(3):
            no = 100000 + w["tohum"] * 3 + i
            oz = ai_ozet(no, p * (0.75 + 0.15 * i), 70 + 10 * i)
            oz["bounty"] = aranan_odul(oz["strength"]) * (i + 1)
            liste.append(oz)
        return liste

    def aranan_json(k):
        w = aranan_durum(k)
        return {"wanted": {"status": 1, "count": w["kazanma"] % max(1, MD["aranan"]["gunluk"]), "combo": 0,
                           "ts_begin": simdi(), "ts_last_battle": 0, "last_enemy": 0, "cd": 0,
                           "enemy_list": [{"uin": e["uin"], "icon": e["icon"], "name": e["name"],
                                           "strength": e["strength"], "level": e["level"], "bounty": e["bounty"]}
                                          for e in aranan_listesi(k)]}}

    isleyici(24, 2400, 2401, kaydet=False)(lambda k, p: aranan_json(k))

    def aranan_baslat(k, uin):
        liste = aranan_listesi(k)
        oz = next((e for e in liste if e["uin"] == uin), liste[0])
        dalga = ai_dalgalar(oz["id"], oz["strength"], oz["level"])
        return savas_baslat(k, 8, [None], oz, dalga, {"bounty": oz["bounty"]})

    def aranan_bitir(k, ctx, kazandi, liste):
        if kazandi:
            w = aranan_durum(k)
            w["kazanma"] += 1
            w["tohum"] += 1
            o = odul(gold=ctx.get("bounty", 0), exp=300, exp_team=100)
        else:
            o = odul(gold=1000)
        return bitis(k, 8, 0, kazandi, o, ctx["idler"])

    BASLAT[8], BITIR[8] = aranan_baslat, aranan_bitir

    # ================================================================ Sıralama (Ladder) 21
    def merdiven(k):
        l = modlar(k).setdefault("merdiven", {})
        l.setdefault("r", MERDIVEN_BASLANGIC)
        l.setdefault("rh", l["r"])
        for ad, v in (("c", 0), ("ta", 0), ("yer", {}), ("log", []), ("en_l", [])):
            l.setdefault(ad, v)
        if not l.get("takim") or len(l["takim"]) != 3:
            l["takim"] = varsayilan_takimlar(k, 1)[0]
        if not l.get("dc"):
            l["dc"] = int((k.get("secili_amigolar") or sorted(MV["amigo"]) or [0])[0])
        return l

    def m_carpan(sira):
        return 0.5 + 0.8 * (1 - math.log(sira) / math.log(MERDIVEN_N + 1))

    def m_seviye(sira):
        return max(20, 100 - (sira - 1) * 80 // MERDIVEN_N)

    def m_ai(k, l, sira, guc=None):
        no = int(l["yer"].get(str(sira), sira))
        guc = takim_gucu(k, l["takim"]) if guc is None else guc
        return ai_ozet(no, guc * m_carpan(sira), m_seviye(sira))

    def m_kendi(k, l, guc=None):
        t = k["takim"]
        return {"uin": int(k.get("uin", 0)), "id": 0, "name": t.get("ad", ""), "icon": int(t.get("ikon", 1)),
                "level": int(t.get("seviye", 1)), "strength": int(takim_gucu(k, l["takim"]) if guc is None else guc)}

    def m_sira_bul(l, no):
        for sira, v in l["yer"].items():
            if int(v) == no:
                return int(sira)
        if str(no) not in l["yer"] and no != l["r"] and 1 <= no <= MERDIVEN_N:
            return no
        return None

    def m_rakip_siralari(r):
        if r <= 5:
            return [s for s in range(1, 6) if s != r]
        adim = max(1, r // 10)
        return [max(1, r - adim * i) for i in range(1, 5)]

    def merdiven_json(k):
        l = merdiven(k)
        guc = takim_gucu(k, l["takim"])
        r = l["r"]
        el = [{"r": s, "e": m_ai(k, l, s, guc)} for s in sorted(set(m_rakip_siralari(r)))]
        top = [{"r": s, "e": m_kendi(k, l, guc) if s == r else m_ai(k, l, s, guc)} for s in (1, 2, 3)]
        pl = plist(l["takim"])
        return {"ladder": {"st": 0, "c": l["c"], "cb": l["c"], "ts": 0, "r": r, "rh": l["rh"], "cd": 0, "ts_n": 0,
                           "ta": l["ta"], "el": el, "top": top, "en_l": list(l["en_l"]),
                           "tl": [{"index": 1, "status": 1, "plist": pl}],
                           "dl": [{"plist": pl, "fight": guc}], "dc": l["dc"]}}

    def m_takim_cevap(k):
        l = merdiven(k)
        data = merdiven_json(k)
        data["team"] = {"team_list": {"plist": plist(l["takim"]), "cheer": l["dc"],
                                      "fight": data["ladder"]["dl"][0]["fight"]}}
        return data

    isleyici(21, 2103, 2105, 2107, kaydet=False)(lambda k, p: merdiven_json(k))
    isleyici(21, 2101, kaydet=False)(lambda k, p: {"ladder_list": merdiven_json(k)["ladder"]["el"]})
    isleyici(21, 2106, kaydet=False)(lambda k, p: {"log": list(merdiven(k)["log"])})

    @isleyici(21, 2102, kaydet=False)
    def m_uin_bilgi(k, param):
        uin = sayi((paramlist(param) + [0])[0])
        l = merdiven(k)
        if uin == int(k.get("uin", 0)) or uin < AI_UIN:
            oz, sira = m_kendi(k, l), l["r"]
            oyuncular = biz_takim(k, l["takim"])[0]
            amigo = {"id": l["dc"], "level": 50, "gears": 6}
        else:
            no = uin - AI_UIN
            sira = m_sira_bul(l, no) or min(MERDIVEN_N, l["r"] + 1)
            oz = m_ai(k, l, sira)
            oz["uin"] = uin
            oyuncular = ai_dalgalar(oz["id"], oz["strength"], oz["level"])[0]
            amigo = ai_amigo(oz["id"])
        e = dict(oz)
        e["players"] = [{"team": [oyuncu_ozet(p) for p in oyuncular], "strength": oz["strength"]}]
        e["cheers"] = [amigo]
        return {"ladder_uin_info": {"r": sira, "e": e, "ec": len(l["en_l"])}}

    @isleyici(21, 2104, 2113)
    def m_takim(k, param):
        liste = paramlist(param)
        l = merdiven(k)
        if len(liste) >= 2:
            pos, pid = sayi(liste[0]), sayi(liste[1])
            if str(pid) in k["oyuncular"]:
                t = [list(l["takim"])]
                takim_yerlestir(t, 0, pos - 1, pid)
                l["takim"] = [p for p in t[0] if p] if len([p for p in t[0] if p]) == 3 else l["takim"]
        elif len(liste) == 1 and sayi(liste[0]):
            l["dc"] = sayi(liste[0])
        return m_takim_cevap(k)

    def m_liste(k, anahtar):
        l = merdiven(k)
        guc = takim_gucu(k, l["takim"])
        kendi = m_kendi(k, l, guc)
        aday = [m_ai(k, l, s, guc) for s in range(1, 61) if s != l["r"]] + [kendi]
        aday.sort(key=lambda e: (-e[anahtar], e["uin"] != kendi["uin"]))
        return {"ladder_list": [{"id": i + 1, "uin": e["uin"], "name": e["name"], "strength": e["strength"],
                                 "level": e["level"], "icon": e["icon"]} for i, e in enumerate(aday[:50])]}

    isleyici(21, 2108, kaydet=False)(lambda k, p: m_liste(k, "strength"))
    isleyici(21, 2109, kaydet=False)(lambda k, p: m_liste(k, "level"))

    @isleyici(21, 2110)
    def m_gorev(k, param):
        gid = sayi((paramlist(param) + [0])[0])
        l = merdiven(k)
        satir = next((g for g in MD["merdiven"]["gorev"] if g[0] == gid), None)
        data = {}
        if satir and gid > l["ta"]:
            l["ta"] = gid
            data["updatelist"] = odul_ver(k, dusus(satir[2]))[0]
        data.update(merdiven_json(k))
        return data

    @isleyici(21, 2111)
    def m_tesvik(k, param):
        uin = sayi((paramlist(param) + [0])[0])
        l = merdiven(k)
        if uin and uin not in l["en_l"]:
            l["en_l"].append(uin)
        data = merdiven_json(k)
        data["updatelist"] = odul_ver(k, odul(gold=MD["merdiven"]["tesvik"]))[0]
        return data

    def m_kazan(k, l, rakip_sira, rakip):
        eski = l["r"]
        if rakip_sira and rakip_sira < eski:
            l["yer"][str(eski)] = int(l["yer"].get(str(rakip_sira), rakip_sira))
            l["yer"].pop(str(rakip_sira), None)
            l["r"] = rakip_sira
            l["rh"] = min(l["rh"], rakip_sira)
        return eski

    def m_log(k, l, rakip, eski, kazandi):
        l["log"].insert(0, {"u": int(k.get("uin", 0)), "uc": rakip["uin"], "n": k["takim"].get("ad", ""),
                            "nc": rakip["name"], "r": eski, "rc": l["r"] if kazandi else rakip.get("sira", 0),
                            "re": 1 if kazandi else 0, "ts": simdi()})
        del l["log"][20:]

    @isleyici(21, 2112)
    def m_supur(k, param):
        l = merdiven(k)
        sira = min(m_rakip_siralari(l["r"]))
        rakip = m_ai(k, l, sira)
        rakip["sira"] = sira
        eski = m_kazan(k, l, sira, rakip)
        m_log(k, l, rakip, eski, True)
        l["c"] += 1
        data = merdiven_json(k)
        data["updatelist"] = odul_ver(k, odul(gold=20000, gem=10, exp=300, exp_team=100),
                                      [p["id"] for p in biz_takim(k, l["takim"])[0]])[0]
        return data

    def m_baslat(k, uin):
        l = merdiven(k)
        sira = m_sira_bul(l, uin - AI_UIN) if uin >= AI_UIN else None
        if sira is None:
            sira = min(m_rakip_siralari(l["r"]), key=lambda s: abs(s - l["r"]))
        oz = m_ai(k, l, sira)
        oz["sira"] = sira
        dalga = ai_dalgalar(oz["id"], oz["strength"], oz["level"])
        return savas_baslat(k, 7, [l["takim"]], oz, dalga, {"sira": sira})

    def m_bitir(k, ctx, kazandi, liste):
        l = merdiven(k)
        oz = dict(ctx["ozet"])
        sira = ctx.get("sira") or oz.get("sira", 0)
        eski = l["r"]
        if kazandi:
            m_kazan(k, l, sira, oz)
        m_log(k, l, oz, eski, kazandi)
        l["c"] += 1
        o = odul(gold=20000, gem=10, exp=300, exp_team=100) if kazandi else odul(gold=2000, exp=50)
        rakip_yeni = eski if (kazandi and sira < eski) else sira
        ek = {"ladder": dict(takim_ek(k, ctx), rk=[l["r"], rakip_yeni, eski - l["r"]])}
        return bitis(k, 7, 0, kazandi, o, ctx["idler"], ek)

    BASLAT[7], BITIR[7] = m_baslat, m_bitir

    # ================================================================ Usta maçı (Master) 52
    def usta(k):
        m = modlar(k).setdefault("usta", {})
        for ad, v in (("sr", 0), ("com", 0), ("ta", 0), ("tohum", 1)):
            m.setdefault(ad, v)
        if not m.get("takimlar"):
            m["takimlar"] = varsayilan_takimlar(k, 3)
        if not m.get("cl"):
            m["cl"] = int((k.get("secili_amigolar") or sorted(MV["amigo"]) or [0])[0])
        return m

    def u_guc(k, m):
        return sum(takim_gucu(k, t) for t in tam_takimlar(m["takimlar"])) or takim_gucu(k)

    def u_rakipler(k, m, guc=None):
        guc = u_guc(k, m) if guc is None else guc
        liste = []
        for d, (puan, alt, ust) in enumerate(MD["usta"]["kural"], 1):
            no = 300000 + m["tohum"] * 10 + d
            rnd = random.Random(no)
            oz = ai_ozet(no, guc * rnd.uniform(alt, ust) / 100.0, 100 - d * 4)
            oz["id"] = d
            oz["no"] = no
            liste.append((oz, puan))
        return liste

    def u_sira(m):
        return 1 + sum(1 for i in range(1, 51) if 4000 - i * 75 > m["sr"])

    def usta_json(k):
        m = usta(k)
        guc = u_guc(k, m)
        an = simdi()
        el = []
        for oz, puan in u_rakipler(k, m, guc):
            e = {a: oz[a] for a in ("uin", "icon", "name", "strength", "id", "level")}
            el.append({"e": e, "sa": puan})
        tl = []
        for i, t in enumerate(m["takimlar"]):
            dolu = [p for p in t if p]
            tl.append({"index": i + 1, "status": 1, "str": takim_gucu(k, dolu) if len(dolu) == 3 else 0,
                       "plist": [{"pos": j + 1, "id": int(p)} for j, p in enumerate(t) if p]})
        sahne = MD["usta"]["sahne"] or [100]
        return {"master_battle": {"ta": m["ta"], "st_cd": 1, "ro": 1, "sc": sahne[0], "sc_l": sahne[1 % len(sahne)],
                                  "str": guc, "sr": m["sr"], "r": u_sira(m), "com": m["com"],
                                  "ts_le": an + 86400, "ts_lbl": an + 2 * 86400, "ts_r": 0, "cb": 0, "el": el,
                                  "cl": [{"id": m["cl"], "level": 50, "gears": 6}], "tl": tl}}

    isleyici(52, 5203, kaydet=False)(lambda k, p: usta_json(k))

    @isleyici(52, 5204)
    def u_takim(k, param):
        liste = paramlist(param) + [0, 0, 0]
        ti, pos, pid = (sayi(x) for x in liste[:3])
        m = usta(k)
        if pid == 0 or str(pid) in k["oyuncular"]:
            takim_yerlestir(m["takimlar"], ti - 1, pos - 1, pid)
        return usta_json(k)

    @isleyici(52, 5212)
    def u_amigo(k, param):
        cid = sayi((paramlist(param) + [0])[0])
        if cid:
            usta(k)["cl"] = cid
        return usta_json(k)

    @isleyici(52, 5205)
    def u_yenile(k, param):
        usta(k)["tohum"] += 1
        return usta_json(k)

    @isleyici(52, 5210)
    def u_gorev(k, param):
        gid = sayi((paramlist(param) + [0])[0])
        m = usta(k)
        satir = next((g for g in MD["usta"]["gorev"] if g[0] == gid), None)
        data = usta_json(k)
        if satir and gid > m["ta"]:
            m["ta"] = gid
            data["updatelist"] = odul_ver(k, dusus(satir[2]))[0]
            data["master_battle"]["ta"] = gid
        return data

    @isleyici(52, 5213, kaydet=False)
    def u_puanlar(k, param):
        m = usta(k)
        guc = u_guc(k, m)
        liste = [dict(ai_ozet(500000 + i, guc * (1.3 - i * 0.012), 100 - i // 2), score=4000 - i * 75)
                 for i in range(1, 51)]
        t = k["takim"]
        liste.append({"uin": int(k.get("uin", 0)), "name": t.get("ad", ""), "icon": int(t.get("ikon", 1)),
                      "level": int(t.get("seviye", 1)), "strength": guc, "score": m["sr"]})
        liste.sort(key=lambda e: -e["score"])
        return {"master_list": [{"id": i + 1, "icon": e["icon"], "name": e["name"], "strength": e["strength"],
                                 "level": e["level"], "score": e["score"]} for i, e in enumerate(liste[:50])],
                "r": u_sira(m)}

    @isleyici(52, 5214, kaydet=False)
    def u_rakip_bilgi(k, param):
        uin = sayi((paramlist(param) + [0])[0])
        m = usta(k)
        for oz, _ in u_rakipler(k, m):
            if oz["uin"] == uin:
                oyuncular = ai_dalgalar(oz["no"], oz["strength"], oz["level"])[0]
                return {"players": [oyuncu_ozet(p) for p in oyuncular], "cheers": [ai_amigo(oz["no"])]}
        return {"players": [], "cheers": []}

    @isleyici(52, 5215, kaydet=False)
    def u_sampiyonlar(k, param):
        sahne = MD["usta"]["sahne"] or [100]
        an = simdi()
        return {"ch": [{"sc": sahne[i % len(sahne)], "lv": 100, "v": 10, "n": ai_adi(600000 + i),
                        "str": int(u_guc(k, usta(k)) * 1.2), "i": IKONLAR[i % len(IKONLAR)],
                        "ts": an - (i + 1) * 7 * 86400} for i in range(10)]}

    def u_baslat(k, uin):
        m = usta(k)
        rakipler = u_rakipler(k, m)
        oz, puan = next(((o, p) for o, p in rakipler if o["uin"] == uin), rakipler[len(rakipler) // 2])
        takimlar = tam_takimlar(m["takimlar"]) or [None]
        dalga = ai_dalgalar(oz["no"], oz["strength"], oz["level"], len(takimlar))
        return savas_baslat(k, 12, takimlar, oz, dalga, {"puan": puan})

    def u_bitir(k, ctx, kazandi, liste):
        m = usta(k)
        if kazandi:
            m["com"] += 1
            seri = MD["usta"]["seri"]
            ek_puan = seri.get(min(m["com"], max(seri) if seri else 0), 0)
            alinan = ctx.get("puan", 0)
            m["sr"] += alinan + ek_puan
            m["tohum"] += 1
            o = odul(gold=15000, gem=10, exp=300, exp_team=100)
        else:
            ek_puan, alinan = 0, -min(m["sr"], MD["usta"]["kayip"])
            m["sr"] += alinan
            m["com"] = 0
            o = odul(gold=1500, exp=50)
        ek = {"master": dict(takim_ek(k, ctx), sa=[m["sr"], alinan, m["com"], ek_puan])}
        return bitis(k, 12, 0, kazandi, o, ctx["idler"], ek)

    BASLAT[12], BITIR[12] = u_baslat, u_bitir

    # ================================================================ Açık turnuva 2059
    P = 2059
    DUGUM = {i: (tur, nid) for i, tur, nid in MD["acik"]["dugum"]}
    SON_DUGUM = max(DUGUM) if DUGUM else 30

    def acik(k):
        o = modlar(k).setdefault("acik", {})
        for ad, v in (("st", 1), ("stsh", 0), ("ta", 0), ("f", 0), ("gs", 0), ("chl", {}), ("tohum", 1),
                      ("rcr", 0)):
            o.setdefault(ad, v)
        if not o.get("tl"):
            o["tl"] = varsayilan_takimlar(k, 3)
        if not o.get("kilit") or len(o["kilit"]) != len(o["tl"]):
            o["kilit"] = [1] * len(o["tl"])
        if not o.get("cl") or len(o["cl"]) != len(o["tl"]):
            amigolar = [int(a) for a in (k.get("secili_amigolar") or [])] + sorted(MV["amigo"])
            o["cl"] = (amigolar * 3)[:len(o["tl"])]
        return o

    def a_rakipler(k, o, guc=None):
        tur, nid = DUGUM.get(o["st"], (0, 0))
        if tur != 1:
            return []
        guc = sum(takim_gucu(k, t) for t in tam_takimlar(o["tl"])) if guc is None else guc
        s = MD["acik"]["savas"].get(nid)
        liste = []
        for d in range(1, 4):
            no = 400000 + o["tohum"] * 10 + d
            carpan = (s[4 + 2 * d] + s[5 + 2 * d]) / 2.0 if s else 0.5 + 0.1 * d
            oz = ai_ozet(no, guc * carpan, 60 + nid * 2 + d * 3)
            oz["no"] = no
            oz["id"] = d
            oz["fan"] = s[2 * (d - 1)] if s else 10
            oz["shot"] = s[2 * (d - 1) + 1] if s else 3
            liste.append(oz)
        return liste

    def a_destek(o):
        tur, nid = DUGUM.get(o["st"], (0, 0))
        havuz = MD["acik"]["destek"].get(nid, []) if tur == 3 else []
        rnd = random.Random(o["tohum"] * 31 + o["st"])
        sl = []
        for seviye in sorted({h[0] for h in havuz}):
            satirlar = [h for h in havuz if h[0] == seviye]
            eid = secim(rnd, [h[1] for h in satirlar], [h[2] for h in satirlar])
            alt, ust = MD["acik"]["destek_deger"].get("%d_%d" % (eid, seviye), [0, 0])
            sl.append({"eid": eid, "level": seviye, "value": int(rnd.randint(int(alt), int(max(alt, ust)))),
                       "teamindex": 0})
        return sl

    def acik_json(k):
        o = acik(k)
        tl, guc = [], 0
        for i, t in enumerate(o["tl"]):
            dolu = [p for p in t if p]
            g = takim_gucu(k, dolu) if len(dolu) == 3 else 0
            if o["kilit"][i] and g:
                guc += g
            tl.append({"index": i + 1, "status": 3 if o["kilit"][i] else 1, "str": g,
                       "plist": [{"pos": j + 1, "id": int(p)} for j, p in enumerate(t) if p]})
        el = [{"e": {a: oz[a] for a in ("id", "uin", "name", "strength", "icon", "level")}}
              for oz in a_rakipler(k, o, guc)]
        chl = []
        for adim, adet in sorted(o["chl"].items(), key=lambda x: int(x[0])):
            tur, nid = DUGUM.get(int(adim), (0, 0))
            chl.append({"nid": nid, "ce": int(adet)})
        return {"open_match": {
            "st": o["st"], "stsh": o["stsh"], "ta": o["ta"], "ft": 0, "f": o["f"], "gs": o["gs"], "eu": 0,
            "rcr": o["rcr"], "til": [], "tilt": [], "el": el,
            "hle": [{"i": 1, "hc": 100, "hm": 100}],
            "hl": [{"i": i + 1, "hc": 100, "hm": 100} for i in range(len(o["tl"]))],
            "tl": tl, "cl": [{"id": int(c), "level": 50, "gears": 6} for c in o["cl"]],
            "sl": a_destek(o), "se": [], "chl": chl}}

    isleyici(P, 205901, 205906, 205907, 205908, 205909, 205915, kaydet=False)(lambda k, p: acik_json(k))

    @isleyici(P, 205902, 5204)
    def a_takim(k, param):
        liste = paramlist(param) + [0, 0, 0]
        ti, pos, pid = (sayi(x) for x in liste[:3])
        o = acik(k)
        if pid == 0 or str(pid) in k["oyuncular"]:
            takim_yerlestir(o["tl"], ti - 1, pos - 1, pid)
        return acik_json(k)

    @isleyici(P, 205911)
    def a_amigo(k, param):
        liste = paramlist(param) + [0, 0]
        o = acik(k)
        ti, cid = sayi(liste[0]), sayi(liste[1])
        if 1 <= ti <= len(o["cl"]) and cid:
            o["cl"][ti - 1] = cid
        return acik_json(k)

    @isleyici(P, 205912)
    def a_kilitle(k, param):
        liste = paramlist(param) + [0] * 5
        o = acik(k)
        ti = sayi(liste[0])
        pids = [sayi(x) for x in liste[1:4]]
        if 1 <= ti <= len(o["tl"]) and all(str(p) in k["oyuncular"] for p in pids):
            for pos, pid in enumerate(pids):
                takim_yerlestir(o["tl"], ti - 1, pos, pid)
            if sayi(liste[4]):
                o["cl"][ti - 1] = sayi(liste[4])
            o["kilit"][ti - 1] = 1
        return acik_json(k)

    @isleyici(P, 205916, kaydet=False)
    def a_guc(k, param):
        pids = [sayi(x) for x in (paramlist(param) + [0, 0, 0])[:3] if sayi(x)]
        return {"str": takim_gucu(k, pids) if pids else 0}

    @isleyici(P, 205914)
    def a_degistir(k, param):
        liste = paramlist(param) + [0, 0]
        a, b = sayi(liste[0]) - 1, sayi(liste[1]) - 1
        o = acik(k)
        if 0 <= a < len(o["tl"]) and 0 <= b < len(o["tl"]):
            for ad in ("tl", "kilit", "cl"):
                o[ad][a], o[ad][b] = o[ad][b], o[ad][a]
        return acik_json(k)

    def a_ilerle(o, adim):
        if o["st"] == adim and o["st"] < SON_DUGUM:
            o["st"] += 1
            o["tohum"] += 1

    def a_sandik(k, param, ek):
        adim = sayi((paramlist(param) + [0])[0])
        o = acik(k)
        tur, nid = DUGUM.get(adim, (0, 0))
        data = {}
        if tur in (2, 4) and adim <= o["st"]:
            seviye = int(k["takim"].get("seviye", 1))
            satirlar = [s for s in MD["acik"]["sandik"] if s[0] == (nid or max(r[0] for r in MD["acik"]["sandik"]))]
            satir = next((s for s in satirlar if s[1] <= seviye <= s[2]), satirlar[-1] if satirlar else None)
            if satir:
                data["updatelist"] = odul_ver(k, dusus(satir[4 if ek else 3]))[0]
            o["chl"][str(adim)] = int(o["chl"].get(str(adim), 0)) + 1
            a_ilerle(o, adim)
        data.update(acik_json(k))
        data.setdefault("updatelist", {"op_flag": 1, "paramlist": {}})
        return data

    isleyici(P, 205903)(lambda k, p: a_sandik(k, p, False))
    isleyici(P, 205904)(lambda k, p: a_sandik(k, p, True))

    @isleyici(P, 205905)
    def a_destek_sec(k, param):
        o = acik(k)
        if DUGUM.get(o["st"], (0, 0))[0] == 3:
            a_ilerle(o, o["st"])
        return acik_json(k)

    @isleyici(P, 205910)
    def a_gorev(k, param):
        gid = sayi((paramlist(param) + [0])[0])
        o = acik(k)
        satir = next((g for g in MD["acik"]["gorev"] if g[0] == gid), None)
        data = {}
        if satir and gid > o["ta"]:
            o["ta"] = gid
            data["updatelist"] = odul_ver(k, dusus(satir[2]))[0]
        data.update(acik_json(k))
        return data

    @isleyici(P, 205913)
    def a_adim(k, param):
        acik(k)["stsh"] = sayi((paramlist(param) + [0])[0])
        return acik_json(k)

    @isleyici(P, 205917)
    def a_sifirla(k, param):
        o = acik(k)
        rcr = o["rcr"] + 1
        tl, kilit, cl = o["tl"], o["kilit"], o["cl"]
        o.clear()
        o.update({"rcr": rcr, "tl": tl, "kilit": kilit, "cl": cl})
        return acik_json(k)

    def a_baslat(k, uin):
        o = acik(k)
        takimlar = [t for i, t in enumerate(o["tl"]) if o["kilit"][i] and len([p for p in t if p]) == 3]
        takimlar = [[p for p in t if p] for t in takimlar] or tam_takimlar(o["tl"]) or [None]
        guc = sum(takim_gucu(k, t) for t in takimlar if t)
        rakipler = a_rakipler(k, o, guc)
        if not rakipler:   # savaş düğümünde değil: bir sonraki savaşın rakibini kullan
            st = o["st"]
            o["st"] = next((i for i in sorted(DUGUM) if i >= st and DUGUM[i][0] == 1), 1)
            rakipler = a_rakipler(k, o, guc)
            o["st"] = st
        oz = next((r for r in rakipler if r["uin"] == uin), rakipler[0])
        dalga = ai_dalgalar(oz["no"], oz["strength"], oz["level"], len(takimlar))
        return savas_baslat(k, 13, takimlar, oz, dalga, {"fan": oz["fan"], "shot": oz["shot"], "adim": o["st"]})

    def a_bitir(k, ctx, kazandi, liste):
        o = acik(k)
        if kazandi:
            f, s = ctx.get("fan", 10), ctx.get("shot", 3)
            o["f"] += f
            o["gs"] += s
            a_ilerle(o, ctx.get("adim", o["st"]))
            od = odul(gold=10000, exp=200, exp_team=80)
        else:
            f, s = -min(o["f"], ctx.get("fan", 10) // 2), 0
            o["f"] += f
            od = odul(gold=1000)
        return bitis(k, 13, 0, kazandi, od, ctx["idler"], {"open": {"f": f, "s": s}})

    BASLAT[13], BITIR[13] = a_baslat, a_bitir

    # ================================================================ Arena 32
    A = MD["arena"]
    SECIM_MAX = 9

    def arena(k):
        a = modlar(k).setdefault("arena", {})
        for ad, v in (("st", 0), ("pl", []), ("sec", []), ("c_w", 0), ("c_l", 0), ("tohum", 1)):
            a.setdefault(ad, v)
        if not a.get("tl"):
            a["tl"] = [[], [], []]
        return a

    def r_adaylar(a):
        rnd = random.Random(a["tohum"] * 7 + len(a["sec"]))
        havuz = [e for e in A["oyuncu"] if e not in a["sec"]] or list(A["oyuncu"])
        return rnd.sample(havuz, min(3, len(havuz)))

    def arena_json(k):
        a = arena(k)
        return {"arena": {"st": a["st"], "s_c": len(a["sec"]), "s_m": SECIM_MAX, "c_w": a["c_w"], "c_l": a["c_l"],
                          "pl": [{"id": e} for e in a["pl"]],
                          "tl": [{"index": i + 1, "status": 1,
                                  "plist": [{"id": e, "pos": j + 1} for j, e in enumerate(t)]}
                                 for i, t in enumerate(a["tl"])]}}

    isleyici(32, 3201, 3207, kaydet=False)(lambda k, p: arena_json(k))

    @isleyici(32, 3200)
    def r_sifirla(k, param):
        modlar(k).pop("arena", None)
        return arena_json(k)

    @isleyici(32, 3202)
    def r_gir(k, param):
        a = arena(k)
        a.update({"st": 1, "sec": [], "tl": [[], [], []], "c_w": 0, "c_l": 0, "tohum": a["tohum"] + 1})
        a["pl"] = r_adaylar(a)
        return arena_json(k)

    @isleyici(32, 3203)
    def r_sec(k, param):
        eid = sayi((paramlist(param) + [0])[0])
        a = arena(k)
        if a["st"] == 1 and eid in a["pl"]:
            a["sec"].append(eid)
            a["tl"][(len(a["sec"]) - 1) // 3].append(eid)
            if len(a["sec"]) >= SECIM_MAX:
                a["st"], a["pl"] = 2, []
            else:
                a["pl"] = r_adaylar(a)
        return arena_json(k)

    @isleyici(32, 3204)
    def r_takim(k, param):
        liste = paramlist(param) + [0, 0, 0]
        ti, pi, eid = sayi(liste[0]) - 1, sayi(liste[1]) - 1, sayi(liste[2])
        a = arena(k)
        for tf, t in enumerate(a["tl"]):
            if 0 <= pi < len(t) and t[pi] == eid and 0 <= ti < len(a["tl"]) and pi < len(a["tl"][ti]):
                t[pi], a["tl"][ti][pi] = a["tl"][ti][pi], t[pi]
                break
        return arena_json(k)

    def r_bitir_tur(k, param):
        a = arena(k)
        sandik = A["sandik"]
        dl = sandik.get(min(a["c_w"], max(sandik))) if sandik else 0
        guncel = odul_ver(k, dusus(dl))[0]
        a.update({"st": 0, "pl": [], "sec": [], "tl": [[], [], []], "c_w": 0, "c_l": 0})
        data = arena_json(k)
        data["updatelist"] = guncel
        return data

    isleyici(32, 3205, 3206)(r_bitir_tur)

    @isleyici(32, 3208, kaydet=False)
    def r_gercek_zamanli(k, param):
        return hata("HintArenaStatuErro")   # ErrorConfig: "竞技场状态错误"

    def r_baslat(k, _):
        a = arena(k)
        takimlar = [t for t in a["tl"] if len(t) == 3]
        if not takimlar:
            takimlar = [r_adaylar(a)]
        biz = [(dusman_dalgasi(t), dict(mac.BOS_AMIGO)) for t in takimlar]
        rnd = random.Random(a["tohum"] * 13 + a["c_w"] + a["c_l"])
        rakip = [dusman_dalgasi(rnd.sample(A["oyuncu"], 3)) for _ in takimlar]
        no = 700000 + a["tohum"] * 10 + a["c_w"] + a["c_l"]
        oz = ai_ozet(no, sum(p["attr"]["fight"] for d in rakip for p in d), 90)
        msg = mesaj_kur(k, 11, biz, rakip, oz)
        baglam.clear()
        baglam.update({"tur": 11, "bid": 0, "ozet": oz, "idler": []})
        return basarili({"battlemsg": msg})

    def r_bitir(k, ctx, kazandi, liste):
        a = arena(k)
        if kazandi:
            a["c_w"] += 1
        else:
            a["c_l"] += 1
        return bitis(k, 11, 0, kazandi, odul(gold=10000, exp_team=80) if kazandi else odul(gold=1000), [])

    BASLAT[11], BITIR[11] = r_baslat, r_bitir

    # ================================================================ Etkinlik sıralaması 40
    def e_liste(k, tur):
        l = merdiven(k)
        guc = takim_gucu(k, l["takim"])
        t = k["takim"]
        kendi = {"u": int(k.get("uin", 0)), "i": int(t.get("ikon", 1)), "n": t.get("ad", ""), "s": guc,
                 "l": int(t.get("seviye", 1)), "g": 0, "r": 0}
        aday = []
        for s in range(1, 31):
            e = m_ai(k, l, s, guc)
            aday.append({"u": e["uin"], "i": e["icon"], "n": e["name"], "s": e["strength"], "l": e["level"],
                         "g": int(200000 // s), "r": int(2000 // s)})
        aday.append(kendi)
        anahtar = {1: "l", 2: "s", 3: "g"}.get(tur, "s")
        aday.sort(key=lambda e: (-e[anahtar], e["u"] != kendi["u"]))
        for i, e in enumerate(aday):
            e["t"] = i + 1
        return aday[:30]

    isleyici(40, 4001, kaydet=False)(lambda k, p: {"rank_list": e_liste(k, sayi((paramlist(p) + [2])[0]))})
    isleyici(40, 4004, 4005, kaydet=False)(lambda k, p: {"gem": 0, "rmb": 0})

    @isleyici(40, 4002)
    def e_odul(k, param):
        tur = sayi((paramlist(param) + [2])[0])
        sira = next((e["t"] for e in e_liste(k, tur) if e["u"] == int(k.get("uin", 0))), 0)
        esyalar = {}
        for alt, ust, eid, adet in MD["sira_odul"].get(tur, []):
            if alt <= sira <= ust:
                esyalar[eid] = adet
        guncel = odul_ver(k, odul(esyalar=esyalar))[0]
        durumlar = modlar(k).setdefault("etkinlik_sira", {"sl": 0, "ss": 0, "sr": 0})
        durumlar[{1: "sl", 2: "ss"}.get(tur, "sr")] = 1
        return {"updatelist": guncel, "ars": dict(durumlar)}

    # ================================================================ Sokak macerası (Reward match) 14
    RM = MD["rm"]
    RM_SAVAS = {r[0]: r for r in RM["savas"]}
    AKSIYON = RM["aksiyon"]

    def rm(k):
        r = modlar(k).setdefault("rm", {})
        for ad, v in (("status", 0), ("level", 0), ("fee", 0), ("fee_temp", 0), ("fee_battle", 0), ("hp", 3),
                      ("hpmax", 3), ("combo", 0), ("select_count", 0), ("select_total", AKSIYON), ("kartlar", []),
                      ("index", 0), ("bag", {}), ("combomax", {}), ("levelcount", {}), ("fee_history", 0),
                      ("history_reward", 0), ("forward", 0), ("savas", -1), ("settlement", []), ("bekleyen", {})):
            r.setdefault(ad, v)
        return r

    def rm_sinir(fee):
        alt = (max(0, fee) // 1000) * 1000
        return alt, alt + 1000

    def rm_json(k):
        r = rm(k)
        savas = next((c for c in r["kartlar"] if c["index"] == r["savas"]), None)
        alt, ust = rm_sinir(r["fee_temp"])
        return {"reward_match": {
            "a_o": 0, "cm": 0, "dc": 0, "dc_b": 99, "dc_bd": 0, "ts": simdi(), "fee": r["fee"],
            "fee_temp": r["fee_temp"], "fee_battle": r["fee_battle"], "status": r["status"], "status_chest": 0,
            "battle_id": RM_SAVAS[savas["id"]][1] if savas and savas["id"] in RM_SAVAS else 0,
            "battle_count": r["combo"], "battle_scene": 1, "battle_scene_list": [], "combo": r["combo"],
            "combo_temp": 0, "dis_slot": 0, "level": r["level"], "levelmax": max(RM["zorluk"] or [0]),
            "hp": r["hp"], "hpmax": r["hpmax"], "chests_cost": alt, "chests_rankup": ust, "chests_item": [],
            "bag_item": [{"id": int(e), "count": int(a), "type": 0} for e, a in r["bag"].items()],
            "slot_list": [], "card_list": [dict(c) for c in r["kartlar"]], "card_list_hid": [], "buff_list": [],
            "combomax": [{"level": z, "max": int(r["combomax"].get(str(z), 0))} for z in RM["zorluk"]],
            "levelcount": [{"level": z, "max": int(r["levelcount"].get(str(z), 0))} for z in RM["zorluk"]],
            "reward_team": [], "select_index": 0, "select_total": r["select_total"], "sweep": 99,
            "forward": r["forward"], "max_index": r["index"], "max_index_buff": 0, "select_count": r["select_count"],
            "chests_action": AKSIYON, "select_count_max": AKSIYON, "settlement": [dict(s) for s in r["settlement"]],
            "fee_history": r["fee_history"], "history_reward": r["history_reward"], "rd": 1}}

    def rm_yenile(k, r):
        rnd = random.Random(r["index"] * 7919 + r["select_count"] + simdi())
        harita1 = [i for i, t in RM["harita"].items() if t == 1]
        harita2 = [i for i, t in RM["harita"].items() if t == 2]
        kartlar = []
        for m in rnd.sample(harita1, min(2, len(harita1))):
            s = rnd.choice(RM["savas"])
            r["index"] += 1
            kartlar.append({"index": r["index"], "id": s[0], "type": 2, "map_index": m, "ap": int(s[4])})
        seviye = int(k["takim"].get("seviye", 1))
        esyalar = [e for e in RM["esya"] if e[4] <= seviye <= e[5]] or RM["esya"]
        if esyalar and harita2:
            e = secim(rnd, esyalar, [x[6] for x in esyalar])
            r["index"] += 1
            kartlar.append({"index": r["index"], "id": e[0], "type": 3, "map_index": rnd.choice(harita2), "ap": 0})
        r["kartlar"] = kartlar

    def rm_bitir_tur(k, r):
        """Tur sonu: status 3, kalan maceracı parasına göre hesaplaşma listesi (istemci gösterir, clear ile verilir)."""
        r["status"] = 3
        r["savas"] = -1
        dl = next((d for lo, hi, d in RM["hesap"] if lo <= r["fee_temp"] <= hi), RM["hesap"][-1][2] if RM["hesap"] else 0)
        o = dusus(dl) if r["fee_temp"] > 0 else odul()
        r["bekleyen"] = {a: o[a] for a in BOS_ODUL}
        r["bekleyen"]["esyalar"] = {str(e): a for e, a in o["esyalar"].items()}
        r["settlement"] = [{"id": int(e), "count": int(a), "type": 1} for e, a in o["esyalar"].items()]

    def rm_aksiyon(k, r):
        r["select_total"] -= 1
        r["select_count"] += 1
        if r["select_total"] <= 0 or r["hp"] <= 0:
            rm_bitir_tur(k, r)
        else:
            rm_yenile(k, r)

    def rm_savas_sonu(k, r, kazandi):
        kart = next((c for c in r["kartlar"] if c["index"] == r["savas"]), None)
        ucret = RM_SAVAS.get(kart["id"], [0, 0, 0])[2] if kart else 0
        z = str(r["level"])
        if kazandi:
            r["fee_temp"] += ucret
            r["fee_battle"] = ucret
            r["combo"] += 1
            r["combomax"][z] = max(int(r["combomax"].get(z, 0)), r["combo"])
        else:
            r["hp"] -= 1
            r["fee_battle"] = 0
            r["combo"] = 0
        r["levelcount"][z] = int(r["levelcount"].get(z, 0)) + 1
        r["status"] = 1
        r["savas"] = -1
        rm_aksiyon(k, r)

    def rm_islem(k, op, liste):
        r = rm(k)
        if op == "enter":
            if r["status"] == 0:
                r.update({"status": 1, "level": sinirla(sayi(liste[0]), 0, max(RM["zorluk"] or [0])), "hp": 3,
                          "hpmax": 3, "combo": 0, "fee_temp": 0, "fee_battle": 0, "select_total": AKSIYON,
                          "select_count": 0, "bag": {}, "settlement": [], "bekleyen": {}, "savas": -1})
                rm_yenile(k, r)
        elif op == "select" and r["status"] == 1:
            kart = next((c for c in r["kartlar"] if c["index"] == sayi(liste[0])), None)
            if kart and kart["type"] == 2:
                r["status"] = 2
                r["savas"] = kart["index"]
            elif kart and kart["type"] == 3:
                e = next((x for x in RM["esya"] if x[0] == kart["id"]), None)
                if e:
                    adet = e[2] * (2 if sayi((liste + [1, 1])[1]) == 2 else 1)
                    odul_ver(k, odul(esyalar={e[1]: adet}))
                    r["bag"][str(e[1])] = int(r["bag"].get(str(e[1]), 0)) + adet
                rm_aksiyon(k, r)
        elif op == "battle_result" and r["status"] == 2:
            rm_savas_sonu(k, r, sayi(liste[0]) == 1)
        elif op == "forward" and r["status"] in (1, 2):
            kart = next((c for c in r["kartlar"] if c["index"] == sayi(liste[0]) and c["type"] == 2), None)
            if kart:
                eski = r["fee_temp"]
                r["savas"] = kart["index"]
                bid = RM_SAVAS.get(kart["id"], [0, 0])[1]
                r["forward"] += 1
                rm_savas_sonu(k, r, True)
                baglam.clear()
                baglam.update({"tur": 3, "bid": bid, "dusus": (MV["mac"].get(bid) or [0, 0, 0])[2], "supurme": True,
                               "eski": eski, "yeni": r["fee_temp"]})
        elif op == "leave" and r["status"] in (1, 2):
            rm_bitir_tur(k, r)
        elif op == "clear":
            if r["status"] == 3:
                b = r.get("bekleyen") or {}
                o = odul(**{a: int(b.get(a, 0)) for a in BOS_ODUL})
                o["esyalar"] = {int(e): int(a) for e, a in (b.get("esyalar") or {}).items()}
                odul_ver(k, o)
                r["fee"] += r["fee_temp"]
                r["fee_history"] += r["fee_temp"]
            r.update({"status": 0, "fee_temp": 0, "fee_battle": 0, "kartlar": [], "settlement": [], "bekleyen": {},
                      "savas": -1, "combo": 0, "bag": {}})
        elif op == "reward":
            hid = sayi(liste[0])
            satir = next((g for g in RM["gecmis"] if g[0] == hid), None)
            if satir and hid > r["history_reward"]:
                r["history_reward"] = hid
                return dict(rm_json(k), updatelist=odul_ver(k, dusus(satir[2]))[0])
        elif op == "reset":
            modlar(k).pop("rm", None)
        return rm_json(k)

    RM_ALT = {1400: "reset", 1401: "get_info", 1402: "enter", 1403: "leave", 1404: "select", 1405: "battle_result",
              1406: "clear", 1407: "add_ticket", 1408: "forward", 1409: "add_ticket", 1410: "reward"}
    for alt, op in RM_ALT.items():
        isleyici(14, alt)(lambda k, p, op=op: rm_islem(k, op, paramlist(p) + [0, 0]))

    def op_rewardmatch(alanlar=None, param=None, **_):
        op = (alanlar or {}).get("op", "get_info")
        with durum.kilit:
            k = kayit()
            data = rm_islem(k, op, paramlist(param) + [0, 0])
            durum.kaydet()
        return basarili(data)

    yon.yollar["/op_rewardmatch"] = op_rewardmatch

    def rm_mac_bitir(k, ctx, kazandi, liste):
        r = rm(k)
        if ctx.get("supurme"):
            eski, yeni, kazandi = ctx.get("eski", 0), ctx.get("yeni", 0), True
        else:
            kart = next((c for c in r["kartlar"] if c["index"] == r["savas"]), None)
            eski = r["fee_temp"]
            yeni = eski + (RM_SAVAS.get(kart["id"], [0, 0, 0])[2] if (kart and kazandi) else 0)
        e_alt, e_ust = rm_sinir(eski)
        y_alt, y_ust = rm_sinir(yeni)
        o = dusus(ctx.get("dusus")) if kazandi else odul()
        ek = {"rm": [eski, e_alt, e_ust, yeni, y_alt, y_ust, r["level"]]}
        return bitis(k, 3, ctx.get("bid", 0), kazandi, o, [p["id"] for p in biz_takim(k)[0]], ek)

    BITIR[3] = rm_mac_bitir

    return baglam
