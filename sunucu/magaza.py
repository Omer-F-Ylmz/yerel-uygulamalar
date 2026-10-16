"""Mağaza: çekilişler (Store 34), VIP (35), kara borsa (/player_shop, Shop 9), banka (34/3402),
sınırlı satış (51), takas etkinlikleri (57), resimli kitap takası (58) ve /gem_shop ekleri.

İstemci tarafı (okunan Lua dosyaları):
  StoreDataManager.InitData        store.{ce, rl, rl_y, ts, ts_p, ts_c, cp, cp_t, cc, ts_m, cm, ts_s, cs, cs_fd, ts_g, cg_fd}
  CardStage.OnReceive (3401)       store.ctpl (şans çubuğu, /1000) ve store.lk (son çekilişte eklenen şans) — yoksa Lua hatası
  CardStage.OnReceive (çekilişler) data.store + data.droplist (tekli) / data.dl (3419) + isteğe bağlı data.team
  Window_DrawResult.InitData       droplist.{player_list[{id,chip}], item_list[{id,count}], gold, gem, star,
                                   cheer_list, magic_list}; chip=0 -> yeni oyuncu, chip>0 -> oyuncu zaten var,
                                   item_list'te playerPiece x chip bulunur (PlayerCompound)
  PayDataManager.GetRl             rl / rl_y tablo olmalı (table.maxn sayıya patlar)
  DataInAdvanceManage.InitVipInfo  vip.{lv, gem, rmb, vip_package[{vip}]}; Window_VipInfo ilerleme çubuğu
                                   gem / data_vip[lv+1].recharge_gem (en üst seviyede kendi eşiği)
  ShopDataManager                  shop.{refresh_num, goods_list[{item_id,item_count,count,cost,grid,discount}],
                                   last (saat), luck, master_refresh_resttime}

Sayaç sınırları (dl_gem, dl_time, VIP banka hakkı) hiç dolmaz: ücretli çekiliş/banka/takas sayaçları 0 kalır.
Ücretsiz çekilişler oyunun kendi bekleme süreleriyle (cd_*) çalışır; günlük sıfırlama 05:00.

Kayıtta tutulanlar (durum.veri):
  magaza      {"ts_p","ts_c","ts_m","ts_s","ts_g": son ücretsiz çekiliş zamanı, "cp","cc","cm","sc","gc","tc":
               toplam çekiliş sayıları, "cg_fd": bugün kullanılan ücretsiz altın çekilişi, "ctpl": şans,
               "lk": son çekilişte eklenen şans, "ts": son 05:00 sıfırlaması}
  vip_paket   satın alınmış VIP paket seviyeleri
  kara_borsa  {"<sekme>": {"mallar": [...], "last": saat}}

Kullanım (sunucu.py, esya.kur'dan sonra):
    import magaza; magaza.kur(yon, durum)
"""
import json
import logging
import os
import random
import time

from cekirdek import basarili, hata
from durum import CANTA_TURU, ESYA_VERI, OYUNCU_VERI, full_oyuncu

log = logging.getLogger("sunucu")
KOK = os.path.dirname(os.path.abspath(__file__))

UST_SINIR = 99999999
ESYA_SINIR = 999999
SANS_TAVANI = 1000          # CardStage: Draw_luck_bar.fillAmount = ctpl / 1000
SURELI_YILDIZ_ETKINLIGI = 20023   # DrawDataManager.TimePlayerActiveId; açık değilse 3. kart "DisItem" gösterir
SURELI_YILDIZ_ACIK = True
SIFIRLAMA_SAATI = 5         # data_store_refresh / PlayerShopAutoConfig
UCRETSIZ_ELMAS = 50         # /gem_shop get_free_gem (reklam izle)


def _int_anahtar(d):
    return {int(k): v for k, v in d.items()}


def veri_yukle(yol=os.path.join(KOK, "veri", "magaza_verisi.json")):
    """araclar/magaza_verisi_cikar.py çıktısı; JSON'un metin anahtarlarını sayıya çevirir."""
    with open(yol, encoding="utf-8") as f:
        v = json.load(f)
    for ad in ("kisitli", "takas", "parca", "amigo_parca", "dusus"):
        v[ad] = _int_anahtar(v[ad])
    for tur in v["cekilis"].values():
        if isinstance(tur, dict):
            if "on" in tur:
                tur["on"] = _int_anahtar(tur["on"])
            if isinstance(tur.get("havuz"), dict):
                tur["havuz"] = _int_anahtar(tur["havuz"])
            if "rehber" in tur:
                tur["rehber"] = _int_anahtar(tur["rehber"])
    kb = v["kara_borsa"]
    kb["izgara"] = _int_anahtar(kb["izgara"])
    kb["para"] = _int_anahtar(kb["para"])
    kb["esya"] = {int(s): _int_anahtar(g) for s, g in kb["esya"].items()}
    kb["yenileme"] = {int(s): _int_anahtar(g) for s, g in kb["yenileme"].items()}
    r = v["resimli"]
    r["hedef"] = _int_anahtar(r["hedef"])
    r["maliyet"] = _int_anahtar(r["maliyet"])
    r["elmas"] = _int_anahtar(r["elmas"])
    return v


