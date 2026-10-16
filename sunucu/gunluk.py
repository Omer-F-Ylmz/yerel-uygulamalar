"""Günlük ve meta özellikler: imza, enerji, görevler, posta, çevrimiçi ödül, etkinlikler, CDK ve ödeme.

Her ödül gerçekten kayda işlenir (mac.odul_uygula) ve cevaptaki "updatelist" ile istemciye bildirilir;
istemci bunu Luahttp.OnResponse -> Execut_Update ile her ekranda otomatik uygular. Satın alma ve
"ücretli" etkinlikler ücretsizdir: her ödeme isteği başarılı sayılır, ürün anında verilir.

Kayıtta tutulanlar (durum.veri["gunluk"]):
  gun / ay            son günlük / aylık sıfırlamanın tarihi
  aylik               aylık imza: sayi (imzalanan gün), son (zaman damgası), son_gun, odul (alınan kümülatif sıra no)
  yedi                yedi günlük imza: sayi, son_gun
  gorev / gunluk_gorev  ödülü alınmış görevler (günlük görevler her gün sıfırlanır)
  buyume_odul         büyüme görevleri toplam ödülü alındı mı (0/1)
  online              bugün alınan çevrimiçi ödül sıra numaraları
  bedava_enerji       bugün alınan bedava enerji dilimleri (1-4)
  kart_gun / yuce_gun   ay kartı / yüce ay kartı ödülünün son alındığı gün
  ilk_odeme, sarj0, sarj1, fon, harika, fragman   etkinlik ödül durumları
  posta, posta_sira   gelen kutusu
  siparis             ödeme: bill_no -> ürün kimliği

Kullanım (sunucu.py, esya.kur'dan sonra):  import gunluk; gunluk.kur(yon, durum)
"""
import json
import logging
import os
import random
import time

from cekirdek import basarili, hata, param_coz
from durum import ESYA_VERI, OYUNCU_VERI
import mac

log = logging.getLogger("sunucu")
KOK = os.path.dirname(os.path.abspath(__file__))

GUNLUK_BEKLEME = False   # True: imzalar gerçek oyundaki gibi günde bir; False: tüm günler hemen imzalanabilir
HARIKA_AZAMI = 12        # açılacak "精彩活动" görev etkinliği sayısı (veri dosyasındaki sırayla)
ENERJI_SINIRI = 99999
GUN = 86400
BEDAVA_ENERJI_DILIM = {1: 9, 2: 10, 3: 13, 4: 18}  # Window_BuyStamina.strengthTimeList -> StrengthConfig id
SATIN_ALMA_ENERJISI = 120                           # StrengthBuyCostConfig.addStrength
REKLAM_ELMASI = 50
FON_ODULU = 1000
YUCE_KART_ODULU = 300
CDK_ODULU = {"gem": 1000, "gold": 100000, "star": 1000}
SARJ0_ETKINLIK = 10003

# Açılan etkinlikler (ActivityBaseInfo): 10001 aylık imza, 10002 ay kartı, 10003/10004 şarj etkinlikleri,
# 10007 ilk şarj, 10011 çevrimiçi ödül, 10012 büyüme görevleri, 10013 yedi günlük imza, 10014 şarj girişi
ETKINLIKLER = [10001, 10002, 10003, 10004, 10007, 10011, 10012, 10013, 10014]


def _veri_yukle(yol=os.path.join(KOK, "veri", "gunluk_verisi.json")):
    """araclar/gunluk_verisi_cikar.py çıktısı."""
    with open(yol, encoding="utf-8") as f:
        v = json.load(f)
    v["gorev"] = {int(k): g for k, g in v["gorev"].items()}
    v["dusus"] = {int(k): d for k, d in v["dusus"].items()}
    v["enerji"] = {int(k): d for k, d in v["enerji"].items()}
    v["fragman"] = {int(k): d for k, d in v["fragman"].items()}
    v["super"] = {int(k): d for k, d in v["super"].items()}
    v["iki_hafta_kume"] = set(v["iki_hafta"])
    v["sonraki"] = {}  # önkoşul görev -> onu bekleyen görevler (MissionBaseInfo.preShowID)
    for gid, g in v["gorev"].items():
        if g[3] > 1:
            v["sonraki"].setdefault(g[3], []).append(gid)
    return v


V = _veri_yukle()


# ---------------------------------------------------------------- yardımcılar

def simdi():
    return int(time.time())


def bugun():
    return time.strftime("%Y-%m-%d")


def bu_ay():
    return time.strftime("%Y-%m")


