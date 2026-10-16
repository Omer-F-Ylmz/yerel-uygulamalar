"""Streetball Hero yerel sunucusu.

Tek bir HTTP portunda (varsayılan 8881) şunların hepsini yapar:
  - CDN: GatewayList/ServerNotice/VersionConfig XML'leri ve kaynak listeleri
  - Giriş: ağ geçidi ve oyun sunucusu /login
  - Oyun: /client (proto/proto_sub) ve adlı uç noktalar (/ball_team, /get_user_info ...)
  - /panel: tarayıcıdan açılan yönetim paneli

Kullanım: python sunucu.py [--port 8881] [--obb <orijinal.obb>]
"""
import argparse
import hashlib
import logging
import os
import sys
import time
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cekirdek import Ham, Yonlendirici, basarili, hata, http_sunucu_kur, param_coz  # noqa: E402
from durum import CANTA_TURU, Durum, OYUNCU_VERI, ESYA_VERI, SINIR, VERI  # noqa: E402

log = logging.getLogger("sunucu")
yon = Yonlendirici()
durum = Durum()
AYAR = {"port": 8881, "obb": None}
OTURUM = "yerel-oturum"


# ---------------------------------------------------------------- yardımcılar

def simdi():
    return int(time.time())


def istek_host(istek):
    host = istek.headers.get("Host") or "127.0.0.1"
    return host.rsplit(":", 1)[0] if ":" in host else host


def kayit():
    """Oturum açılmadan gelen isteklerde de çalışsın diye hesabı garanti eder."""
    return durum.hesap_ac(durum.veri["hesap"] if durum.veri else "")


def op_yolu(yol, islevler, varsayilan=None):
    """Aynı uç noktaya farklı 'op' değerleriyle gelen istekleri ayırır."""
    def isle(alanlar, param, oturum, istek):
        op = alanlar.get("op", "")
        f = islevler.get(op, varsayilan)
        if f is None:
            log.warning("BILINMEYEN %s op=%s alanlar=%s", yol, op, alanlar)
            return basarili({})
        return f(alanlar=alanlar, param=param)
    yon.yollar[yol] = isle


def sabit(proto, sub, data):
    """Her zaman aynı veriyi dönen /client protokolü."""
    yon.protolar[(proto, sub)] = lambda **_: basarili(data() if callable(data) else data)


def sabit_yol(yol, data):
    yon.yollar[yol] = lambda **_: basarili(data() if callable(data) else data)


# ---------------------------------------------------------------- oyun verisi şekillendirme

# equipPlayerInfo: yuva i'nin eşyası = önek + oyuncu id (1011007 ...); sınırlar equipMaxConfig'ten
# (güçlendirme 100, kırılma 19-1, uyanış 5; equipBreakAttr/equipWakeAttr bu seviyelere kadar satır içerir)
EKIPMAN_ONEK = (101, 102, 103, 201, 202, 203)


def oyuncu_json(pid, o):
    bilgi = OYUNCU_VERI[int(pid)]
    return {
        "id": int(pid),
        "exp": o["exp"],
        "level": o["level"],
        "break_level": o["break_level"],
        "color": o["color"],
        "fight": o["level"] * 1000,
        "qualifily": {"qa": 0, "t": 0},
        "s_equipment_list": [],
        # 6 yuva şart: EquipDataManager.IsCanStrength equipInfoList[1..6] okur (PanMain.InitButtonTip)
        "equip": [{"no": i + 1, "id": int("%d%d" % (on, pid)), "lv": 100, "blv": 18, "wlv": 5}
                  for i, on in enumerate(EKIPMAN_ONEK)],
        "s_skill_list": [{"skill_id": s, "skill_level": o["beceri"]} for s in bilgi["beceriler"]],
        "other_skill_list": bilgi["diger_beceriler"],
        "train": [{"level": o["train"]} for _ in range(5)],
        "rela": [],
    }


def takim_json(k):
    secili = [{"pos": s["pos"], "id": s["id"]} for s in k["secili"]]
    return {
        "player_lists": [oyuncu_json(pid, o) for pid, o in k["oyuncular"].items()],
        "select": secili,
        "team_list": [{"index": 1, "status": 1, "plist": secili}],
        "styles_today_buy_num": 0,
    }


