"""PvE maç akışı: Elite (Street Fight, battle_type 6), Hikaye/Legend (battle_type 2) ve genel maç başlatma.

Akış (istemci tarafı):
  Elite : 16/1602 -> MatchManager.startEliteMatch(cur_battle) -> 7/705 -> maç -> 7/702 -> 16/1601
  Legend: 2/2     -> MatchManager.startMatch(battleId)        -> 7/705 -> maç -> 7/702 -> 2/3
  Diğer : MatchManager.startMatch(type, enemy, drop, scene)   -> 7/701 -> maç -> 7/702
Maç sırasında her dalga değişiminde 7/711 (enerji kontrolü) gelir.

Oyuncu nitelikleri istemcinin kendi formülüyle hesaplanır (lua/PlayerAttributeLua.lua,
PlayerAttributeLua:initData); rakipler data_battle.team_list -> data_team.playerN -> data_enemy
(+ data_enemy_skill) zincirinden kurulur, istemcinin Elite önizlemesi (EliteBattleDataVO) ile aynı.

Kullanım (sunucu.py, tüm sabit() kayıtlarından SONRA):
    import mac; mac.kur(yon, durum)
"""
import logging
import math
import random
import time

from cekirdek import basarili
from durum import ESYA_VERI, OYUNCU_VERI, SINIR, CANTA_TURU
from elite import MAC_VERI as MV, elite_json, elite_yildiz_json, mac_yildizi, sandiklar

log = logging.getLogger("sunucu")

UST_SINIR = 99999999          # gold/gem/star tavanı (durum.BOL ile aynı)
ESYA_SINIR = 999999
AMIGO_NITELIK_EKLE = True     # seçili amigonun nitelikleri oyunculara eklensin mi (bkz. amigo_niteligi)
# Kendi oyuncularımızın niteliklerine uygulanan çarpan. Kayıtta ekipman/bağ/resimli kitap olmadığından tam
# gelişmiş takım ~325k güçte kalır; son Elite şehri ~800k ister. Kayıttaki "guc_carpani" bunu geçersiz kılar.
GUC_CARPANI = 2.5

# PlayerAttributeLua'daki nitelik sırası ve her niteliğin bağlı olduğu antrenman dalı (train[1..5])
NITELIK = ["morale", "attackMorale", "defendMorale", "shot", "dribble", "rebound", "block", "defend",
           "noBallAbility", "crossOver"]
ANTRENMAN_DALI = [1, 2, 1, 2, 3, 5, 4, 4, 5, 3]
EK_NITELIK = ["crit", "moraleRecover", "powerRecover", "skillDamage", "fightCourage",
              "versatile", "critValue", "endurance", "toughness", "passivation", "mastery"]
BOS_AMIGO = {"id": 0, "level": 0, "gears": 0}


# ---------------------------------------------------------------- formüller

def guc_hesapla(degerler):
    """PlayerAttributeLua.lua:430-446 savaş gücü (Fighting); SecondTotal ve stil becerileri 0."""
    a, p = 0.1, 5000
    l_i = 1 - a
    toplam = sum(degerler)
    n = math.floor(toplam / p) + 1
    t = p * l_i * (n - 1) + p * a * ((n * (n - 1)) / 2)
    return int(math.ceil((t + (toplam - p * (n - 1)) * (l_i + a * n)) / 5))


def _sinirla(x, alt, ust):
    return max(alt, min(ust, x))


def _antrenman(o):
    tr = o.get("train", 0)
    if isinstance(tr, list):
        seviyeler = [int(x["level"] if isinstance(x, dict) else x) for x in tr][:5]
    else:
        seviyeler = [int(tr)] * 5
    return seviyeler + [0] * (5 - len(seviyeler))


def amigo_bilgisi(k):
    """Seçili ilk amigo: (id, seviye, gears). gears = kademe (1..6); >=3 elle kullanılan beceri, >=5 ikinci beceri."""
    secili = [int(a) for a in k.get("secili_amigolar") or [] if int(a) in MV["amigo"]]
    if not secili:
        return None
    aid = secili[0]
    kayit = (k.get("amigolar") or {}).get(str(aid), 1)
    if isinstance(kayit, dict):
        seviye = int(kayit.get("level", 1))
        kademe = kayit.get("index") or kayit.get("gears")
    else:
        seviye, kademe = int(kayit), None
    bilgi = MV["amigo"][aid]
    seviye = _sinirla(seviye, 1, len(bilgi["s"]))
    if not kademe:
        kademe = 1 + sum(1 for lim, _ in bilgi["l"] if lim <= seviye)
    return aid, seviye, int(_sinirla(int(kademe), 1, len(bilgi["l"]) + 1))