def sayi(x, varsayilan=0):
    try:
        return int(x)
    except (TypeError, ValueError):
        return varsayilan


def paramlist(param):
    """{"paramlist":[a,b]} / {"paramlist":a} / [a] / a -> [a, b] (sayıya çevrilir)."""
    if isinstance(param, dict):
        param = param.get("paramlist", [])
    if not isinstance(param, list):
        param = [param]
    return [sayi(x) for x in param]


def bos_odul():
    return {"exp": 0, "exp_team": 0, "gold": 0, "gem": 0, "star": 0, "esyalar": {}}


def dusus_coz(dusus_id, rnd=random):
    """mac.dusus_coz ile aynı kurallar; gunluk_verisi.json'daki düşüş listelerini kullanır."""
    d = V["dusus"].get(sayi(dusus_id))
    odul = bos_odul()
    if d is None:
        return odul
    exp, exp_team, gold, gem, star, cekilis, kesin, sansli, agirlikli = d
    odul.update(exp=exp, exp_team=exp_team, gold=gold, gem=gem, star=star)

    def ekle(eid, adet):
        odul["esyalar"][eid] = odul["esyalar"].get(eid, 0) + adet

    for eid, adet in kesin:
        ekle(eid, adet)
    for eid, adet, oran in sansli:
        if rnd.random() * 10000 < oran:
            ekle(eid, adet)
    if agirlikli and cekilis > 0:
        for _ in range(cekilis):
            eid, adet, _w = rnd.choices(agirlikli, weights=[x[2] for x in agirlikli])[0]
            ekle(eid, adet)
    return odul


def odul_ver(k, dususler=(), **ek):
    """Düşüş listelerini (ve gem=/gold=/star=/esyalar= eklerini) kayda işler; updatelist döner."""
    odul = mac.odul_topla([dusus_coz(d) for d in dususler] + [bos_odul()])
    for ad in ("gold", "gem", "star", "exp_team"):
        odul[ad] += int(ek.get(ad, 0))
    for eid, adet in (ek.get("esyalar") or {}).items():
        odul["esyalar"][int(eid)] = odul["esyalar"].get(int(eid), 0) + int(adet)
    updatelist, _, _ = mac.odul_uygula(k, odul, [])
    return updatelist


def gunluk_durum(k):
    """Oyuncunun günlük durum sözlüğü; gün/ay değişince ilgili alanlar sıfırlanır."""
    st = k.setdefault("gunluk", {})
    for ad, deger in (("aylik", None), ("yedi", None), ("gorev", []), ("gunluk_gorev", []), ("buyume_odul", 0),
                      ("online", []), ("bedava_enerji", []), ("kart_gun", ""), ("yuce_gun", ""), ("ilk_odeme", 0),
                      ("sarj0", []), ("sarj1", []), ("fon", None), ("harika", []), ("fragman", None),
                      ("siparis", {}), ("reklam", 0)):
        if ad not in st:
            st[ad] = deger
    if st["aylik"] is None or st.get("ay") != bu_ay():
        st["aylik"] = {"sayi": 0, "son": 0, "son_gun": "", "odul": []}
        st["ay"] = bu_ay()
    if st["yedi"] is None:
        st["yedi"] = {"sayi": 0, "son_gun": ""}
    if st["fon"] is None:
        st["fon"] = {"is_buy": 0, "alinan": []}
    if st["fragman"] is None:
        st["fragman"] = {"1": [0, 0], "2": [0, 0]}
    if st.get("gun") != bugun():
        st["gun"] = bugun()
        st["gunluk_gorev"] = []
        st["online"] = []
        st["bedava_enerji"] = []
    return st


def bit_dizisi(alinanlar, uzunluk):
    """Sıra no i (1'den) sağdan i. karakter: istemci dizeyi sondan başa okur (GetActivityStatus vb.)."""
    return "".join("1" if i in alinanlar else "0" for i in range(uzunluk, 0, -1))


# ---------------------------------------------------------------- JSON şekilleri

def aylik_json(st):
    a = st["aylik"]
    toplam = len(V["aylik"])
    n = min(int(a["sayi"]), toplam)
    bugun_imzali = GUNLUK_BEKLEME and a.get("son_gun") == bugun()
    return {"monthchckin": {
        "month_check_status": "1" * n if n else "0",
        "month_cumulative_prize_status": bit_dizisi(set(a["odul"]), len(V["aylik_odul"])),
        "last_checkin_ts": int(a["son"]),
        "day": n,
        "if_cancheck": 1 if (bugun_imzali or n >= toplam) else 0,
    }}