def canta_json(k):
    canta = {ad: [] for ad in CANTA_TURU.values()}
    for i, (eid, adet) in enumerate(sorted(k["canta"].items())):
        bilgi = ESYA_VERI.get(int(eid))
        if bilgi is None or adet <= 0:
            continue
        canta[CANTA_TURU[bilgi["tur"]]].append({"uuid": 100000 + i, "id": int(eid), "count": adet})
    return canta


STIL_PUANI = 30  # PointConfig id=1 (en fazla puan); fazlası PlayerStyleData'da eksi süre üretir


def oyuncu_bilgisi_json(k):
    return {
        "uname": k["hesap"],
        "dis_name": k["takim"]["ad"],
        "gold": k["gold"],
        "gem": k["gem"],
        "rm_ticket": k["rm_ticket"],
        "rm_ticket_cd": 0,
        "star": k["star"],
        "cd_liveshow": 0,
        "point": STIL_PUANI,
        "point_cd": 0,
        "point_last_update_ts": simdi(),
    }


# GuideBaseInfo (1001-1033), Lua'nın sorduğu zayıf rehberler ve maç içi rehberler (MatchManager).
# Hepsi "bitti" sayılır: GuideManager.isFinishGuildById true döner, hiçbir öğretici başlamaz.
REHBERLER = (list(range(1001, 1034)) + [1803] + list(range(2001, 2025)) + [2050, 6666]
             + list(range(11000001, 11000005)))


def rehber_json(k):
    bitti = sorted(set(REHBERLER) | set(k["rehber"]))
    return {"type": 0, "step": 0, "all": [{"type": t, "step": 0} for t in bitti],
            "start": [{"type": t, "step": 0} for t in k.get("rehber_baslangic", [])]}


def takim_gucu(k):
    return sum(oyuncu_json(s["id"], k["oyuncular"][str(s["id"])])["fight"] for s in k["secili"])


# TeamPlayerIcon tablosundaki oyuncu dışı ikonlar; oyuncu ikonları sahip olunan oyunculardan gelir
TAKIM_IKONLARI = [1, 2, 8, 11] + list(range(15, 37))


def ballteam_json(k):
    t = k["takim"]
    return {
        "ballteam": {"name": t["ad"], "icon": t["ikon"], "level": t["seviye"], "exp": t["exp"],
                     "icons": [{"icon": i} for i in TAKIM_IKONLARI + [int(p) for p in k["oyuncular"]]],
                     # prizelog rakam dizisidir (PanMainDataManager.GetTeamPrizeStatus string.len yapar)
                     "prizelog": ""},
        "fight": takim_gucu(k),
        "arena_max": 0,
    }


def elite_json(k):
    """Tüm şehirler açık ve tamamlanmış, her maç tekrar oynanabilir."""
    ilerleme = k.setdefault("elite", {})
    sehirler = []
    for e in VERI["elite"]:
        maclar = []
        for b in e["maclar"]:
            yildiz = ilerleme.get(str(b), 3)
            maclar.append({"battle_id": b, "star": yildiz, "count": 0, "supply_times": 0, "battle_status": 1})
        toplam = sum(m["star"] for m in maclar)
        sehirler.append({
            "stage_id": e["id"],
            "stage_status": 2,
            "star_all": toplam,
            "chests_list": [{"star_count": s, "status": 0} for s in e["sandiklar"]],
            "stage_status_ex": 2,
            "battle_list": maclar,
        })
    return {"pi_s": 0, "pi_b": 0, "stage_list": sehirler}


def elite_yildiz_json(k):
    data = elite_json(k)
    data.update({"su_t_s": 0, "pi_ss": 0, "pi_bs": 0, "pi_ss_h": 0, "pi_bs_h": 0,
                 "st_s_s": 0, "ts_ss": 0, "ts_ss_e": 0, "h_r": 0})
    return data


# ---------------------------------------------------------------- CDN ve kaynak dosyaları

_obb = None


def obb():
    global _obb
    if _obb is None and AYAR["obb"]:
        _obb = zipfile.ZipFile(AYAR["obb"])
    return _obb