def amigo_niteligi(k):
    """OuendanStageDataManager.GetFightValue (lua 330-357): seviye niteliği * kademe yüzdesi."""
    a = amigo_bilgisi(k)
    if a is None:
        return [0] * 10
    aid, seviye, kademe = a
    bilgi = MV["amigo"][aid]
    yuzde = 1.0
    if kademe >= 2:
        yuzde = bilgi["l"][min(kademe, len(bilgi["l"]) + 1) - 2][1] / 100.0
    return [v * yuzde for v in bilgi["s"][seviye - 1]]


def nitelik_hesapla(pid, o, ek=None):
    """lua/PlayerAttributeLua.lua PlayerAttributeLua:initData (satır 61-447) Python karşılığı.

    yildiz kısmı  : 3*(level-1)*GrowUp/10 + StarUpValue                (PlayerGrowUpValue/PlayerStarUpValue[star])
    antrenman     : 2*dugum*GrowUp/5 + 4*(train-dugum)*GrowUp/15      (dugum = playerGrowUpCnts.lastnodelevel)
    giysi         : renk (kalite) 1..color satırlarındaki 6 giysinin Basic değerleri * 1.5 (PlayerDressEquip)
    Kalite güçlendirme, ekipman, bağ (rela), resimli kitap çarpanları kayıtta olmadığı için 1.
    """
    v = MV["oyuncu"][pid]
    yildiz = _sinirla(int(o.get("break_level", 1)), 1, len(v["y"]))
    seviye = max(1, int(o.get("level", 1)))
    renk = _sinirla(int(o.get("color", 1)), 0, len(v["g"]))
    buyume, yildiz_deger = v["b"][yildiz - 1], v["y"][yildiz - 1]
    antrenman = _antrenman(o)
    dugum = MV["egitim_dugum"].get(int(o.get("grow_up_cnts", 0)), 0)
    giysi = [sum(satir[i] for satir in v["g"][:renk]) * 1.5 for i in range(10)]
    sonuc = []
    for i in range(10):
        g = buyume[i]
        tr = antrenman[ANTRENMAN_DALI[i] - 1]
        tl = dugum if tr > 0 else 0
        deger = 3 * (seviye - 1) * g / 10 + yildiz_deger[i]
        deger += 2 * tl * g / 5 + 4 * (tr - tl) * g / 15
        deger += giysi[i] + (ek[i] if ek else 0)
        sonuc.append(int(math.ceil(deger - 1e-9)))
    return sonuc


def attr_json(degerler, enerji, enerji_hiz):
    attr = {"fight": guc_hesapla(degerler)}
    attr.update({ad: int(d) for ad, d in zip(NITELIK, degerler)})
    attr["entranceEnergy"] = int(enerji)
    attr["energyRecoverSpeed"] = int(enerji_hiz)
    attr.update({ad: 0 for ad in EK_NITELIK})
    return attr


def beceri_listesi(pid, o):
    """Yıldız atlamada açılmış tür 1/3 beceriler (starUpBaseInfo, starSec <= break_level); oyuncunun kendi
    becerileri (PlayerSkillInfo) kayıttaki beceri seviyesiyle, diğerleri tablo seviyesiyle."""
    yildiz = int(o.get("break_level", 1))
    kendi = set(OYUNCU_VERI[pid]["beceriler"]) if pid in OYUNCU_VERI else set()
    kayitli = o.get("beceri", 1)
    seviyeler = {}
    for sec, sid, sv in MV["oyuncu"][pid]["s"]:
        if sec > yildiz:
            continue
        if sid in kendi:
            sv = int(kayitli.get(str(sid), sv)) if isinstance(kayitli, dict) else int(kayitli)
        seviyeler[sid] = max(seviyeler.get(sid, 0), sv)
    return [{"skill_id": s, "skill_level": sv} for s, sv in seviyeler.items()]