def yedi_json(st):
    y = st["yedi"]
    imzalanabilir = y["sayi"] < len(V["yedi"]) and not (GUNLUK_BEKLEME and y.get("son_gun") == bugun())
    return {"seven_count": int(y["sayi"]), "can_sign": 1 if imzalanabilir else 0}


def enerji_json(k, st):
    return {"strength": {
        "strength": int(k.get("stamina", 0)), "strength_cd": 0, "today_buy_times": 0,
        # basamak i (birler=1. dilim ...) 1 ise o dilimin bedava enerjisi alınmış (Window_BuyStamina.CheckClaimStatus)
        "free_get_status": sum(10 ** (d - 1) for d in set(st["bedava_enerji"]) if 1 <= d <= 4),
        "styles_points": 30, "styles_last_update_ts": simdi(), "last_update_ts": simdi(), "cd": 0}}


def gorev_alindi(st, gid):
    tur = V["gorev"][gid][0]
    return gid in (st["gunluk_gorev"] if tur in V["gunluk_gorev_turleri"] else st["gorev"])


def buyume_sayisi(st):
    alinan = set(st["gorev"]) | set(st["gunluk_gorev"])
    return sum(1 for g in V["iki_hafta"] if g in alinan)


def gorev_gorunur(st, gid):
    """Normal görev listesine girer mi: tür 1-5, ödülü alınmamış, önkoşulu (preShowID) alınmış.
    Büyüme (iki hafta) görevleri önkoşuldan bağımsız hep gönderilir: Window_GrowthMission ödül cevabındaki
    görevleri "alındı" sayar, sonradan açılanları ancak listede baştan varlarsa gösterebilir."""
    g = V["gorev"].get(gid)
    if g is None or not 1 <= g[0] <= 5 or gorev_alindi(st, gid):
        return False
    if gid in V["iki_hafta_kume"] or g[3] <= 1 or g[3] not in V["gorev"]:
        return True
    return gorev_alindi(st, g[3])


def gorev_json(st):
    """Görevler tamamlanmış (progress1 = condition1) gönderilir; ödülü alınanlar listede yer almaz."""
    liste = [{"id": gid, "progress1": g[1]} for gid, g in V["gorev"].items() if gorev_gorunur(st, gid)]
    return {"mission": {"mission": liste, "is_gotpriaze": int(st["buyume_odul"]),
                        "complete_cnts": buyume_sayisi(st)}}


def harika_etkinlikler():
    return V["harika"][:HARIKA_AZAMI]


def harika_json(st):
    acik = set(harika_etkinlikler())
    alinan = set(st["harika"])
    return {"mission": {"mission": [{"id": gid, "progress1": g[1]} for gid, g in V["gorev"].items()
                                    if g[0] in acik and gid not in alinan]}}


def etkinlik_json():
    t = simdi()
    durumlar = []
    for aid in ETKINLIKLER + harika_etkinlikler():
        bt, et, ct = t - GUN, t + 30 * GUN, t + 30 * GUN
        if aid == 10012:
            # büyüme görevlerinin toplam ödülü ancak etkinlik bitince alınabilir (isGetReward: now > endTime)
            et = t - 60
        durumlar.append({"id": aid, "bt": bt, "et": et, "ct": ct, "lvf": 0, "lvt": 999})
    return {"activity": {"status": durumlar}}


def kart_json(st):
    return {"gem_shop": {"mcts": simdi() + 30 * GUN, "mcstas": 1, "mcprize": 1 if st["kart_gun"] == bugun() else 0,
                         "mcgem": 0, "fg": int(st["reklam"])}}


def ilk_odeme_json(st):
    return {"first_recharge": {"if_fc": 1, "if_prize": int(st["ilk_odeme"])}}


def sarj0_satirlari():
    return {gun: dusus for act, gun, dusus in V["sarj0"] if act == SARJ0_ETKINLIK}


def sarj0_json(st):
    satir = sarj0_satirlari()
    en_buyuk = max(satir) if satir else 0
    alinan = set(st["sarj0"])
    return {"id": SARJ0_ETKINLIK, "conti_recharge": {
        "status": "1" * en_buyuk if en_buyuk else "0", "prize": bit_dizisi(alinan - {0}, en_buyuk) or "0",
        "status0": 1, "prize0": 1 if 0 in alinan else 0}}


def sarj1_json(st):
    toplam = max([r[1] for r in V["sarj1"]] or [0])
    # InitActivity1Data i. satır (1'den) için prize dizesinin sağdan i. karakterini okur; satır i = id i-1
    return {"acc_recharge": {"prize": bit_dizisi({i + 1 for i in st["sarj1"]}, len(V["sarj1"])) or "0",
                             "gem": toplam}}