def obb_oku(*adaylar):
    z = obb()
    if z is None:
        return None
    for ad in adaylar:
        try:
            return z.read(ad)
        except KeyError:
            continue
    return None


@yon.onek("/GameConfig/")
def cdn_config(yol, istek):
    host = istek_host(istek)
    ad = yol.rsplit("/", 1)[-1].split("?")[0]
    if ad == "GatewayList.xml":
        xml = ('<RECORDS>\n  <RECORD>\n    <Item serverId="1" serverName="Yerel" serverIP="http://%s" '
               'serverPort="%d" status="1" tag="1" isTestServer="0" resourcePath="http://%s:%d/res/"/>\n'
               '  </RECORD>\n</RECORDS>\n') % (host, AYAR["port"], host, AYAR["port"])
    elif ad == "ServerNotice.xml":
        xml = '<ServerNotice>\n  <Item title="Yerel sunucu" content="Iyi oyunlar!" />\n</ServerNotice>\n'
    elif ad == "VersionConfig.xml":
        xml = '<Config>\n  <Item resourceVersion="1.0.0" />\n</Config>\n'
    else:
        return Ham("", durum=404)
    return Ham(xml, "text/xml; charset=utf-8")


@yon.onek("/GamePack/")
def cdn_gamepack(yol, istek):
    # Boş liste: indirilecek ek paket yok.
    return Ham("")


def conf_zamani():
    """ConfManager'ın md5 karşılaştırması: conf#?#conf_json#surum; eşleşirse yerel dosyayı kullanır."""
    a = obb_oku("assets/Android/conf_qte.assetbundle") or b""
    b = obb_oku("assets/Android/conf_luatab_qte.assetbundle") or b""
    return "%s#0#%s#1" % (hashlib.md5(a).hexdigest(), hashlib.md5(b).hexdigest())


@yon.onek("/res/ANDROID/")
def kaynak(yol, istek):
    yol = yol.split("?")[0]
    ad = yol.rsplit("/", 1)[-1]
    if ad == "conf_time.txt":
        return Ham(conf_zamani())
    veri = obb_oku("assets/Android/" + yol, "assets/Android/md5/" + yol, "assets/Android/" + ad)
    if veri is None:
        log.warning("kaynak bulunamadı: %s", yol)
        if ad.endswith(".txt"):
            return Ham("")
        return Ham("", durum=404)
    return Ham(veri, "application/octet-stream")


# ---------------------------------------------------------------- giriş

@yon.yol("/login")
def giris(alanlar, param, oturum, istek):
    if "uin" in alanlar:
        # Oyun sunucusu girişi: oturum kimliği ver, öğreticileri kapat.
        return basarili({"session": OTURUM, "guide": 0})
    hesap = alanlar.get("id") or "Oyuncu"
    durum.hesap_ac(hesap)
    host = istek_host(istek)
    log.info("giriş: hesap=%s", hesap)
    zarf = basarili({
        "login_info": {"uin": kayit()["uin"], "token": "yerel", "white_name": 0, "is_new": 0},
        "server_list": [{
            "display_info": {"name": "Yerel", "type": 1, "state": 1},
            "server_info": {"ip": host, "port": AYAR["port"], "pvp_port": 9001,
                            "chat_ip": host, "chat_port": 9002},
        }],
    })
    zarf["force"] = 0
    zarf["url"] = ""
    return zarf


# ---------------------------------------------------------------- lobi yüklemesi

def ball_team_al(**_):
    return basarili(ballteam_json(kayit()))


def ball_team_ad(alanlar, **_):
    with durum.kilit:
        kayit()["takim"]["ad"] = alanlar.get("param") or kayit()["takim"]["ad"]
        durum.kaydet()
    return basarili(ballteam_json(kayit()))


op_yolu("/ball_team", {"get_ball_team": ball_team_al, "rename": ball_team_ad}, ball_team_al)


@yon.yol("/get_user_info")
def kullanici_bilgisi(**_):
    k = kayit()
    return basarili({
        "player": oyuncu_bilgisi_json(k),
        "guide_step": rehber_json(k),
        "team": takim_json(k),
        "backpack": canta_json(k),
    })


@yon.yol("/get_server_time")
def sunucu_zamani(**_):
    t = time.localtime()
    return basarili({"now": simdi(), "server_time": t.tm_hour * 3600 + t.tm_min * 60 + t.tm_sec})