MG = veri_yukle()
AYAR = MG["cekilis"]["ayar"]


# ---------------------------------------------------------------- zaman

def simdi():
    return int(time.time())


def son_sifirlama(t=None):
    """En son yerel 05:00'ın zaman damgası (DrawDataManager.GetCanDraw0_RemainTime: ts + 86402)."""
    t = simdi() if t is None else int(t)
    y = time.localtime(t)
    bugun = int(time.mktime((y.tm_year, y.tm_mon, y.tm_mday, SIFIRLAMA_SAATI, 0, 0, 0, 0, -1)))
    return bugun if t >= bugun else bugun - 86400


# ---------------------------------------------------------------- ödül yardımcıları

def bos_odul():
    return {"gold": 0, "gem": 0, "star": 0, "esyalar": []}   # esyalar: [[id, adet], ...] (sıra korunur)


def dusus_coz(dusus_id, rnd=random):
    """data_droplist: sabit değerler + _item (kesin) + _odds (rate/10000) + _weight (weight_item_count çekiliş)."""
    odul = bos_odul()
    d = MG["dusus"].get(int(dusus_id or 0))
    if d is None:
        return odul
    _exp, _exp_team, gold, gem, star, cekilis, kesin, sansli, agirlikli = d
    odul.update(gold=gold, gem=gem, star=star)
    for eid, adet in kesin:
        odul["esyalar"].append([eid, adet])
    for eid, adet, oran in sansli:
        if rnd.random() * 10000 < oran:
            odul["esyalar"].append([eid, adet])
    if agirlikli and cekilis > 0:
        for _ in range(cekilis):
            eid, adet, _w = rnd.choices(agirlikli, weights=[x[2] for x in agirlikli])[0]
            odul["esyalar"].append([eid, adet])
    return odul


def ekle(hedef, kaynak):
    for ad in ("gold", "gem", "star"):
        hedef[ad] += kaynak[ad]
    hedef["esyalar"].extend(kaynak["esyalar"])
    return hedef


def esya_listesi(esyalar):
    return [{"id": int(e), "count": int(a)} for e, a in esyalar if a]


def kayit_uygula(k, gold=0, gem=0, star=0, esyalar=()):
    """Para ve eşya değişimlerini kayda işler (kilit altında); istemcinin Execut_Update'i için paramlist döner.

    Değerler fark olarak gider (Luahttp.Execut_Update: Gem = Gem + paramlist.gem); tavan/taban kırpılır.
    """
    param = {}
    for ad, fark in (("gold", gold), ("gem", gem), ("star", star)):
        if not fark:
            continue
        eski = int(k.get(ad, 0))
        yeni = max(0, min(UST_SINIR, eski + int(fark)))
        k[ad] = yeni
        if yeni != eski:
            param[ad] = yeni - eski
    canta = k.setdefault("canta", {})
    toplam = {}
    for eid, adet in esyalar:
        toplam[int(eid)] = toplam.get(int(eid), 0) + int(adet)
    degisen = []
    for eid, adet in toplam.items():
        bilgi = ESYA_VERI.get(eid)
        if not adet or bilgi is None or bilgi.get("tur") not in CANTA_TURU:
            continue
        eski = int(canta.get(str(eid), 0))
        yeni = max(0, min(ESYA_SINIR, eski + adet))
        if yeni != eski:
            canta[str(eid)] = yeni
            degisen.append({"id": eid, "count": yeni - eski})
    if degisen:
        param["item_list"] = degisen
    return param


def updatelist(param):
    return {"op_flag": 1, "paramlist": param}


# ---------------------------------------------------------------- çekiliş tabloları

def satir_sec(satirlar, seviye, sayac, rnd=random):
    """[lmin, lmax, dmin, dmax, dusus] satırlarından seviye+sayaca uyanı; yoksa yalnız seviyeye, yoksa herhangi biri."""
    if not satirlar:
        return 0
    uyan = [s for s in satirlar if s[0] <= seviye <= s[1] and s[2] <= sayac <= s[3]]
    if not uyan:
        uyan = [s for s in satirlar if s[0] <= seviye <= s[1]] or satirlar
    return rnd.choice(uyan)[4]


def tablo_dususleri(tur, seviye, sayac, adet, rnd=random):
    """Tekli çekiliş: 'tek' tablosundan bir düşüş. Onlu: 'on' tablosunun her yuvası + kalan yuvalar 'tek'ten."""
    t = MG["cekilis"][tur]
    odul = bos_odul()
    yuva = 0
    if adet > 1:
        for indeks in sorted(t.get("on", {})):
            if yuva >= adet:
                break
            ekle(odul, dusus_coz(satir_sec(t["on"][indeks], seviye, sayac, rnd), rnd))
            yuva += 1
    while yuva < adet:
        ekle(odul, dusus_coz(satir_sec(t.get("tek", []), seviye, sayac, rnd), rnd))
        yuva += 1
    return odul