def kendi_takim(k):
    """Seçili 3 oyuncu (pos sırasıyla); eksik varsa sahip olunan oyunculardan tamamlanır."""
    secili = [s for s in sorted(k.get("secili") or [], key=lambda s: s["pos"])
              if int(s["id"]) in MV["oyuncu"] and str(s["id"]) in k["oyuncular"]]
    idler = [int(s["id"]) for s in secili][:3]
    for pid in k["oyuncular"]:
        if len(idler) >= 3:
            break
        if int(pid) in MV["oyuncu"] and int(pid) not in idler:
            idler.append(int(pid))
    ek = amigo_niteligi(k) if AMIGO_NITELIK_EKLE else None
    carpan = float(k.get("guc_carpani", GUC_CARPANI) or 1.0)
    oyuncular = []
    for i, pid in enumerate(idler):
        o = k["oyuncular"][str(pid)]
        deger = [int(math.ceil(x * carpan)) for x in nitelik_hesapla(pid, o, ek)]
        enerji = MV["oyuncu"][pid]["e"]
        oyuncular.append({
            "id": pid, "enemy_id": 0, "level": int(o.get("level", 1)), "break_level": int(o.get("break_level", 1)),
            "color": int(o.get("color", 1)), "pos": i + 1, "skill_list": beceri_listesi(pid, o),
            "attr": attr_json(deger, enerji[0], enerji[1]),
        })
    a = amigo_bilgisi(k)
    amigo = {"id": a[0], "level": a[1], "gears": a[2]} if a else dict(BOS_AMIGO)
    return oyuncular, amigo


def rakip_dalgasi(takim_id):
    oyuncular = []
    for i, eid in enumerate(MV["takim"].get(takim_id, [])):
        e = MV["dusman"].get(eid)
        if e is None:
            continue
        pid, seviye, degerler, enerji, enerji_hiz, beceriler = e
        oyuncular.append({
            "id": pid, "enemy_id": eid, "level": seviye, "break_level": 1, "color": 1, "pos": i + 1,
            "skill_list": [{"skill_id": s, "skill_level": sv} for s, sv in beceriler],
            "attr": attr_json(degerler, enerji, enerji_hiz),
        })
    return oyuncular


def dalga(oyuncular, amigo):
    return {"team": oyuncular, "cheer": [amigo], "skill": [],
            "strength": sum(p["attr"]["fight"] for p in oyuncular)}


def battlemsg(k, battle_id, battle_type, sahne, takim_idler, droplist_id=0, rakip_adi=""):
    """MatchLoader.lua:32'deki tutorial_data ile aynı şekil."""
    biz, amigo = kendi_takim(k)
    rakip_dalgalari = [d for d in (rakip_dalgasi(t) for t in takim_idler) if len(d) == 3]
    if not rakip_dalgalari:
        raise ValueError("rakip takımı kurulamadı: %s" % takim_idler)
    t = k["takim"]
    return {
        "ts_begin": int(time.time()), "ladder_count": 0, "battle_type": int(battle_type),
        "battle_id": int(battle_id), "droplist_id": int(droplist_id), "enemy_uin": 0, "scene": int(sahne or 100),
        "status": 1, "is_home_team": 1, "possession": 0, "remaining_time": 0,
        "self_hp": sum(p["attr"]["morale"] for p in biz),
        "enemy_hp": sum(p["attr"]["morale"] for p in rakip_dalgalari[0]),
        "battle_player_self": [dalga(biz, amigo)],
        "battle_player_enemy": [dalga(d, dict(BOS_AMIGO)) for d in rakip_dalgalari],
        "cheer_self": [amigo], "cheer_enemy": [dict(BOS_AMIGO)],
        "team_level_self": int(t.get("seviye", 1)),
        "team_level_enemy": max(p["level"] for d in rakip_dalgalari for p in d),
        "team_icon_self": int(t.get("ikon", 1)), "team_icon_enemy": 1,
        "team_name_self": t.get("ad", ""), "team_name_enemy": rakip_adi or "",
        "skill_cd": [{"id": 0, "ts": 0} for _ in range(3)],
    }


# ---------------------------------------------------------------- ödüller

def dusus_coz(dusus_id, rnd=random):
    """data_droplist: sabit değerler + data_droplist_item (kesin) + _odds (rate/10000) + _weight (N çekiliş)."""
    d = MV["dusus"].get(int(dusus_id or 0))
    odul = {"exp": 0, "exp_team": 0, "gold": 0, "gem": 0, "star": 0, "esyalar": {}}
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