op_yolu("/player_month_checkin", {}, lambda **_: basarili({"monthchckin": {
    "month_check_status": "0" * 31, "month_cumulative_prize_status": "00000",
    "last_checkin_ts": 0, "day": 0, "if_cancheck": 0}}))

sabit_yol("/get_notice", {"notice_info": []})

op_yolu("/player_strength", {}, lambda **_: basarili({"strength": {
    "strength": kayit()["stamina"], "strength_cd": 0, "today_buy_times": 0, "free_get_status": 0,
    "styles_points": STIL_PUANI, "styles_last_update_ts": simdi(), "last_update_ts": simdi(), "cd": 0}}))

sabit(2, 1, {"story": {"stage_list": [], "ts_l": 0, "ts_lc": 0, "cur_count": 0}})
sabit(16, 1601, lambda: {"elite": elite_json(kayit())})
sabit(16, 1610, lambda: {"elite": elite_yildiz_json(kayit())})

op_yolu("/player_mission", {
    "get_growth_mission_day": lambda **_: basarili({"growth_mission_day": {}}),
}, lambda **_: basarili({"mission": {"mission": [], "is_gotpriaze": 0, "complete_cnts": 0}}))

sabit_yol("/month_card", {"supreme_month_card": {"is_buy": 0, "is_receive": 0}})
sabit_yol("/growth_fund", {"growth_fund": {"is_buy": 0, "count": 0, "accepted": []}})

op_yolu("/cheer_leader", {}, lambda **_: basarili({"cheer_leader": {
    "cheers": [{"id": int(a), "level": sv} for a, sv in kayit()["amigolar"].items()],
    "select_cheers": [{"id": a} for a in kayit()["secili_amigolar"]]}}))

sabit(24, 2401, {})
op_yolu("/two_week", {}, lambda **_: basarili({"checkin": {"2ws": 0}}))
sabit(35, 3501, lambda: {"vip": {"lv": kayit()["vip"], "gem": 0, "rmb": 0, "vip_package": []}})

op_yolu("/gem_shop", {
    "get_conti_charge": lambda **_: basarili({"id": 0, "conti_recharge": {"status": 0, "prize": 0, "status0": 0, "prize0": 0}}),
    "get_acc_charge": lambda **_: basarili({"acc_recharge": {"prize": 0, "gem": 0}}),
    "get_card_info": lambda **_: basarili({"gem_shop": {"mcts": 0, "mcstas": 0, "mcprize": 0, "mcgem": 0, "fg": 0}}),
    "get_first_charge": lambda **_: basarili({"first_recharge": {"if_fc": 0, "if_prize": 0}}),
})

op_yolu("/activity", {
    "get_forcasttime_status": lambda **_: basarili({"activity": {"forcastacts": []}}),
}, lambda **_: basarili({"activity": {"status": []}}))

sabit(34, 3401, {"store": {k: 0 for k in ["ce", "rl", "rl_y", "ts", "ts_p", "ts_c", "cp", "cp_t", "cc",
                                          "ts_m", "cm", "ts_s", "cs", "cs_fd", "ts_g", "cg_fd"]}})
sabit(45, 4501, {})
op_yolu("/online_package", {}, lambda **_: basarili({"online_package": {"online_time": 0, "reward_index_list": []}}))
op_yolu("/trailer", {}, lambda **_: basarili({"trailers": []}))
op_yolu("/seven", {}, lambda **_: basarili({"seven_count": 0, "can_sign": 0}))
sabit(40, 4003, {"ars": {"sl": 0, "ss": 0, "sr": 0}})
op_yolu("/reward_mission", {}, lambda **_: basarili({"reward_mission": {
    "max_acpt": 0, "buy_num": 0, "buy_gem": 0, "spec": [], "acpted": [], "acpt": []}}))