def fragman_json(st):
    return {"trailers": [{"type": int(t), "vote_info": int(v[0]), "res_reward": int(v[1])}
                         for t, v in sorted(st["fragman"].items())]}


def cevrimici_json(st):
    return {"online_package": {"online_time": max([r[1] for r in V["cevrimici"]] or [0]),
                               "reward_index_list": [{"index": i} for i in sorted(set(st["online"]))]}}


def yuce_kart_json(st):
    return {"supreme_month_card": {"is_buy": 1, "is_receive": 1 if st["yuce_gun"] == bugun() else 0,
                                   "player_id": int(V["super"].get(7) or min(OYUNCU_VERI)), "drop_id": 0,
                                   "end_time": simdi() + 30 * GUN}}


def fon_json(st):
    f = st["fon"]
    return {"growth_fund": {"is_buy": int(f["is_buy"]), "count": int(f["is_buy"]), "accepted": list(f["alinan"])}}


# ---------------------------------------------------------------- posta

def metin(s):
    return {"is_template": 0, "key": s, "params": []}


def posta_ekle(st, baslik, icerik, ekler):
    """ekler: [{"type": 100 (eşya) | 1 elmas | 2 altın | 3 yıldız | 5 takım deneyimi, "id": .., "count": ..}]"""
    st["posta_sira"] = int(st.get("posta_sira", 0)) + 1
    st.setdefault("posta", []).append({
        "id": st["posta_sira"], "baslik": baslik, "icerik": icerik, "zaman": simdi(),
        "okundu": 0, "ekler": ekler, "ek_durum": 1 if ekler else 0, "favori": 0})


def posta_kutusu(st):
    if "posta" not in st:
        st["posta"] = []
        ekler = [{"type": 1, "id": 1, "count": 1000}, {"type": 2, "id": 2, "count": 100000},
                 {"type": 3, "id": 3, "count": 1000}]
        ekler += [{"type": 100, "id": e, "count": 10} for e in (40046, 40018, 40001) if e in ESYA_VERI]
        posta_ekle(st, "Hos geldin!", "Yerel sunucuya hos geldin. Her sey acik ve sinirsiz, iyi oyunlar!", ekler)
    return st["posta"]


def posta_json(p):
    return {"mail_id": p["id"], "title": metin(p["baslik"]), "content": metin(p["icerik"]),
            "source_id": "0", "source_name": "Yerel Sunucu", "mail_time": p["zaman"],
            "mail_time_term": p["zaman"] + 30 * GUN, "status_read": p["okundu"], "status_attach": p["ek_durum"],
            "type": 2, "attach": p["ekler"], "status_favorite": p["favori"]}


def posta_eki_uygula(k, postalar):
    ek = {"gem": 0, "gold": 0, "star": 0, "exp_team": 0, "esyalar": {}}
    for p in postalar:
        for e in p["ekler"]:
            tur, adet = int(e["type"]), int(e["count"])
            if tur == 100:
                ek["esyalar"][int(e["id"])] = ek["esyalar"].get(int(e["id"]), 0) + adet
            else:
                ad = {1: "gem", 2: "gold", 3: "star", 5: "exp_team"}.get(tur)
                if ad:
                    ek[ad] += adet
        p["ek_durum"] = 2
        p["okundu"] = 1
    return odul_ver(k, **ek)


# ---------------------------------------------------------------- ödeme

def urun_ver(k, urun):
    tur, deger = V["urun"].get(urun, [None, 0])
    if tur == 1:
        return odul_ver(k, gem=deger)
    if tur == 0:
        return odul_ver(k, [deger])
    log.info("ödeme: tanınmayan ürün %r, ödülsüz başarılı sayıldı", urun)
    return odul_ver(k)


# ---------------------------------------------------------------- kayıt