def odul_topla(oduller):
    top = {"exp": 0, "exp_team": 0, "gold": 0, "gem": 0, "star": 0, "esyalar": {}}
    for o in oduller:
        for ad in ("exp", "exp_team", "gold", "gem", "star"):
            top[ad] += o[ad]
        for eid, adet in o["esyalar"].items():
            top["esyalar"][eid] = top["esyalar"].get(eid, 0) + adet
    return top


def _esya_listesi(esyalar):
    return [{"id": int(e), "count": int(a)} for e, a in esyalar.items() if a]


def oyuncu_exp_durumu(k, idler):
    return [{"id": pid, "level": int(k["oyuncular"][str(pid)].get("level", 1)),
             "exp": int(k["oyuncular"][str(pid)].get("exp", 0))} for pid in idler]


def odul_uygula(k, odul, oyuncu_idler):
    """Ödülü kayda işler (kilit altında çağrılmalı); istemciye gidecek updatelist'i ve exp durumlarını döner."""
    param = {}
    for ad in ("gold", "gem", "star"):
        eski = int(k.get(ad, 0))
        yeni = min(UST_SINIR, eski + int(odul[ad]))
        k[ad] = max(eski, yeni)
        if k[ad] != eski:
            param[ad] = k[ad] - eski
    canta = k.setdefault("canta", {})
    degisen = []
    for eid, adet in odul["esyalar"].items():
        bilgi = ESYA_VERI.get(int(eid))
        if bilgi is None or bilgi.get("tur") not in CANTA_TURU:
            continue
        eski = int(canta.get(str(eid), 0))
        yeni = min(ESYA_SINIR, eski + int(adet))
        if yeni != eski:
            canta[str(eid)] = yeni
            degisen.append({"id": int(eid), "count": yeni - eski})
    if degisen:
        param["item_list"] = degisen

    # takım deneyimi (TeamExperience: seviye -> o seviyeyi geçmek için gereken exp)
    t = k["takim"]
    tmax = max(MV["takim_exp"])
    if odul["exp_team"] > 0 and t.get("seviye", 1) < tmax:
        param["exp_team"] = int(odul["exp_team"])
        t["exp"] = int(t.get("exp", 0)) + int(odul["exp_team"])
        while t["seviye"] < tmax and t["exp"] >= MV["takim_exp"].get(t["seviye"], 1 << 60):
            t["exp"] -= MV["takim_exp"][t["seviye"]]
            t["seviye"] += 1
        if t["seviye"] >= tmax:
            t["exp"] = 0

    # oyuncu deneyimi (PlayerExperienceInfo); azami seviyede exp değişmez, böylece sonuç ekranı animasyonsuz kalır
    eski = oyuncu_exp_durumu(k, oyuncu_idler)
    omax = min(SINIR["oyuncu_seviye"], max(MV["oyuncu_exp"]))
    exp_degisen = []
    for pid in oyuncu_idler:
        o = k["oyuncular"][str(pid)]
        if odul["exp"] <= 0 or o.get("level", 1) >= omax:
            continue
        o["exp"] = int(o.get("exp", 0)) + int(odul["exp"])
        while o["level"] < omax and o["exp"] >= MV["oyuncu_exp"].get(o["level"], 1 << 60):
            o["exp"] -= MV["oyuncu_exp"][o["level"]]
            o["level"] += 1
        if o["level"] >= omax:
            o["exp"] = 0
        exp_degisen.append({"id": pid, "level": o["level"], "exp": o["exp"]})
    if exp_degisen:
        param["exp"] = exp_degisen
    param["stamina"] = int(k.get("stamina", 0))
    return {"op_flag": 1, "paramlist": param}, eski, oyuncu_exp_durumu(k, oyuncu_idler)


# ---------------------------------------------------------------- hikaye (Legend)

def hikaye_bolumu():
    """Haftalık dönen bölüm (data_story_stage 1..3)."""
    idler = sorted(MV["hikaye"])
    hafta = time.localtime().tm_yday // 7
    return idler[hafta % len(idler)]


def hikaye_json():
    return {"stage_list": [{"id": hikaye_bolumu()}], "ts_l": 0, "ts_lc": int(time.time()), "cur_count": 0}


# ---------------------------------------------------------------- kayıt

