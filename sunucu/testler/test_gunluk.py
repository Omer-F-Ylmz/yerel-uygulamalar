"""gunluk.py işleyicilerinin testleri: python -m unittest discover -s sunucu/testler"""
import json
import os
import random
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cekirdek import Yonlendirici, json_yaz, param_coz  # noqa: E402
from durum import Durum  # noqa: E402
import gunluk  # noqa: E402


def null_yok(nesne):
    if nesne is None:
        return False
    if isinstance(nesne, dict):
        return all(null_yok(v) for v in nesne.values())
    if isinstance(nesne, list):
        return all(null_yok(v) for v in nesne)
    return True


class GunlukTesti(unittest.TestCase):
    def setUp(self):
        random.seed(1)
        self.gecici = tempfile.TemporaryDirectory()
        self.durum = Durum(os.path.join(self.gecici.name, "kayit.json"))
        self.durum.hesap_ac("test")
        with self.durum.kilit:  # ödüller görünsün diye para birimleri tavanın altında
            for ad in ("gold", "gem", "star"):
                self.durum.veri[ad] = 1000
        self.yon = Yonlendirici()
        gunluk.kur(self.yon, self.durum)

    def tearDown(self):
        self.gecici.cleanup()

    def dogrula(self, cevap, basari=True):
        if basari:
            self.assertEqual(cevap["result"], 0, cevap)
        self.assertTrue(null_yok(cevap), "JSON null var: %r" % (cevap,))
        metin = json_yaz(cevap)
        self.assertIn('"result":0' if basari else '"result":-1', metin)
        json.loads(metin)
        return cevap.get("data")

    def yol(self, yol, op="", param="0", basari=True, **alanlar):
        alanlar.update(op=op, param=param)
        return self.dogrula(self.yon.yollar[yol](alanlar=alanlar, param=param_coz(param), oturum="t", istek=None),
                            basari)

    def proto(self, proto, sub, param=None, basari=True):
        metin = json.dumps(param) if param is not None else ""
        return self.dogrula(self.yon.protolar[(proto, sub)](alanlar={}, param=param_coz(metin), oturum="t",
                                                            istek=None), basari)

    # ------------------------------------------------ imzalar
    def test_aylik_imza(self):
        d = self.yol("/player_month_checkin", "get_checkin_status")["monthchckin"]
        self.assertEqual(set(d), {"month_check_status", "month_cumulative_prize_status", "last_checkin_ts", "day",
                                  "if_cancheck"})
        self.assertEqual((d["day"], d["last_checkin_ts"], d["if_cancheck"]), (0, 0, 0))
        gold = self.durum.veri["gold"]
        for i in range(1, 11):
            d = self.yol("/player_month_checkin", "monthchckin", str(i))
            self.assertIn("updatelist", d)
        m = d["monthchckin"]
        self.assertEqual(m["day"], 10)
        self.assertEqual(m["month_check_status"], "1" * 10)
        self.assertGreater(m["last_checkin_ts"], 0)
        self.assertGreaterEqual(self.durum.veri["gold"], gold)
        d = self.yol("/player_month_checkin", "get_cumulative_prize", '{"paramlist":[10]}')["monthchckin"]
        self.assertTrue(d["month_cumulative_prize_status"].endswith("1"))
        self.yol("/player_month_checkin", "get_cumulative_prize", '{"paramlist":[10]}', basari=False)
        self.yol("/player_month_checkin", "get_cumulative_prize", '{"paramlist":[15]}', basari=False)

    def test_yedi_gun(self):
        d = self.yol("/seven", "get_status")
        self.assertEqual(d, {"seven_count": 0, "can_sign": 1})
        for _ in range(7):
            d = self.yol("/seven", "checkin")
            self.assertIn("paramlist", d["updatelist"])
        self.assertEqual((d["seven_count"], d["can_sign"]), (7, 0))
        self.yol("/seven", "checkin", basari=False)

    # ------------------------------------------------ enerji
    def test_enerji(self):
        s = self.yol("/player_strength", "query_info")["strength"]
        self.assertEqual(s["free_get_status"], 0)
        once = s["strength"]
        s = self.yol("/player_strength", "get_strength", '{"paramlist":[2]}')["strength"]
        self.assertEqual(s["free_get_status"], 10)
        self.assertGreater(s["strength"], once)
        s = self.yol("/player_strength", "re_strength", '{"paramlist":[4]}')["strength"]
        self.assertEqual(s["free_get_status"], 1010)
        gem = self.durum.veri["gem"]
        s2 = self.yol("/player_strength", "buy_strength")["strength"]
        self.assertEqual(s2["strength"], s["strength"] + gunluk.SATIN_ALMA_ENERJISI)
        self.assertEqual(self.durum.veri["gem"], gem)

    # ------------------------------------------------ görevler
    def test_gorevler(self):
        d = self.yol("/player_mission", "get_mission_info")["mission"]
        self.assertEqual(set(d), {"mission", "is_gotpriaze", "complete_cnts"})
        self.assertGreater(len(d["mission"]), 100)
        hepsi = {m["id"] for m in d["mission"]}
        for m in d["mission"][:20]:
            self.assertEqual(m["progress1"], gunluk.V["gorev"][m["id"]][1])
        self.assertEqual(self.yol("/player_mission", "get_growth_mission_day")["growth_mission_day"], 7)
        gid = next(g for g in hepsi if gunluk.V["gorev"][g][0] == 2)
        d = self.yol("/player_mission", "get_mission_reward", '{"paramlist":[%d]}' % gid)
        self.assertEqual(d["updatelist"]["paramlist"]["mission"][0], {"id": gid, "progress1": -1})
        self.assertIn("complete_cnts", d)
        kalan = {m["id"] for m in self.yol("/player_mission", "get_mission_info")["mission"]["mission"]}
        self.assertNotIn(gid, kalan)
        # aynı görev ikinci kez ödül vermez ama istek yine başarılı (liste boş)
        d = self.yol("/player_mission", "get_mission_reward", '{"paramlist":[%d]}' % gid)
        self.assertEqual(d["updatelist"]["paramlist"]["mission"], [])

    def test_zincir_gorev_acilir(self):
        ids = {m["id"] for m in self.yol("/player_mission", "get_mission_info")["mission"]["mission"]}
        onceki = next(g for g in sorted(ids) if g in gunluk.V["sonraki"] and g not in gunluk.V["iki_hafta_kume"])
        sonraki = gunluk.V["sonraki"][onceki][0]
        self.assertNotIn(sonraki, ids)
        d = self.yol("/player_mission", "get_mission_reward", '{"paramlist":[%d]}' % onceki)
        self.assertIn({"id": sonraki, "progress1": gunluk.V["gorev"][sonraki][1]},
                      d["updatelist"]["paramlist"]["mission"])
        ids = {m["id"] for m in self.yol("/player_mission", "get_mission_info")["mission"]["mission"]}
        self.assertIn(sonraki, ids)
        self.assertNotIn(onceki, ids)

    def test_buyume_gorevleri(self):
        self.yol("/player_mission", "get_complete_cnts_reward", '{"paramlist":[]}', basari=False)
        iki = gunluk.V["iki_hafta"][:3]
        d = self.yol("/player_mission", "get_mission_reward", '{"paramlist":[%s]}' % ",".join(map(str, iki)))
        self.assertEqual(d["complete_cnts"], 3)
        d = self.yol("/player_mission", "get_complete_cnts_reward", '{"paramlist":[]}')
        self.assertEqual(d["mission"]["is_gotpriaze"], 1)
        esya = gunluk.V["iki_hafta_odul"][1]
        if esya in gunluk.ESYA_VERI:
            self.assertIn({"id": esya, "count": 3}, d["updatelist"]["paramlist"]["item_list"])
        self.yol("/player_mission", "get_complete_cnts_reward", '{"paramlist":[]}', basari=False)

    def test_gunluk_gorevler_her_gun_sifirlanir(self):
        gid = next(g for g, v in gunluk.V["gorev"].items() if v[0] == 1)
        self.yol("/player_mission", "get_mission_reward", '{"paramlist":[%d]}' % gid)
        with self.durum.kilit:
            self.durum.veri["gunluk"]["gun"] = "2000-01-01"
        ids = {m["id"] for m in self.yol("/player_mission", "get_mission_info")["mission"]["mission"]}
        self.assertIn(gid, ids)

    # ------------------------------------------------ çevrimiçi ödül
    def test_cevrimici(self):
        d = self.yol("/online_package", "get_status")["online_package"]
        self.assertEqual(d["reward_index_list"], [])
        self.assertGreaterEqual(d["online_time"], max(r[1] for r in gunluk.V["cevrimici"]))
        d = self.yol("/online_package", "get_reward", '{"paramlist":[1]}')
        self.assertEqual(d["online_package"]["reward_index_list"], [{"index": 1}])
        self.yol("/online_package", "get_reward", '{"paramlist":[1]}', basari=False)
        self.yol("/online_package", "time_start")
        self.yol("/online_package", "time_end")

    # ------------------------------------------------ elmas dükkânı
    def test_ay_karti_ve_reklam(self):
        d = self.yol("/gem_shop", "get_card_info")["gem_shop"]
        self.assertEqual(set(d), {"mcts", "mcstas", "mcprize", "mcgem", "fg"})
        self.assertEqual((d["mcstas"], d["mcprize"]), (1, 0))
        gem = self.durum.veri["gem"]
        d = self.yol("/gem_shop", "get_prize")
        self.assertEqual(d["gem_shop"]["mcprize"], 1)
        self.assertEqual(self.durum.veri["gem"], gem + 100)
        self.yol("/gem_shop", "get_prize", basari=False)
        d = self.yol("/gem_shop", "get_free_gem")
        self.assertIn("gem", d["updatelist"]["paramlist"])
        self.assertEqual(d["gem_shop"]["fg"], 0)

    def test_ilk_sarj_ve_sarj_etkinlikleri(self):
        d = self.yol("/gem_shop", "get_first_charge", '{"paramlist":0}')
        self.assertEqual(d, {"first_recharge": {"if_fc": 1, "if_prize": 0}})
        d = self.yol("/gem_shop", "get_fc_prize", '{"paramlist":0}')
        self.assertEqual(d["first_recharge"]["if_prize"], 1)
        self.yol("/gem_shop", "get_fc_prize", '{"paramlist":0}', basari=False)

        d = self.yol("/gem_shop", "get_conti_charge", '{"paramlist":0}')
        self.assertEqual(d["id"], gunluk.SARJ0_ETKINLIK)
        self.assertEqual(set(d["conti_recharge"]), {"status", "prize", "status0", "prize0"})
        d = self.yol("/gem_shop", "get_conti_prize", '{"paramlist":[0]}')
        self.assertEqual(d["conti_recharge"]["prize0"], 1)
        d = self.yol("/gem_shop", "get_conti_prize", '{"paramlist":[2]}')
        self.assertEqual(d["conti_recharge"]["prize"][-2], "1")
        self.yol("/gem_shop", "get_conti_prize", '{"paramlist":[2]}', basari=False)

        d = self.yol("/gem_shop", "get_acc_charge", '{"paramlist":0}')["acc_recharge"]
        self.assertGreaterEqual(d["gem"], max(r[1] for r in gunluk.V["sarj1"]))
        d = self.yol("/gem_shop", "get_acc_prize", '{"paramlist":[0]}')["acc_recharge"]
        self.assertTrue(d["prize"].endswith("1"))

    # ------------------------------------------------ etkinlikler
    def test_etkinlikler(self):
        d = self.yol("/activity", "get_status")["activity"]["status"]
        ids = {e["id"] for e in d}
        self.assertTrue({10001, 10011, 10013}.issubset(ids))
        for e in d:
            self.assertEqual(set(e), {"id", "bt", "et", "ct", "lvf", "lvt"})
            self.assertLess(e["bt"], e["ct"])
        self.assertEqual(self.yol("/activity", "get_forcasttime_status"), {"activity": {"forcastacts": []}})

    def test_harika_gorevler(self):
        liste = self.yol("/activity_mission", "get_mission_info")["mission"]["mission"]
        self.assertTrue(liste)
        gid = liste[0]["id"]
        d = self.yol("/activity_mission", "get_mission_reward", '{"paramlist":%d}' % gid)
        self.assertEqual(d["updatelist"]["paramlist"]["activity_mission"], [{"id": gid, "progress1": -1}])
        self.yol("/activity_mission", "get_mission_reward", '{"paramlist":%d}' % gid, basari=False)

    def test_fragman(self):
        d = self.yol("/trailer", "get_trailer_info")["trailers"]
        self.assertEqual([t["type"] for t in d], [1, 2])
        d = self.yol("/trailer", "voute", '{"paramlist":[1,1]}')["trailers"]
        self.assertEqual(d[0]["vote_info"], 1)
        d = self.yol("/trailer", "res_reward", '{"paramlist":[1,1]}')["trailers"]
        self.assertEqual(d[0]["res_reward"], 1)

    def test_iki_hafta_anket(self):
        self.assertEqual(self.yol("/two_week", "get_checkin_status"), {"checkin": {"2ws": 0}})
        self.assertEqual(self.yol("/answer", "get_status")["answer"]["status"], 1)

    def test_yuce_kart_ve_fon(self):
        d = self.yol("/month_card", proto_sub="101")["supreme_month_card"]
        self.assertEqual((d["is_buy"], d["is_receive"]), (1, 0))
        d = self.yol("/month_card", proto_sub="102")
        self.assertEqual(d["supreme_month_card"]["is_receive"], 1)
        self.yol("/month_card", proto_sub="102", basari=False)
        d = self.yol("/growth_fund", proto_sub="101")["growth_fund"]
        self.assertEqual(d, {"is_buy": 0, "count": 0, "accepted": []})
        self.yol("/growth_fund", param="[1]", proto_sub="103", basari=False)
        self.assertEqual(self.yol("/growth_fund", proto_sub="102")["growth_fund"]["is_buy"], 1)
        d = self.yol("/growth_fund", param="[1]", proto_sub="103")
        self.assertEqual(d["growth_fund"]["accepted"], [1])

    # ------------------------------------------------ posta ve CDK
    def test_posta(self):
        self.assertEqual(self.proto(17, 1711, {})["count"], 1)
        liste = self.proto(17, 1701)["mail_title_list"]
        self.assertEqual(len(liste), 1)
        p = liste[0]
        for ad in ("mail_id", "title", "content", "source_id", "source_name", "mail_time", "mail_time_term",
                   "status_read", "status_attach", "type", "attach", "status_favorite"):
            self.assertIn(ad, p)
        self.assertEqual(set(p["title"]), {"is_template", "key", "params"})
        self.assertEqual(p["status_attach"], 1)
        self.assertEqual(len(self.proto(17, 1702)["mail_title_list"]), 1)
        mid = p["mail_id"]
        self.assertEqual(self.proto(17, 1705, {"mailIDList": [mid]})["mail_id_list"], [mid])
        gem = self.durum.veri["gem"]
        d = self.proto(17, 1708, {"mailIDList": [mid]})
        self.assertEqual(self.durum.veri["gem"], gem + 1000)
        self.assertEqual(d["updatelist"]["paramlist"]["gem"], 1000)
        self.assertEqual(self.proto(17, 1702)["mail_title_list"], [])
        self.assertEqual(self.proto(17, 1712, {"sec": 60})["count"], 0)
        self.proto(17, 1707, {"mailIDList": [mid], "status": 1})
        self.assertEqual(len(self.proto(17, 1704)["mail_title_list"]), 1)
        self.proto(17, 1707, {"mailIDList": [mid], "status": 0})
        self.assertEqual(self.proto(17, 1703)["mail_title_list"], [])
        self.proto(17, 1706, {"mailIDList": [mid]})
        self.assertEqual(self.proto(17, 1700)["mail_title_list"], [])

    def test_cdk_postayla_gelir(self):
        self.proto(17, 1701)
        self.yol("/exchange_cdkey", param="HERHANGIBIRKOD")
        liste = self.proto(17, 1702)["mail_title_list"]
        self.assertEqual(len(liste), 2)
        d = self.proto(17, 1709, {})
        self.assertEqual(sorted(d["mail_id_list"]), sorted(p["mail_id"] for p in liste))
        self.assertEqual(self.proto(17, 1702)["mail_title_list"], [])

    def test_kayan_yazi(self):
        self.assertEqual(self.proto(45, 4501), {"gm_pl": [], "pl": []})

    # ------------------------------------------------ ödeme
    def test_odeme_ucretsiz(self):
        gem = self.durum.veri["gem"]
        d = self.yol("/get_billno", goods_id="xianyugame.jqlm.g60", serverid="1", plat="google")
        self.assertTrue(d["bill_no"])
        self.assertEqual(self.durum.veri["gem"], gem + 66)
        self.assertEqual(d["gem"], self.durum.veri["gem"])
        self.assertEqual(d["updatelist"]["paramlist"]["gem"], 66)
        for yol in ("/query_order", "/google_buy", "/query_balance_and_buy"):
            s = self.yol(yol, bill_no=d["bill_no"], plat="google")
            self.assertEqual(s["gem"], self.durum.veri["gem"])
            self.assertEqual(s["product_id"], "xianyugame.jqlm.g60")
        self.assertEqual(self.durum.veri["gem"], gem + 66)  # sorgular ikinci kez vermez
        d = self.yol("/get_billno", goods_id="bilinmeyen.urun")
        self.assertEqual(d["gem"], self.durum.veri["gem"])
        self.assertIn("product_id", self.yol("/iap_buy", receipt="abc"))

    def test_kayit_kalici(self):
        self.yol("/seven", "checkin")
        yeni = Durum(self.durum.yol)
        self.assertEqual(yeni.veri["gunluk"]["yedi"]["sayi"], 1)

    def test_tum_dusus_listeleri_cozulur(self):
        for did in gunluk.V["dusus"]:
            odul = gunluk.dusus_coz(did)
            self.assertEqual(set(odul), {"exp", "exp_team", "gold", "gem", "star", "esyalar"})


if __name__ == "__main__":
    unittest.main()