def kur(yon, durum):
    def kayit():
        return durum.hesap_ac(durum.veri["hesap"] if durum.veri else "")

    def op_yolu(yol, islevler, varsayilan):
        def isle(alanlar, param, oturum, istek):
            f = islevler.get(alanlar.get("op", ""), varsayilan)
            with durum.kilit:
                k = kayit()
                st = gunluk_durum(k)
                cevap = f(k=k, st=st, alanlar=alanlar, param=param)
                durum.kaydet()
            return cevap
        yon.yollar[yol] = isle

    def proto_kaydet(proto, sub, f):
        def isle(alanlar, param, oturum, istek):
            with durum.kilit:
                k = kayit()
                st = gunluk_durum(k)
                cevap = f(k=k, st=st, alanlar=alanlar, param=param if param is not None else {})
                durum.kaydet()
            return cevap
        yon.protolar[(proto, sub)] = isle

    # ------------------------------------------------ aylık imza (5/501-503)
    def aylik_imza(k, st, **_):
        a = st["aylik"]
        if a["sayi"] >= len(V["aylik"]) or (GUNLUK_BEKLEME and a.get("son_gun") == bugun()):
            return hata("HintBallTeamError")
        dusus = V["aylik"][a["sayi"]][1]
        a["sayi"] += 1
        a["son"], a["son_gun"] = simdi(), bugun()
        cevap = aylik_json(st)
        cevap["updatelist"] = odul_ver(k, [dusus])
        return basarili(cevap)

    def aylik_kumulatif(k, st, param, **_):
        a = st["aylik"]
        istenen = (paramlist(param) or [0])[0]
        for i, (gerekli, dusus) in enumerate(V["aylik_odul"], 1):
            if gerekli == istenen and a["sayi"] >= gerekli and i not in a["odul"]:
                a["odul"].append(i)
                cevap = aylik_json(st)
                cevap["updatelist"] = odul_ver(k, [dusus])
                return basarili(cevap)
        return hata("HintBallTeamError")

    op_yolu("/player_month_checkin", {"monthchckin": aylik_imza, "get_cumulative_prize": aylik_kumulatif},
            lambda st, **_: basarili(aylik_json(st)))

    # ------------------------------------------------ yedi günlük imza (5/504-505)
    def yedi_imza(k, st, **_):
        y = st["yedi"]
        if not yedi_json(st)["can_sign"]:
            return hata("HintBallTeamError")
        dusus = V["yedi"][y["sayi"]][1]
        y["sayi"] += 1
        y["son_gun"] = bugun()
        cevap = yedi_json(st)
        cevap["updatelist"] = odul_ver(k, [dusus])
        return basarili(cevap)

    op_yolu("/seven", {"checkin": yedi_imza}, lambda st, **_: basarili(yedi_json(st)))

    # ------------------------------------------------ enerji (13/1301-1304)
    def enerji_ekle(k, miktar):
        k["stamina"] = min(ENERJI_SINIRI, int(k.get("stamina", 0)) + int(miktar))

    def bedava_enerji(k, st, param, **_):
        dilim = (paramlist(param) or [0])[0]
        if dilim in BEDAVA_ENERJI_DILIM and dilim not in st["bedava_enerji"]:
            st["bedava_enerji"].append(dilim)
            enerji_ekle(k, V["enerji"].get(BEDAVA_ENERJI_DILIM[dilim], 60))
        return basarili(enerji_json(k, st))

    def enerji_satin_al(k, st, **_):
        enerji_ekle(k, SATIN_ALMA_ENERJISI)  # elmas düşülmez
        return basarili(enerji_json(k, st))

    op_yolu("/player_strength", {"get_strength": bedava_enerji, "re_strength": bedava_enerji,
                                 "buy_strength": enerji_satin_al},
            lambda k, st, **_: basarili(enerji_json(k, st)))

    # ------------------------------------------------ görevler (19/1901-1902, 27/2601-2603, 38/3801)
    def gorev_odulu(k, st, param, **_):
        alinan, dususler = [], []
        for gid in paramlist(param):
            g = V["gorev"].get(gid)
            if g is None or not 1 <= g[0] <= 5 or gorev_alindi(st, gid):
                continue
            (st["gunluk_gorev"] if g[0] in V["gunluk_gorev_turleri"] else st["gorev"]).append(gid)
            alinan.append(gid)
            dususler.append(g[2])
        updatelist = odul_ver(k, dususler)
        # Window_GrowthMission/ActiveBagGiftData.setActiveTaskData(isUpdate) bu listeyi ve complete_cnts'i okur;
        # Execut_Update -> TaskDataManager.UpdateData: -1 görevi siler, yeni kayıt görevi ekler
        gorevler = [{"id": gid, "progress1": -1} for gid in alinan]
        for gid in alinan:
            if gid not in V["iki_hafta_kume"]:
                gorevler += [{"id": s, "progress1": V["gorev"][s][1]} for s in V["sonraki"].get(gid, [])
                             if s not in V["iki_hafta_kume"] and gorev_gorunur(st, s)]
        updatelist["paramlist"]["mission"] = gorevler
        return basarili({"updatelist": updatelist, "complete_cnts": buyume_sayisi(st)})

    def buyume_toplam_odul(k, st, **_):
        sayi_ = buyume_sayisi(st)
        if st["buyume_odul"] or sayi_ <= 0:
            return hata("HintBallTeamError")
        st["buyume_odul"] = 1
        _dusus, esya, sinir = V["iki_hafta_odul"]
        cevap = gorev_json(st)
        cevap["updatelist"] = odul_ver(k, esyalar={esya: min(sayi_, sinir)})
        return basarili(cevap)

    op_yolu("/player_mission", {
        "get_mission_reward": gorev_odulu,
        "get_complete_cnts_reward": buyume_toplam_odul,
        # sayı olmalı: ActiveBagGiftData.setTaskMissionDay tonumber eder; 7 = tüm günlerin sekmeleri açık
        "get_growth_mission_day": lambda **_: basarili({"growth_mission_day": 7}),
    }, lambda st, **_: basarili(gorev_json(st)))

    # ------------------------------------------------ çevrimiçi ödül (42/5001-5003)
    def cevrimici_odul(k, st, param, **_):
        i = (paramlist(param) or [0])[0]
        satir = next((r for r in V["cevrimici"] if r[0] == i), None)
        if satir is None or i in st["online"]:
            return hata("HintBallTeamError")
        st["online"].append(i)
        cevap = cevrimici_json(st)
        cevap["updatelist"] = odul_ver(k, [satir[2]])
        return basarili(cevap)

    op_yolu("/online_package", {"get_reward": cevrimici_odul}, lambda st, **_: basarili(cevrimici_json(st)))

    # ------------------------------------------------ iki hafta (26/2500) ve anket (29/2901)
    op_yolu("/two_week", {}, lambda **_: basarili({"checkin": {"2ws": 0}}))
    op_yolu("/answer", {}, lambda **_: basarili({"answer": {"status": 1}}))

    # ------------------------------------------------ elmas dükkânı: ay kartı, reklam, ilk şarj, şarj etkinlikleri
    def kart_odulu(k, st, **_):
        if st["kart_gun"] == bugun():
            return hata("HintBallTeamError")
        st["kart_gun"] = bugun()
        cevap = kart_json(st)
        cevap["updatelist"] = odul_ver(k, gem=int(V["super"].get(5, 100)))
        return basarili(cevap)

    def reklam_elmasi(k, st, **_):
        st["reklam"] = 0  # 4 saatlik bekleme yok
        updatelist = odul_ver(k, gem=REKLAM_ELMASI)
        updatelist["paramlist"].setdefault("gem", 0)  # PanMain.LookAdGetItems tonumber(paramlist.gem) okur
        cevap = kart_json(st)
        cevap["updatelist"] = updatelist
        return basarili(cevap)

    def ilk_odeme_odulu(k, st, **_):
        if st["ilk_odeme"]:
            return hata("HintBallTeamError")
        st["ilk_odeme"] = 1
        cevap = ilk_odeme_json(st)
        cevap["updatelist"] = odul_ver(k, [int(V["super"].get(8, 0))])
        return basarili(cevap)

    def sarj0_odulu(k, st, param, **_):
        gun = (paramlist(param) or [-1])[0]
        dusus = sarj0_satirlari().get(gun)
        if dusus is None or gun in st["sarj0"]:
            return hata("HintBallTeamError")
        st["sarj0"].append(gun)
        cevap = sarj0_json(st)
        cevap["updatelist"] = odul_ver(k, [dusus])
        return basarili(cevap)

    def sarj1_odulu(k, st, param, **_):
        sid = (paramlist(param) or [-1])[0]
        satir = next((r for r in V["sarj1"] if r[0] == sid), None)
        if satir is None or sid in st["sarj1"]:
            return hata("HintBallTeamError")
        st["sarj1"].append(sid)
        cevap = sarj1_json(st)
        cevap["updatelist"] = odul_ver(k, [satir[2]])
        return basarili(cevap)

    op_yolu("/gem_shop", {
        "get_card_info": lambda st, **_: basarili(kart_json(st)),
        "get_prize": kart_odulu,
        "get_free_gem": reklam_elmasi,
        "get_first_charge": lambda st, **_: basarili(ilk_odeme_json(st)),
        "get_fc_prize": ilk_odeme_odulu,
        "get_conti_charge": lambda st, **_: basarili(sarj0_json(st)),
        "get_conti_prize": sarj0_odulu,
        "get_acc_charge": lambda st, **_: basarili(sarj1_json(st)),
        "get_acc_prize": sarj1_odulu,
    }, lambda st, **_: basarili(kart_json(st)))

    # ------------------------------------------------ etkinlikler (36/3601) ve harika görevler (49/4901-4902)
    op_yolu("/activity", {"get_forcasttime_status": lambda **_: basarili({"activity": {"forcastacts": []}})},
            lambda **_: basarili(etkinlik_json()))

    def harika_odul(k, st, param, **_):
        acik = set(harika_etkinlikler())
        alinan, dususler = [], []
        for gid in paramlist(param):
            g = V["gorev"].get(gid)
            if g is None or g[0] not in acik or gid in st["harika"]:
                continue
            st["harika"].append(gid)
            alinan.append(gid)
            dususler.append(g[2])
        if not alinan:
            return hata("HintBallTeamError")
        updatelist = odul_ver(k, dususler)
        updatelist["paramlist"]["activity_mission"] = [{"id": gid, "progress1": -1} for gid in alinan]
        return basarili({"updatelist": updatelist})

    op_yolu("/activity_mission", {"get_mission_reward": harika_odul}, lambda st, **_: basarili(harika_json(st)))

    # ------------------------------------------------ fragman oylaması (46/4601-4603)
    def fragman_oy(k, st, param, **_):
        oy, tur = (paramlist(param) + [0, 0])[:2]
        kayit_ = st["fragman"].get(str(tur))
        if kayit_ is None or kayit_[0]:
            return hata("HintBallTeamError")
        kayit_[0] = max(1, oy)
        cevap = fragman_json(st)
        cevap["updatelist"] = odul_ver(k, [V["fragman"][tur][0]])
        return basarili(cevap)

    def fragman_odul(k, st, param, **_):
        _oy, tur = (paramlist(param) + [0, 0])[:2]
        kayit_ = st["fragman"].get(str(tur))
        if kayit_ is None or kayit_[1]:
            return hata("HintBallTeamError")
        kayit_[1] = 1
        cevap = fragman_json(st)
        cevap["updatelist"] = odul_ver(k, [V["fragman"][tur][1 if kayit_[0] == 1 else 2]])
        return basarili(cevap)

    op_yolu("/trailer", {"voute": fragman_oy, "res_reward": fragman_odul}, lambda st, **_: basarili(fragman_json(st)))

    # ------------------------------------------------ yüce ay kartı (68) ve büyüme fonu (67): proto_sub ile
    def yuce_kart(k, st, alanlar, **_):
        if sayi(alanlar.get("proto_sub")) == 102:
            if st["yuce_gun"] == bugun():
                return hata("HintBallTeamError")
            st["yuce_gun"] = bugun()
            cevap = yuce_kart_json(st)
            cevap["updatelist"] = odul_ver(k, gem=YUCE_KART_ODULU)
            return basarili(cevap)
        return basarili(yuce_kart_json(st))

    def buyume_fonu(k, st, alanlar, param, **_):
        sub = sayi(alanlar.get("proto_sub"))
        f = st["fon"]
        if sub == 102:
            f["is_buy"] = 1  # elmas düşülmez
        elif sub == 103:
            fid = (paramlist(param) or [0])[0]
            if not f["is_buy"] or fid <= 0 or fid in f["alinan"]:
                return hata("HintBallTeamError")
            f["alinan"].append(fid)
            cevap = fon_json(st)
            cevap["updatelist"] = odul_ver(k, gem=FON_ODULU)
            return basarili(cevap)
        return basarili(fon_json(st))

    op_yolu("/month_card", {}, yuce_kart)
    op_yolu("/growth_fund", {}, buyume_fonu)

    # ------------------------------------------------ CDK (55/5501): her kod kabul, ödül postayla gelir
    def cdk(k, st, alanlar, **_):
        kod = (alanlar.get("param") or "").strip()[:40]
        ekler = [{"type": 1, "id": 1, "count": CDK_ODULU["gem"]}, {"type": 2, "id": 2, "count": CDK_ODULU["gold"]},
                 {"type": 3, "id": 3, "count": CDK_ODULU["star"]}]
        posta_kutusu(st)
        posta_ekle(st, "Hediye kodu", "Kod: %s" % (kod or "-"), ekler)
        return basarili({})

    op_yolu("/exchange_cdkey", {}, cdk)

    # ------------------------------------------------ kayan yazı (45/4501)
    proto_kaydet(45, 4501, lambda **_: basarili({"gm_pl": [], "pl": []}))

    # ------------------------------------------------ posta (17/1700-1712)
    def okunmamis(st):
        return sum(1 for p in posta_kutusu(st) if not p["okundu"] or p["ek_durum"] == 1)

    def liste_cevabi(st, suzgec=lambda p: True):
        return basarili({"mail_title_list": [posta_json(p) for p in posta_kutusu(st) if suzgec(p)]})

    def idler(param):
        return [sayi(x) for x in (param.get("mailIDList") or [])] if isinstance(param, dict) else []

    def posta_bul(st, param):
        istenen = set(idler(param))
        return [p for p in posta_kutusu(st) if p["id"] in istenen]

    for sub in (1700, 1701):
        proto_kaydet(17, sub, lambda st, **_: liste_cevabi(st))
    for sub in (1703, 1704):
        proto_kaydet(17, sub, lambda st, **_: liste_cevabi(st, lambda p: p["favori"]))
    proto_kaydet(17, 1702, lambda st, **_: liste_cevabi(st, lambda p: p["ek_durum"] == 1))

    def posta_oku(st, param, **_):
        for p in posta_bul(st, param):
            p["okundu"] = 1
        return basarili({"mail_id_list": idler(param)})

    def posta_sil(st, param, **_):
        sil = set(idler(param))
        st["posta"] = [p for p in posta_kutusu(st) if p["id"] not in sil]
        return basarili({"mail_id_list": sorted(sil)})

    def posta_favori(st, param, **_):
        durum_ = 1 if sayi(param.get("status") if isinstance(param, dict) else 1, 1) else 0
        for p in posta_bul(st, param):
            p["favori"] = durum_
        return basarili({"mail_id_list": idler(param)})

    def posta_ek_al(k, st, param, **_):
        postalar = [p for p in posta_bul(st, param) if p["ek_durum"] == 1]
        return basarili({"mail_id_list": idler(param), "updatelist": posta_eki_uygula(k, postalar)})

    def posta_tum_ekler(k, st, **_):
        postalar = [p for p in posta_kutusu(st) if p["ek_durum"] == 1]
        return basarili({"mail_id_list": [p["id"] for p in postalar], "updatelist": posta_eki_uygula(k, postalar)})

    def posta_bilgi(st, param, **_):
        return basarili({"mail_title_list": [posta_json(p) for p in posta_bul(st, param)]})

    proto_kaydet(17, 1705, posta_oku)
    proto_kaydet(17, 1706, posta_sil)
    proto_kaydet(17, 1707, posta_favori)
    proto_kaydet(17, 1708, posta_ek_al)
    proto_kaydet(17, 1709, posta_tum_ekler)
    proto_kaydet(17, 1710, posta_bilgi)
    proto_kaydet(17, 1711, lambda st, **_: basarili({"count": okunmamis(st)}))
    proto_kaydet(17, 1712, lambda st, **_: basarili({"count": okunmamis(st)}))

    # ------------------------------------------------ ödeme: her satın alma ücretsiz ve başarılı
    def odeme_cevabi(k, bill_no, **ek):
        cevap = {"bill_no": bill_no, "gem": int(k.get("gem", 0)), "payType": "channel", "ts": simdi(),
                 "call_back_path": "", "sign": "", "accountid": "", "accessKey": "", "vivo_bill_no": bill_no,
                 "cpOrderTime": simdi(), "submit_time": simdi(), "purchaseToken": bill_no, "product_id": ""}
        cevap.update(ek)
        return basarili(cevap)

    def fatura_no(k, st, alanlar, **_):
        urun = alanlar.get("goods_id") or ""
        st["siparis_sira"] = int(st.get("siparis_sira", 0)) + 1
        bill_no = "yerel%06d" % st["siparis_sira"]
        st["siparis"][bill_no] = urun
        st["siparis"] = dict(list(st["siparis"].items())[-50:])
        updatelist = urun_ver(k, urun)
        return odeme_cevabi(k, bill_no, updatelist=updatelist)

    def siparis_sorgu(k, st, alanlar, **_):
        bill_no = alanlar.get("bill_no") or ""
        return odeme_cevabi(k, bill_no, product_id=st["siparis"].get(bill_no, ""))

    def iap(k, st, alanlar, **_):
        # iOS makbuzu: ürün bilinmiyor; isteği başarılı sayıp mevcut elması döner (補單 döngüsü kapanır)
        return odeme_cevabi(k, "", product_id=(alanlar.get("receipt") or "")[:64])

    op_yolu("/get_billno", {}, fatura_no)
    for yol in ("/query_order", "/google_buy", "/query_balance_and_buy"):
        op_yolu(yol, {}, siparis_sorgu)
    op_yolu("/iap_buy", {}, iap)