def ladder_json(k):
    """RankBattleDataManager.InitDataInRankStage dl[1].plist (3 oyuncu), dc ve dl[1].fight okur."""
    secili = [{"pos": s["pos"], "id": s["id"]} for s in k["secili"]]
    return {"ladder": {"st": 0, "c": 0, "cb": 0, "ts": 0, "r": 0, "rh": 0, "cd": 0, "ts_n": 0, "ta": 0, "el": [],
                       "tl": [{"index": 1, "status": 1, "plist": secili}],
                       "dl": [{"plist": secili, "fight": takim_gucu(k)}],
                       "dc": (k["secili_amigolar"] or [0])[0]}}


sabit(21, 2103, lambda: ladder_json(kayit()))
sabit(10, 1001, {"trial": {}, "trial_count": []})
sabit(47, 4701, {"league": {}, "stage_list": []})
sabit(51, 5101, {"restriction": {}, "pl": []})
op_yolu("/activity_mission", {}, lambda **_: basarili({"mission": {"mission": []}}))
sabit(54, 5433, {"gid": 0, "r": 0, "ta": 0, "ts": 0, "gn": ""})
sabit(52, 5203, {})
sabit_yol("/icon", {"icons": []})
sabit(57, 5701, {})
op_yolu("/facebook_gift", {}, lambda **_: basarili({"info": {"fan_count": 0, "list": "000", "share_state": 0, "invite_state": 0}}))
sabit(58, 5811, {"ll": []})
sabit(60, 6003, {"act_trial": {"trial_count": 0}})
sabit(110, 11001, {"guide": 0})


def rehber_kaydet(alanlar, baslangic=False, **_):
    """GuideCom.lua: data={"datalist":[{"type":..,"step":..}]}; cevapta guide_step.all/start şart."""
    turler = [int(d["type"]) for d in param_coz(alanlar.get("data", "")).get("datalist", []) if "type" in d]
    with durum.kilit:
        k = kayit()
        liste = k.setdefault("rehber_baslangic", []) if baslangic else k["rehber"]
        liste.extend(t for t in turler if t not in liste)
        durum.kaydet()
    return basarili({"guide_step": rehber_json(kayit())})


op_yolu("/sync_guide_step", {"start_guide_step": lambda **a: rehber_kaydet(baslangic=True, **a)}, rehber_kaydet)
sabit_yol("/time_pay_gift", {"gift_info": {"seconds": 0}})
sabit_yol("/player_book", {"book_info": {"circle": 0, "fight_power": 0, "point_list": []}})

# lobi açıldıktan sonra periyodik gelenler
sabit(33, 3301, {"newinfo": []})
sabit(17, 1711, {"count": 0})

# ---------------------------------------------------------------- takım ve çanta

sabit(12, 1201, lambda: {"team": takim_json(kayit())})


@yon.proto(12, 1202)
def kadro_degistir(param, **_):
    liste = (param or {}).get("paramlist") or []
    if len(liste) >= 3:
        _, pos, pid = (int(x) for x in liste[:3])
        with durum.kilit:
            k = kayit()
            if str(pid) in k["oyuncular"]:
                secili = [s for s in k["secili"] if s["pos"] != pos and s["id"] != pid]
                secili.append({"pos": pos, "id": pid})
                k["secili"] = sorted(secili, key=lambda s: s["pos"])
                durum.kaydet()
    return basarili({"team": takim_json(kayit())})


op_yolu("/op_bag", {}, lambda **_: basarili({"backpack": canta_json(kayit())}))
sabit(1, 113, lambda: {"backpack": canta_json(kayit())})


# ---------------------------------------------------------------- başlatma

def obb_bul():
    kok = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for dizin, _, dosyalar in os.walk(os.path.join(kok, "apk")):
        for d in dosyalar:
            if d.endswith(".obb") and "yamali" not in d:
                return os.path.join(dizin, d)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8881)
    ap.add_argument("--obb", default=None)
    arg = ap.parse_args()
    AYAR["port"] = arg.port
    AYAR["obb"] = arg.obb or obb_bul()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    if not AYAR["obb"]:
        log.warning("Orijinal OBB bulunamadı; yapılandırma dosyaları servis edilemeyecek.")
    import panel
    panel.kur(yon, durum)
    sunucu = http_sunucu_kur("0.0.0.0", AYAR["port"], yon, lambda sid: sid)
    log.info("Sunucu hazır: port %d  |  Panel: http://localhost:%d/panel", AYAR["port"], AYAR["port"])
    try:
        sunucu.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