def kur(yon, durum):
    aktif = {}

    def kayit():
        return durum.hesap_ac(durum.veri["hesap"] if durum.veri else "")

    def secili_idler(k):
        return [p["id"] for p in kendi_takim(k)[0]]

    def paramlist(param):
        liste = (param or {}).get("paramlist") if isinstance(param, dict) else param
        return liste if isinstance(liste, list) else []

    def sayi(x, varsayilan=0):
        try:
            return int(x)
        except (TypeError, ValueError):
            return varsayilan

    def tum_elite(k):
        return elite_json(k)

    # ---------------- maç başlatma
    def mac_baslat(battle_id, battle_type=None, sahne=None, takimlar=None, dusus=None, ad=""):
        k = kayit()
        m = MV["mac"].get(battle_id)
        if m is not None:
            battle_type = m[0] if battle_type is None else battle_type
            sahne = sahne or m[1]
            takimlar = takimlar or m[3]
            dusus = m[2] if dusus is None else dusus
            ad = ad or m[4]
        with durum.kilit:
            msg = battlemsg(k, battle_id, battle_type or 0, sahne, takimlar or [], dusus or 0, ad)
        aktif.clear()
        aktif.update({"battle_id": battle_id, "battle_type": msg["battle_type"], "dusus": dusus or 0,
                      "ts": time.time()})
        log.info("maç başladı: id=%s tür=%s dalga=%d", battle_id, msg["battle_type"], len(msg["battle_player_enemy"]))
        return basarili({"battlemsg": msg})

    @yon.proto(7, 705)
    def battle_begin_ex(param, **_):
        liste = paramlist(param)
        bid = sayi(liste[0]) if liste else 0
        if bid not in MV["mac"]:
            log.warning("bilinmeyen battleId %s; yedek rakip kullanılıyor", bid)
            return mac_baslat(bid, 0, 100, yedek_takim(), 0)
        return mac_baslat(bid)

    def yedek_takim():
        """Bilinmeyen rakip: son 3 Elite şehrinden rastgele bir maçın takımları."""
        adaylar = [b for b, m in MV["mac"].items() if m[0] == 6]
        adaylar = sorted(adaylar)[-48:]
        return MV["mac"][random.choice(adaylar)][3]

    @yon.proto(7, 701)
    def battle_begin(param, **_):
        liste = paramlist(param) + [0, 0, 0, 0]
        tur, rakip, dusus, sahne = (sayi(x) for x in liste[:4])
        if rakip in MV["takim"]:
            return mac_baslat(0, tur, sahne or 100, [rakip], dusus)
        if rakip in MV["mac"]:
            m = MV["mac"][rakip]
            return mac_baslat(0, tur, sahne or m[1], m[3], dusus or m[2], m[4])
        return mac_baslat(0, tur, sahne or 100, yedek_takim(), dusus)

    @yon.proto(7, 711)
    def enerji_kontrol(**_):
        return basarili({"code": 0})

    # ---------------- maç sonu
    @yon.proto(7, 702)
    def battle_over(param, **_):
        liste = paramlist(param) + [0, 0, 0]
        kazandi = sayi(liste[0]) == 1
        yildiz = _sinirla(sayi(liste[1]), 0, 3)
        bid, tur = aktif.get("battle_id", 0), aktif.get("battle_type", 0)
        with durum.kilit:
            k = kayit()
            idler = secili_idler(k)
            odul = dusus_coz(aktif.get("dusus", 0)) if kazandi else dusus_coz(0)
            if kazandi and tur == 6 and bid:
                ilerleme = k.setdefault("elite", {})
                ilerleme[str(bid)] = max(int(ilerleme.get(str(bid), 0)), yildiz or 1)
            guncel, eski, yeni = odul_uygula(k, odul, idler)
            durum.kaydet()
        aktif.clear()
        msg = {"battle_type": tur, "battle_id": bid, "win": 1 if kazandi else 0, "result_star": yildiz,
               "exp": odul["exp"], "gold": odul["gold"], "gem": odul["gem"], "star": odul["star"],
               "exp_team": odul["exp_team"], "item_list": _esya_listesi(odul["esyalar"]),
               "player_exp_old": eski, "player_exp_new": yeni}
        log.info("maç bitti: id=%s kazandı=%s yıldız=%s ödül=%s", bid, kazandi, yildiz, odul)
        return basarili({"battlemsg": msg, "updatelist": guncel})

    # ---------------- Elite
    @yon.proto(16, 1602)
    def elite_mac(param, **_):
        bid = sayi((param or {}).get("battle"))
        with durum.kilit:
            k = kayit()
            data = tum_elite(k)
            data["cur_battle"] = bid
            data["cur_stage"] = sayi((param or {}).get("stage"))
            data["cur_star"] = sayi((param or {}).get("star"))
            stamina = int(k.get("stamina", 0))
        # dayanıklılık düşülmez (sınırsız); updatelist yalnızca güncel değeri tazeler
        return basarili({"elite": data, "updatelist": {"op_flag": 1, "paramlist": {"stamina": stamina}}})

    def elite_cevap(k, guncel=None, **ek):
        data = {"elite": tum_elite(k)}
        data.update(ek)
        if guncel is not None:
            data["updatelist"] = guncel
        return basarili(data)

    @yon.proto(16, 1606)
    def elite_mac_sandigi(param, **_):
        bid = sayi((param or {}).get("battle"))
        with durum.kilit:
            k = kayit()
            acilan = sandiklar(k)
            guncel = None
            if bid in MV["elite_mac_sandik"] and bid not in acilan["mac"]:
                acilan["mac"].append(bid)
                odul = dusus_coz(MV["elite_mac_sandik"][bid])
                guncel = odul_uygula(k, odul, [])[0]
                durum.kaydet()
            return elite_cevap(k, guncel)

    @yon.proto(16, 1607)
    def elite_yildiz_sandigi(param, **_):
        sid = sayi((param or {}).get("stage"))
        yildiz = sayi((param or {}).get("star"))
        with durum.kilit:
            k = kayit()
            acilan = sandiklar(k)["yildiz"].setdefault(str(sid), [])
            guncel = None
            dusus = MV["elite_yildiz_sandik"].get(sid, {}).get(yildiz)
            if dusus is not None and yildiz not in acilan:
                acilan.append(yildiz)
                guncel = odul_uygula(k, dusus_coz(dusus), [])[0]
                durum.kaydet()
            return elite_cevap(k, guncel)

    @yon.proto(16, 1605)
    def elite_supur(param, **_):
        bid = sayi((param or {}).get("battle"))
        adet = _sinirla(sayi((param or {}).get("count"), 1), 1, 50)
        with durum.kilit:
            k = kayit()
            idler = secili_idler(k)
            dusus = MV["elite_supurme"].get(bid) or (MV["mac"].get(bid) or [0, 0, 0])[2]
            oduller = [dusus_coz(dusus) for _ in range(adet)]
            guncel, eski, yeni = odul_uygula(k, odul_topla(oduller), idler)
            durum.kaydet()
            sonuc = [{"gold": o["gold"], "gem": o["gem"], "star": o["star"], "exp": o["exp"],
                      "exp_team": o["exp_team"], "item_list": _esya_listesi(o["esyalar"])} for o in oduller]
            data = tum_elite(k)
            data["battle_result"] = {"player_exp_old": eski, "player_exp_new": yeni}
            return basarili({"elite": data, "resultlist": sonuc, "updatelist": guncel})

    def sadece_elite(**_):
        with durum.kilit:
            return elite_cevap(kayit())

    for sub in (1600, 1601, 1603, 1604, 1608, 1609):
        yon.protolar[(16, sub)] = sadece_elite

    def elite_yildiz(**_):
        with durum.kilit:
            return basarili({"elite": elite_yildiz_json(kayit())})

    for sub in (1610, 1611, 1617, 1618):
        yon.protolar[(16, sub)] = elite_yildiz

    # ---------------- Hikaye / Legend
    def hikaye(**_):
        return basarili({"story": hikaye_json()})

    for sub in (1, 3, 4, 100):
        yon.protolar[(2, sub)] = hikaye

    @yon.proto(2, 2)
    def hikaye_mac(param, **_):
        bid = sayi((param or {}).get("battle"))
        log.info("hikaye maçı istendi: bölüm=%s maç=%s", (param or {}).get("stage"), bid)
        return basarili({"story": hikaye_json(), "updatelist": {"op_flag": 1, "paramlist": {
            "stamina": int(kayit().get("stamina", 0))}}})

    return aktif