def agirlikli_sec(liste, rnd=random):
    """[[deger, agirlik], ...] listesinden ağırlıkla seçer."""
    if not liste:
        return None
    return rnd.choices([x[0] for x in liste], weights=[max(0, x[1]) for x in liste])[0]


def havuzdan_oyuncu(havuz, yildiz, rnd=random):
    aday = havuz.get(yildiz) or [p for liste in havuz.values() for p in liste]
    return rnd.choice(aday) if aday else 0


# ---------------------------------------------------------------- kurulum

def kur(yon, durum):
    def kayit():
        return durum.hesap_ac(durum.veri["hesap"] if durum.veri else "")

    def sayi(x, varsayilan=0):
        try:
            return int(x)
        except (TypeError, ValueError):
            return varsayilan

    def paramlist(param):
        liste = (param or {}).get("paramlist") if isinstance(param, dict) else param
        if isinstance(liste, list):
            return liste
        return [] if liste is None else [liste]

    def magaza(k):
        m = k.setdefault("magaza", {})
        for ad in ("ts_p", "ts_c", "ts_m", "ts_s", "ts_g", "cp", "cc", "cm", "sc", "gc", "tc", "cg_fd", "ctpl", "lk"):
            m.setdefault(ad, 0)
        sifir = son_sifirlama()
        if m.get("ts") != sifir:
            m["ts"] = sifir
            m["cg_fd"] = 0
        return m

    def store_json(k, lk_tuket=False):
        m = magaza(k)
        lk = int(m.get("lk", 0))
        if lk_tuket:
            m["lk"] = 0
        return {
            "ce": 0,                       # banka: kullanılan hak (sınırsız)
            "rl": [], "rl_y": [],          # yükleme geçmişi; PayDataManager.GetRl / IsBuyHappyShop tablo bekler
            "ts": m["ts"],
            "ts_p": m["ts_p"], "ts_c": m["ts_c"], "ts_m": m["ts_m"], "ts_s": m["ts_s"], "ts_g": m["ts_g"],
            "cp": m["cp"], "cc": m["cc"], "cm": m["cm"],
            "cp_t": 0, "cs": 0, "cs_fd": 0,   # günlük ücretli onlu/tekli/süreli çekiliş sayıları (sınır hiç dolmaz)
            "cg_fd": m["cg_fd"],
            "ctpl": int(m["ctpl"]), "lk": lk,
        }

    def vip_seviye(k):
        enust = max(v["level"] for v in MG["vip"])
        return max(0, min(enust, sayi(k.get("vip", enust), enust)))

    def vip_json(k):
        """InitVipInfo: VipLv = lv. gem = o seviyenin eşiği (en üstte çubuk dolu görünür, 'eksik 0')."""
        lv = vip_seviye(k)
        esik = next((v["recharge_gem"] for v in MG["vip"] if v["level"] == lv), 0)
        return {"lv": lv, "gem": int(esik), "rmb": int(esik) // 10,
                "vip_package": [{"vip": int(x)} for x in sorted(set(k.get("vip_paket", [])))]}

    def takim():
        f = yon.protolar.get((12, 1201))
        if f is None:
            return None
        try:
            return f(alanlar={}, param={}, oturum=None, istek=None)["data"]["team"]
        except Exception:
            log.exception("takım bilgisi alınamadı")
            return None

    def ucretsiz_mi(m, anahtar, cd):
        """İstemci 'cd - (now - ts) - 1 <= 0' ise ücretsiz gösterir; aynı ölçüt."""
        return simdi() - int(m.get(anahtar, 0)) >= int(cd) - 1

    # ---------------- oyuncu kazanımı
    def oyuncu_ver(k, pid, chip, odul, eklenen):
        """Sahip olunmayan oyuncu kayda eklenir (chip=0); sahip olunanın yerine PlayerCompound parçası verilir."""
        pid = int(pid)
        if str(pid) not in k["oyuncular"] and pid in OYUNCU_VERI:
            k["oyuncular"][str(pid)] = full_oyuncu()
            eklenen.append(pid)
            return {"id": pid, "chip": 0}
        parca = MG["parca"].get(pid)
        chip = max(1, int(chip))
        if parca:
            odul["esyalar"].insert(0, [parca[0], chip])
        return {"id": pid, "chip": chip}

    def oyuncu_dugumu(n):
        """n. oyuncu çekilişi garanti oyuncu mu? data_store_draw_guide_player, sonra node (10->3*, 20->4*, 40->5*)."""
        t = MG["cekilis"]["oyuncu"]
        dugumler = sorted(t["dugum"], key=lambda d: -d[0])
        parca_by_yildiz = {d[1]: d[2] for d in dugumler}
        if n in t["rehber"]:
            yildiz, pid = t["rehber"][n]
            return yildiz, pid, parca_by_yildiz.get(yildiz, 15)
        for say, yildiz, chip in dugumler:
            if say > 0 and n % say == 0:
                return yildiz, 0, chip
        return None

    def cevap(k, odul, oyuncular, eklenen, maliyet, ek=None, droplist_anahtar="droplist"):
        param = kayit_uygula(k, gold=odul["gold"] + maliyet.get("gold", 0), gem=odul["gem"] + maliyet.get("gem", 0),
                             star=odul["star"] + maliyet.get("star", 0), esyalar=odul["esyalar"])
        data = {"store": store_json(k), "updatelist": updatelist(param)}
        if droplist_anahtar:
            data[droplist_anahtar] = droplist_json(odul, oyuncular)
        if ek:
            data.update(ek)
        if eklenen:
            durum.kaydet()
            t = takim()
            if t is not None:
                data["team"] = t
        return data

    def droplist_json(odul, oyuncular, **ek):
        d = {"player_list": oyuncular, "item_list": esya_listesi(odul["esyalar"]),
             "cheer_list": [], "magic_list": [],
             "gold": int(odul["gold"]), "gem": int(odul["gem"]), "star": int(odul["star"])}
        d.update(ek)
        return d

    # ---------------- 3401 bilgi
    @yon.proto(34, 3401)
    def store_bilgi(**_):
        with durum.kilit:
            k = kayit()
            data = {"store": store_json(k, lk_tuket=True)}
            durum.kaydet()
        return basarili(data)

    # ---------------- 3404/3405 oyuncu (elmas)
    def oyuncu_cekilisi(adet):
        with durum.kilit:
            k = kayit()
            m = magaza(k)
            seviye = int(k["takim"].get("seviye", 1))
            maliyet = {}
            if adet == 1 and ucretsiz_mi(m, "ts_p", AYAR["cd_player"]):
                m["ts_p"] = simdi()
            else:
                maliyet["gem"] = -int(AYAR["cost_one_player"] if adet == 1 else AYAR["cost_ten_player"])
            if -maliyet.get("gem", 0) > int(k.get("gem", 0)):
                return hata("HintNotEnoughGem")
            odul = tablo_dususleri("oyuncu", seviye, m["cp"], adet)
            odul["gold"] += int(AYAR["gold_one_player"] if adet == 1 else AYAR["gold_ten_player"])
            oyuncular, eklenen = [], []
            for _ in range(adet):
                m["cp"] += 1
                dugum = oyuncu_dugumu(m["cp"])
                if dugum:
                    yildiz, pid, chip = dugum
                    pid = pid or havuzdan_oyuncu(MG["cekilis"]["oyuncu"]["havuz"], yildiz)
                    if pid:
                        oyuncular.append(oyuncu_ver(k, pid, chip, odul, eklenen))
            data = cevap(k, odul, oyuncular, eklenen, maliyet)
            durum.kaydet()
        log.info("oyuncu çekilişi x%d: oyuncular=%s", adet, oyuncular)
        return basarili(data)

    yon.protolar[(34, 3404)] = lambda **_: oyuncu_cekilisi(1)
    yon.protolar[(34, 3405)] = lambda **_: oyuncu_cekilisi(10)

    # ---------------- 3406/3407 amigo, 3412/3413 beceri, 3414/3415 yıldız parası (eski DrawStage / ShopStage)
    def basit_cekilis(tur, adet, ts_anahtar, sayac, cd, maliyet_tek, maliyet_on, para, altin_tek, altin_on):
        with durum.kilit:
            k = kayit()
            m = magaza(k)
            seviye = int(k["takim"].get("seviye", 1))
            maliyet = {}
            if adet == 1 and ucretsiz_mi(m, ts_anahtar, AYAR[cd]):
                m[ts_anahtar] = simdi()
            else:
                maliyet[para] = -int(AYAR[maliyet_tek] if adet == 1 else AYAR[maliyet_on])
            if -maliyet.get(para, 0) > int(k.get(para, 0)):
                return hata("HintNotEnoughGem" if para == "gem" else "XingBiBuZu!")
            odul = tablo_dususleri(tur, seviye, m[sayac], adet)
            odul["gold"] += int(AYAR.get(altin_tek if adet == 1 else altin_on, 0))
            amigolar = []
            if tur == "amigo":
                t = MG["cekilis"]["amigo"]
                for i in range(adet):
                    n = m[sayac] + i + 1
                    for say, indeks, chip in sorted(t["dugum"], key=lambda d: -d[0]):
                        if say > 0 and n % say == 0 and t["havuz"]:
                            aid = random.choice(t["havuz"])
                            if str(aid) not in k.setdefault("amigolar", {}):
                                k["amigolar"][str(aid)] = 50
                                amigolar.append({"id": aid, "chip": 0})
                            else:
                                parca = MG["amigo_parca"].get(aid)
                                if parca:
                                    odul["esyalar"].insert(0, [parca[0], chip])
                                amigolar.append({"id": aid, "chip": chip})
                            break
            m[sayac] += adet
            data = cevap(k, odul, [], [], maliyet)
            data["droplist"]["cheer_list"] = amigolar
            durum.kaydet()
        return basarili(data)

    yon.protolar[(34, 3406)] = lambda **_: basit_cekilis("amigo", 1, "ts_c", "cc", "cd_cheer", "cost_one_cheer",
                                                         "cost_ten_cheer", "gem", "gold_one_cheer", "gold_ten_cheer")
    yon.protolar[(34, 3407)] = lambda **_: basit_cekilis("amigo", 10, "ts_c", "cc", "cd_cheer", "cost_one_cheer",
                                                         "cost_ten_cheer", "gem", "gold_one_cheer", "gold_ten_cheer")
    yon.protolar[(34, 3412)] = lambda **_: basit_cekilis("beceri", 1, "ts_m", "cm", "cd_magic", "cost_one_magic",
                                                         "cost_ten_magic", "gem", "gold_one_magic", "gold_ten_magic")
    yon.protolar[(34, 3413)] = lambda **_: basit_cekilis("beceri", 10, "ts_m", "cm", "cd_magic", "cost_one_magic",
                                                         "cost_ten_magic", "gem", "gold_one_magic", "gold_ten_magic")
    yon.protolar[(34, 3414)] = lambda **_: basit_cekilis("yildiz", 1, "ts_s", "sc", "cd_star", "cost_one_star",
                                                         "cost_ten_star", "star", "gold_one_star", "gold_ten_star")
    yon.protolar[(34, 3415)] = lambda **_: basit_cekilis("yildiz", 10, "ts_s", "sc", "cd_star", "cost_one_star",
                                                         "cost_ten_star", "star", "gold_one_star", "gold_ten_star")

    # ---------------- 3416/3417 oyuncu parçası (altın / "Token")
    def altin_cekilisi(adet):
        with durum.kilit:
            k = kayit()
            m = magaza(k)
            seviye = int(k["takim"].get("seviye", 1))
            maliyet = {}
            if (adet == 1 and m["cg_fd"] < int(AYAR["limit_gold_free_daily"])
                    and ucretsiz_mi(m, "ts_g", AYAR["cd_gold"])):
                m["cg_fd"] += 1
                m["ts_g"] = simdi()
            else:
                maliyet["gold"] = -int(AYAR["cost_one_gold"] if adet == 1 else AYAR["cost_ten_gold"])
            if -maliyet.get("gold", 0) > int(k.get("gold", 0)):
                return hata("JieQiuBiBuZu")
            odul = tablo_dususleri("altin", seviye, m["gc"], adet)
            t = MG["cekilis"]["altin"]
            for _ in range(adet):
                parca = agirlikli_sec(t["parca"])
                if parca:
                    odul["esyalar"].append([parca, agirlikli_sec(t["parca_adet"]) or 1])
            odul["esyalar"].insert(0, [int(AYAR["gold_reward_itemid"]),
                                       int(AYAR["gold_one_itemcount"] if adet == 1 else AYAR["gold_ten_itemcount"])])
            m["gc"] += adet
            data = cevap(k, odul, [], [], maliyet)
            durum.kaydet()
        return basarili(data)

    yon.protolar[(34, 3416)] = lambda **_: altin_cekilisi(1)
    yon.protolar[(34, 3417)] = lambda **_: altin_cekilisi(10)

    # ---------------- 3418/3419 süreli yıldız (Window_DrawTimeResult)
    def sureli_cekilis(adet):
        with durum.kilit:
            k = kayit()
            m = magaza(k)
            seviye = int(k["takim"].get("seviye", 1))
            gem = int(AYAR["cost_one_time_player"] if adet == 1 else AYAR["cost_combo_time_player"])
            if gem > int(k.get("gem", 0)):
                return hata("HintNotEnoughGem")
            t = MG["cekilis"]["sureli"]
            toplam = bos_odul()
            dusus_listesi, eklenen = [], []
            m["lk"] = 0
            altin_her = int(AYAR["gold_one_time_player"]) if adet == 1 else int(AYAR["gold_combo_time_player"]) // adet
            for _ in range(adet):
                m["tc"] += 1
                odul = dusus_coz(satir_sec(t["tek"], seviye, m["tc"]))
                odul["gold"] += altin_her
                oyuncular = []
                sans = int(agirlikli_sec(t["sans"]) or 0)
                m["lk"] += sans
                m["ctpl"] = int(m["ctpl"]) + sans
                if m["ctpl"] >= SANS_TAVANI:
                    m["ctpl"] -= SANS_TAVANI
                    oyuncular.append(oyuncu_ver(k, int(AYAR["time_player_id"]), int(AYAR["time_player_chip"]),
                                                odul, eklenen))
                for say, yildiz, chip in sorted(t["dugum"], key=lambda d: -d[0]):
                    if say > 0 and m["tc"] % say == 0:
                        pid = havuzdan_oyuncu(t["havuz"], yildiz)
                        if pid:
                            oyuncular.append(oyuncu_ver(k, pid, chip, odul, eklenen))
                        break
                dusus_listesi.append(droplist_json(odul, oyuncular))
                ekle(toplam, odul)
            ek = {"droplist": dusus_listesi[0]} if adet == 1 else {"dl": dusus_listesi}
            data = cevap(k, toplam, [], eklenen, {"gem": -gem}, ek=ek, droplist_anahtar=None)
            durum.kaydet()
        return basarili(data)

    yon.protolar[(34, 3418)] = lambda **_: sureli_cekilis(1)
    yon.protolar[(34, 3419)] = lambda **_: sureli_cekilis(6)

    # ---------------- 3402 banka (elmas -> altın)
    @yon.proto(34, 3402)
    def banka(param, **_):
        b = MG["banka"]
        tur = sayi((paramlist(param) or [1])[0], 1)
        ce = 0
        kademe = next((x for x in b["kademe"] if x[0] <= ce + 1 <= x[1]), b["kademe"][0])
        adet = 1 if tur == 1 else max(1, kademe[1] - ce)
        f = b["formul"]
        liste, altin = [], 0
        for _ in range(adet):
            taban = int(f.get("param_base", 25000)) + ce * int(f.get("param_increment", 0))
            yuzde = random.randint(int(f.get("percent_min", 100)), int(f.get("percent_max", 100)))
            kat = int(agirlikli_sec(b["kritik"]) or 1)
            g = taban * yuzde // 100 * kat
            liste.append({"g": g, "t": kat})
            altin += g
        with durum.kilit:
            k = kayit()
            gem = kademe[2] * adet
            if gem > int(k.get("gem", 0)):
                return hata("HintNotEnoughGem")
            param = kayit_uygula(k, gold=altin, gem=-gem)
            data = {"store": store_json(k), "exchangelist": liste, "updatelist": updatelist(param)}
            durum.kaydet()
        return basarili(data)

    # ---------------- 3408 test yüklemesi (PayStage.SetPayTestRequest)
    @yon.proto(34, 3408)
    def yukleme(param, **_):
        indeks = sayi((paramlist(param) or [0])[0])
        satir = next((y for y in MG["yukleme"] if y["index"] == indeks), None)
        with durum.kilit:
            k = kayit()
            p = kayit_uygula(k, gem=int(satir["gem"]) if satir else 0)
            data = {"vip": vip_json(k), "store": store_json(k), "updatelist": updatelist(p)}
            durum.kaydet()
        return basarili(data)

    def kisitli_liste():
        """Bugünün sınırlı satış ürünleri (data_restriction_product.day döngüsü); alınan sayısı hep 0 (sınırsız)."""
        gunler = sorted({u[4] for u in MG["kisitli"].values()})
        if not gunler:
            return []
        gun = gunler[(son_sifirlama() // 86400) % len(gunler)]
        return [{"i": i, "c": 0} for i in sorted(MG["kisitli"]) if MG["kisitli"][i][4] == gun]

    def kisitli_bilgi(**_):
        return basarili({"restriction": {"pl": kisitli_liste()}})

    yon.protolar[(34, 3403)] = kisitli_bilgi
    yon.protolar[(51, 5101)] = kisitli_bilgi

    @yon.proto(51, 5102)
    def kisitli_al(param, **_):
        urun = MG["kisitli"].get(sayi((paramlist(param) or [0])[0]))
        if urun is None:
            return hata("HintBallTeamError")
        dusus, gem = urun[0], urun[1]
        with durum.kilit:
            k = kayit()
            if gem > int(k.get("gem", 0)):
                return hata("HintNotEnoughGem")
            odul = dusus_coz(dusus)
            p = kayit_uygula(k, gold=odul["gold"], gem=odul["gem"] - gem, star=odul["star"], esyalar=odul["esyalar"])
            durum.kaydet()
        return basarili({"restriction": {"pl": kisitli_liste()}, "updatelist": updatelist(p)})

    # ---------------- VIP
    @yon.proto(35, 3501)
    def vip_bilgi(**_):
        return basarili({"vip": vip_json(kayit())})

    @yon.proto(35, 3502)
    def vip_paket(param, **_):
        lv = sayi((param or {}).get("vip"))
        satir = next((v for v in MG["vip"] if v["level"] == lv), None)
        with durum.kilit:
            k = kayit()
            alinan = k.setdefault("vip_paket", [])
            if satir is None or lv > vip_seviye(k) or lv in alinan:
                return hata("HintBallTeamError")
            if int(satir["vip_package_gem"]) > int(k.get("gem", 0)):
                return hata("HintNotEnoughGem")
            odul = dusus_coz(satir["vip_package"])
            p = kayit_uygula(k, gold=odul["gold"], gem=odul["gem"] - int(satir["vip_package_gem"]),
                             star=odul["star"], esyalar=odul["esyalar"])
            alinan.append(lv)
            data = {"vip": vip_json(k), "updatelist": updatelist(p)}
            durum.kaydet()
        return basarili(data)

    # ---------------- kara borsa (/player_shop, Shop 9)
    def mallari_uret(sekme, rnd=random):
        kb = MG["kara_borsa"]
        izgaralar = kb["esya"].get(sekme, {})
        mallar = []
        for grid in range(1, int(kb["izgara"].get(sekme, len(izgaralar))) + 1):
            secenek = izgaralar.get(grid)
            if not secenek:
                continue
            eid, adet, fiyat, _ = rnd.choices(secenek, weights=[s[3] for s in secenek])[0]
            mallar.append({"item_id": eid, "item_count": adet, "count": adet, "cost": fiyat,
                           "grid": grid, "discount": 100})
        return mallar

    def dukkan(k, sekme, yenile=False):
        kb = k.setdefault("kara_borsa", {})
        d = kb.get(str(sekme))
        sifir = son_sifirlama()
        if yenile or d is None or d.get("ts") != sifir:
            d = {"mallar": mallari_uret(sekme), "ts": sifir}
            kb[str(sekme)] = d
        return d

    def dukkan_json(d):
        return {"shop": {"refresh_num": 0, "goods_list": d["mallar"], "luck": 0,
                         "last": time.localtime().tm_hour,
                         "master_refresh_resttime": son_sifirlama() + 86400}}

    def kb_sekme(param):
        return sayi((paramlist(param) or [2])[0], 2) or 2

    def kb_getir(param, **_):
        with durum.kilit:
            k = kayit()
            d = dukkan(k, kb_sekme(param))
            durum.kaydet()
            return basarili(dukkan_json(d))

    def kb_yenile(param, **_):
        sekme = kb_sekme(param)
        with durum.kilit:
            k = kayit()
            d = dukkan(k, sekme, yenile=True)
            # refresh_num hep 0: sonraki yenileme de 1. yenilemenin ücretini (genelde 0) ister
            ucret = int(MG["kara_borsa"]["yenileme"].get(sekme, {}).get(1, 0))
            p = kayit_uygula(k, gem=-min(ucret, int(k.get("gem", 0))))
            data = dukkan_json(d)
            data["updatelist"] = updatelist(p)
            durum.kaydet()
            return basarili(data)

    def kb_al(param, **_):
        liste = paramlist(param)
        sekme = sayi(liste[0], 2) if liste else 2
        grid = sayi(liste[1]) if len(liste) > 1 else 0
        with durum.kilit:
            k = kayit()
            d = dukkan(k, sekme)
            mal = next((x for x in d["mallar"] if x["grid"] == grid), None)
            if mal is None or not mal["item_count"]:
                return hata("HintBallTeamError")
            para_id, ek_tur = MG["kara_borsa"]["para"].get(sekme, [3, 3])
            if ek_tur == 3:          # yıldız parası
                if int(k.get("star", 0)) < mal["cost"]:
                    return hata("XingBiBuZu!")
                p = kayit_uygula(k, star=-mal["cost"], esyalar=[[mal["item_id"], mal["count"]]])
            else:                    # eşya parası (sıralama/ustalar/lonca/açık turnuva); eksikse var olan kadar düşülür
                eldeki = int(k.get("canta", {}).get(str(para_id), 0))
                p = kayit_uygula(k, esyalar=[[para_id, -min(eldeki, mal["cost"])], [mal["item_id"], mal["count"]]])
            mal["item_count"] = 0
            data = dukkan_json(d)
            data["updatelist"] = updatelist(p)
            durum.kaydet()
            return basarili(data)

    kb_islev = {"get_shop": kb_getir, "auto_refresh": kb_getir, "manual_refresh": kb_yenile, "buy": kb_al}

    def player_shop(alanlar, param, oturum=None, istek=None):
        f = kb_islev.get(alanlar.get("op", ""), kb_getir)
        return f(param=param)

    yon.yollar["/player_shop"] = player_shop
    yon.protolar[(9, 901)] = lambda param=None, **_: kb_getir(param)
    yon.protolar[(9, 902)] = lambda param=None, **_: kb_getir(param)
    yon.protolar[(9, 903)] = lambda param=None, **_: kb_al(param)

    # ---------------- 57 takas etkinlikleri
    def takas_json(aid):
        return {"a": {"aid": aid, "ts": son_sifirlama(),
                      "el": [{"i": eid, "c": 0} for eid, v in sorted(MG["takas"].items()) if v["aid"] == aid]}}

    def takas_bilgi(param, **_):
        return basarili(takas_json(sayi((paramlist(param) or [0])[0])))

    yon.protolar[(57, 5703)] = takas_bilgi
    yon.protolar[(57, 5704)] = takas_bilgi

    def tur_uygula(liste, carpan, isaret):
        """WonderfulActiveExchangeItemDataVO.CreateProp: ctype 1 elmas, 2 altın, 3 yıldız, 100 eşya."""
        p = {"gold": 0, "gem": 0, "star": 0, "esyalar": []}
        for ctype, eid, adet in liste:
            miktar = isaret * int(adet) * carpan
            if ctype == 1:
                p["gem"] += miktar
            elif ctype == 2:
                p["gold"] += miktar
            elif ctype == 3:
                p["star"] += miktar
            else:
                p["esyalar"].append([eid, miktar])
        return p

    @yon.proto(57, 5702)
    def takas_yap(param, **_):
        liste = paramlist(param)
        t = MG["takas"].get(sayi(liste[0]) if liste else 0)
        if t is None:
            return hata("HintBallTeamError")
        adet = max(1, sayi(liste[1], 1) if len(liste) > 1 else 1)
        with durum.kilit:
            k = kayit()
            toplam = ekle(tur_uygula(t["urun"], adet, 1), tur_uygula(t["maliyet"], adet, -1))
            p = kayit_uygula(k, gold=toplam["gold"], gem=toplam["gem"], star=toplam["star"],
                             esyalar=toplam["esyalar"])
            durum.kaydet()
        data = takas_json(t["aid"])
        data["updatelist"] = updatelist(p)
        return basarili(data)

    # ---------------- 58 resimli kitap parça takası
    def resimli_json():
        """HandBookDataManager.SetTabExchangetimesData: el[{i: hedef eşya, c: yapılan, b: satın alınan}], ts."""
        hedefler = sorted({h[0] for h in MG["resimli"]["hedef"].values()})
        return {"el": [{"i": i, "c": 0, "b": 99} for i in hedefler], "ts": son_sifirlama() + 86400}

    yon.protolar[(58, 5801)] = lambda **_: basarili(resimli_json())

    @yon.proto(58, 5802)
    def resimli_takas(param, **_):
        indeks = sayi((paramlist(param) or [0])[0])
        hedef = MG["resimli"]["hedef"].get(indeks)
        if hedef is None:
            return hata("HintBallTeamError")
        with durum.kilit:
            k = kayit()
            canta = k.setdefault("canta", {})
            maliyet = MG["resimli"]["maliyet"].get(indeks, [])
            if any(int(canta.get(str(e), 0)) < a for e, a in maliyet):
                return hata("DuiHuanCaiLiaoBuZu")
            p = kayit_uygula(k, esyalar=[[e, -a] for e, a in maliyet] + [hedef])
            durum.kaydet()
        data = resimli_json()
        data["updatelist"] = updatelist(p)
        return basarili(data)

    @yon.proto(58, 5803)
    def resimli_hak_al(param, **_):
        liste = paramlist(param)
        adet = max(1, sayi(liste[1], 1) if len(liste) > 1 else 1)
        fiyat = MG["resimli"]["elmas"]
        en_cok = max(fiyat) if fiyat else 0
        gem = sum(int(fiyat.get(min(i, en_cok), 0)) for i in range(1, adet + 1))
        with durum.kilit:
            k = kayit()
            if gem > int(k.get("gem", 0)):
                return hata("HintNotEnoughGem")
            p = kayit_uygula(k, gem=-gem)
            durum.kaydet()
        data = resimli_json()
        data["updatelist"] = updatelist(p)
        return basarili(data)

    # ---------------- /gem_shop ekleri (mevcut işlemler sunucu.py'de kalır)
    eski_gem_shop = yon.yollar.get("/gem_shop")

    def gem_shop(alanlar, param, oturum=None, istek=None):
        """Önce mevcut işleyici (sunucu.py / gunluk.py); yalnız get_free_gem'i bilmiyorsa burada cevaplanır."""
        if eski_gem_shop is not None:
            sonuc = eski_gem_shop(alanlar=alanlar, param=param, oturum=oturum, istek=istek)
            if sonuc.get("result") == 0 or alanlar.get("op") != "get_free_gem":
                return sonuc
        if alanlar.get("op") == "get_free_gem":
            with durum.kilit:
                k = kayit()
                p = kayit_uygula(k, gem=UCRETSIZ_ELMAS)
                p.setdefault("gem", 0)   # PanMain.LookAdGetItems tonumber(paramlist.gem) okur
                durum.kaydet()
            return basarili({"gem_shop": {"mcts": 0, "mcstas": 0, "mcprize": 0, "mcgem": 0, "fg": simdi()},
                             "updatelist": updatelist(p)})
        if eski_gem_shop is None:
            return hata("HintBallTeamError")
        return eski_gem_shop(alanlar=alanlar, param=param, oturum=oturum, istek=istek)

    yon.yollar["/gem_shop"] = gem_shop

    # ---------------- süreli yıldız etkinliğini açık bildir (CardStage 3. kart)
    eski_etkinlik = yon.yollar.get("/activity")
    if SURELI_YILDIZ_ACIK and eski_etkinlik is not None:
        def etkinlik(alanlar, param, oturum=None, istek=None):
            sonuc = eski_etkinlik(alanlar=alanlar, param=param, oturum=oturum, istek=istek)
            try:
                liste = sonuc["data"]["activity"]["status"]
            except (KeyError, TypeError):
                return sonuc
            if isinstance(liste, list) and not any(int(x.get("id", 0)) == SURELI_YILDIZ_ETKINLIGI for x in liste):
                bas = son_sifirlama()
                liste.append({"id": SURELI_YILDIZ_ETKINLIGI, "bt": bas - 86400, "et": bas + 365 * 86400,
                              "ct": bas + 365 * 86400, "lvf": 0, "lvt": 999})
            return sonuc

        yon.yollar["/activity"] = etkinlik

    return MG
