"""modlar.py işleyicilerinin testi: python -m unittest discover -s sunucu/testler"""
import json
import os
import random
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cekirdek import Yonlendirici, json_yaz  # noqa: E402
from durum import Durum  # noqa: E402
import mac  # noqa: E402
import modlar  # noqa: E402

UST = {"ts_begin", "ladder_count", "battle_type", "battle_id", "droplist_id", "enemy_uin", "scene", "status",
       "is_home_team", "possession", "remaining_time", "self_hp", "enemy_hp", "battle_player_self",
       "battle_player_enemy", "cheer_self", "cheer_enemy", "team_level_self", "team_level_enemy",
       "team_icon_self", "team_icon_enemy", "team_name_self", "team_name_enemy", "skill_cd"}
OYUNCU = {"id", "enemy_id", "level", "break_level", "color", "pos", "skill_list", "attr"}
SONUC = {"battle_type", "battle_id", "win", "result_star", "exp", "gold", "gem", "star", "exp_team", "item_list",
         "player_exp_old", "player_exp_new"}


def null_yok(nesne):
    if nesne is None:
        return False
    if isinstance(nesne, dict):
        return all(null_yok(v) for v in nesne.values())
    if isinstance(nesne, list):
        return all(null_yok(v) for v in nesne)
    return True


def pl(*x):
    return {"paramlist": list(x)}


class ModlarTesti(unittest.TestCase):
    def setUp(self):
        random.seed(1)
        self.gecici = tempfile.TemporaryDirectory()
        self.durum = Durum(os.path.join(self.gecici.name, "kayit.json"))
        self.k = self.durum.hesap_ac("test")
        self.yon = Yonlendirici()
        mac.kur(self.yon, self.durum)
        modlar.kur(self.yon, self.durum)

    def tearDown(self):
        self.gecici.cleanup()

    def cagir(self, proto, sub, param=None, basari=True):
        cevap = self.yon.protolar[(proto, sub)](alanlar={}, param=param if param is not None else {},
                                                oturum="t", istek=None)
        self.assertTrue(null_yok(cevap), "JSON null var: %s" % cevap)
        json.loads(json_yaz(cevap))
        if not basari:
            return cevap
        self.assertEqual(cevap["result"], 0, cevap)
        return cevap["data"]

    def mac_oyna(self, tur, rakip, kazan=True, dalga=None):
        msg = self.cagir(7, 701, pl(tur, rakip, 0, 0))["battlemsg"]
        self.assertEqual(set(msg), UST)
        self.assertEqual(msg["battle_type"], tur)
        for taraf in ("battle_player_self", "battle_player_enemy"):
            for d in msg[taraf]:
                self.assertEqual(len(d["team"]), 3)
                for p in d["team"]:
                    self.assertEqual(set(p), OYUNCU)
                    self.assertGreater(p["attr"]["fight"], 8)
        if dalga:
            self.assertEqual(len(msg["battle_player_enemy"]), dalga)
        data = self.cagir(7, 702, pl(1 if kazan else 0, 3, 1, 1, 1, 0, 0, 0))
        self.assertEqual(set(data["battlemsg"]), SONUC)
        self.assertEqual(data["battlemsg"]["battle_type"], tur)
        return data

    # ------------------------------------------------ yapay zekâ
    def test_ai_gucu_hedefe_yakin(self):
        for hedef in (5000, 300000, 2000000):
            dalga = modlar.ai_dalgalar(42, hedef, 80)[0]
            guc = sum(p["attr"]["fight"] for p in dalga)
            self.assertLess(abs(guc - hedef) / hedef, 0.05, (hedef, guc))
            self.assertEqual(len({p["id"] for p in dalga}), 3)

    # ------------------------------------------------ sıralama
    def test_merdiven_lobi_sekli_ve_listeler(self):
        l = self.cagir(21, 2103)["ladder"]
        for anahtar in ("st", "c", "cb", "ts", "r", "rh", "cd", "ts_n", "ta", "el", "tl", "dl", "dc", "top", "en_l"):
            self.assertIn(anahtar, l)
        self.assertEqual(len(l["dl"][0]["plist"]), 3)
        self.assertEqual(len(l["el"]), 4)
        self.assertTrue(all(e["r"] < l["r"] for e in l["el"]))
        self.assertEqual([t["r"] for t in l["top"]], [1, 2, 3])
        for e in l["el"] + l["top"]:
            self.assertLess(e["e"]["uin"], 1400000000)
            self.assertTrue(e["e"]["name"])
        for sub in (2108, 2109):
            liste = self.cagir(21, sub)["ladder_list"]
            self.assertEqual(len(liste), 50)
            self.assertEqual([e["id"] for e in liste], list(range(1, 51)))
            self.assertGreater(len({e["name"] for e in liste}), 45)
        bilgi = self.cagir(21, 2102, pl(l["el"][0]["e"]["uin"]))["ladder_uin_info"]
        self.assertEqual(bilgi["r"], l["el"][0]["r"])
        self.assertEqual(len(bilgi["e"]["players"][0]["team"]), 3)
        self.assertTrue(bilgi["e"]["cheers"][0]["id"])
        kendi = self.cagir(21, 2102, pl(self.k["uin"]))["ladder_uin_info"]
        self.assertEqual(kendi["r"], l["r"])

    def test_merdiven_kazaninca_sira_yukselir(self):
        l = self.cagir(21, 2103)["ladder"]
        hedef = min(l["el"], key=lambda e: e["r"])
        data = self.mac_oyna(7, hedef["e"]["uin"])
        self.assertEqual(data["ladder"]["rk"][0], hedef["r"])
        self.assertEqual(data["ladder"]["rk"][1], l["r"])
        self.assertEqual(len(data["ladder"]["tm_s"][0]), 3)
        yeni = self.cagir(21, 2103)["ladder"]
        self.assertEqual(yeni["r"], hedef["r"])
        # yenilen takım bizim eski sıramıza düşer
        bilgi = self.cagir(21, 2102, pl(hedef["e"]["uin"]))["ladder_uin_info"]
        self.assertEqual(bilgi["r"], l["r"])
        log = self.cagir(21, 2106)["log"]
        self.assertEqual(log[0]["re"], 1)
        # kaybedince sıra değişmez
        r = yeni["r"]
        self.mac_oyna(7, yeni["el"][0]["e"]["uin"], kazan=False)
        self.assertEqual(self.cagir(21, 2103)["ladder"]["r"], r)

    def test_merdiven_takim_amigo_gorev_supurme(self):
        pid = int([p for p in self.k["oyuncular"]][-1])
        data = self.cagir(21, 2104, pl(1, pid))
        self.assertEqual(data["team"]["team_list"]["plist"][0]["id"], pid)
        self.assertEqual(self.cagir(21, 2113, pl(2001))["team"]["team_list"]["cheer"], 2001)
        r = self.cagir(21, 2103)["ladder"]["r"]
        self.assertLess(self.cagir(21, 2112)["ladder"]["r"], r)
        self.assertEqual(self.cagir(21, 2110, pl(1))["ladder"]["ta"], 1)
        self.assertIn("updatelist", self.cagir(21, 2111, pl(2000001)))

    # ------------------------------------------------ aranan / usta / açık / arena
    def test_aranan(self):
        w = self.cagir(24, 2401)["wanted"]
        self.assertEqual(len(w["enemy_list"]), 3)
        altin = self.k["gold"]
        self.k["gold"] = 0
        data = self.mac_oyna(8, w["enemy_list"][2]["uin"])
        self.assertEqual(data["battlemsg"]["gold"], w["enemy_list"][2]["bounty"])
        self.assertEqual(self.k["gold"], w["enemy_list"][2]["bounty"])
        self.k["gold"] = altin
        self.assertNotEqual(self.cagir(24, 2401)["wanted"]["enemy_list"][0]["uin"], w["enemy_list"][0]["uin"])

    def test_usta(self):
        m = self.cagir(52, 5203)["master_battle"]
        self.assertEqual(len(m["el"]), 5)
        self.assertEqual(len(m["tl"]), 3)
        self.assertTrue(all(len(t["plist"]) == 3 for t in m["tl"]))
        rakip = m["el"][0]
        self.assertEqual(len(self.cagir(52, 5214, pl(rakip["e"]["uin"]))["players"]), 3)
        data = self.mac_oyna(12, rakip["e"]["uin"], dalga=3)
        self.assertEqual(data["master"]["sa"][1], rakip["sa"])
        self.assertEqual(len(data["master"]["tm_e"]), 3)
        self.assertEqual(self.cagir(52, 5203)["master_battle"]["sr"], data["master"]["sa"][0])
        self.assertEqual(len(self.cagir(52, 5213)["master_list"]), 50)
        self.assertEqual(len(self.cagir(52, 5215)["ch"]), 10)
        t = self.cagir(52, 5204, pl(1, 1, 0))["master_battle"]["tl"][0]
        self.assertEqual(len(t["plist"]), 2)

    def test_acik_turnuva(self):
        o = self.cagir(2059, 205901)["open_match"]
        self.assertEqual(o["st"], 1)
        self.assertEqual(len(o["el"]), 3)
        self.assertEqual(len(o["cl"]), 3)
        self.assertTrue(all(t["status"] == 3 for t in o["tl"]))
        data = self.mac_oyna(13, o["el"][1]["e"]["uin"], dalga=3)
        self.assertGreater(data["open"]["f"], 0)
        o = self.cagir(2059, 205915, pl(1, 1, 1, 1, 1, 1, 1))["open_match"]
        self.assertEqual(o["st"], 2)                      # 2. düğüm sandık
        data = self.cagir(2059, 205903, pl(2))
        self.assertIn("updatelist", data)
        self.assertEqual(data["open_match"]["st"], 3)
        self.assertEqual(data["open_match"]["chl"][0]["ce"], 1)
        self.mac_oyna(13, data["open_match"]["el"][0]["e"]["uin"])
        o = self.cagir(2059, 205901)["open_match"]
        self.assertEqual(o["st"], 4)                      # destek düğümü
        self.assertTrue(o["sl"])
        self.assertEqual(self.cagir(2059, 205905, pl())["open_match"]["st"], 5)
        self.assertGreater(self.cagir(2059, 205916, pl(*[p["id"] for p in o["tl"][0]["plist"]], 0))["str"], 0)
        self.assertEqual(self.cagir(2059, 205917)["open_match"]["st"], 1)

    def test_arena(self):
        a = self.cagir(32, 3201)["arena"]
        self.assertEqual(a["st"], 0)
        a = self.cagir(32, 3202, pl(1))["arena"]
        self.assertEqual(a["st"], 1)
        for _ in range(a["s_m"]):
            a = self.cagir(32, 3203, pl(a["pl"][0]["id"]))["arena"]
        self.assertEqual(a["st"], 2)
        self.assertTrue(all(len(t["plist"]) == 3 for t in a["tl"]))
        self.mac_oyna(11, 0, dalga=3)
        self.assertEqual(self.cagir(32, 3201)["arena"]["c_w"], 1)
        self.assertEqual(self.cagir(32, 3208, basari=False)["result"], -1)
        data = self.cagir(32, 3206)
        self.assertIn("updatelist", data)
        self.assertEqual(data["arena"]["st"], 0)

    # ------------------------------------------------ PvE modları (7/705 üzerinden)
    def test_deneme(self):
        t = self.cagir(10, 1001)["trial"]["trial_count"]
        self.assertEqual([x["type"] for x in t], [1, 2, 3, 4])
        bid = modlar.MD["deneme"]["seviye"][1][0][1]
        self.cagir(10, 1002, pl(1, 1))
        self.cagir(7, 705, pl(bid))
        data = self.cagir(7, 702, pl(0, 0, 2, 1, 1, 0, 0, 0))
        self.assertEqual(data["battlemsg"]["battle_type"], 5)
        self.assertEqual(data["battlemsg"]["win"], 1)
        self.assertTrue(data["battlemsg"]["item_list"])     # 2 dalga ödülü
        self.cagir(10, 1005, pl(1, 1))
        data = self.cagir(7, 702, pl(1, 0, 3, 0, 0, 0, 0, 1))
        self.assertTrue(data["battlemsg"]["item_list"])

    def test_lig(self):
        lig = self.cagir(47, 4701)["league"]["stage_list"]
        self.assertEqual(len(lig), len(modlar.MD["lig"]))
        self.assertTrue(all(s["stage_status"] == 2 for s in lig))
        sid, maclar = modlar.MD["lig"][0]
        data = self.cagir(47, 4704, {"stage": sid, "battle_index": maclar[0][0], "count": 3})
        self.assertEqual(len(data["resultlist"]), 3)
        # tür 9 maç sonucu mac.py'de işlenir; düşüş listesi bu modülden eklendi
        self.cagir(47, 4702, {"stage": sid, "battle_index": maclar[0][0]})
        self.cagir(7, 705, pl(maclar[0][1]))
        data = self.cagir(7, 702, pl(1, 3, 1))
        self.assertEqual(data["battlemsg"]["battle_type"], 9)

    def test_sokak_macerasi(self):
        def op(ad, *liste):
            cevap = self.yon.yollar["/op_rewardmatch"](alanlar={"op": ad}, param=pl(*liste), oturum="t", istek=None)
            self.assertEqual(cevap["result"], 0)
            self.assertTrue(null_yok(cevap))
            return cevap["data"]["reward_match"]

        r = op("get_info")
        self.assertEqual(r["status"], 0)
        self.assertGreater(r["dc_b"], 0)
        r = op("enter", 0)
        self.assertEqual(r["status"], 1)
        self.assertEqual(len(r["card_list"]), 3)
        esya = next(c for c in r["card_list"] if c["type"] == 3)
        r = op("select", esya["index"], 1)
        self.assertEqual(r["select_count"], 1)
        self.assertTrue(r["bag_item"])
        kart = next(c for c in r["card_list"] if c["type"] == 2)
        r = op("select", kart["index"], 1)
        self.assertEqual(r["status"], 2)
        self.cagir(7, 705, pl(r["battle_id"]))
        data = self.cagir(7, 702, pl(1, 3, 1))
        self.assertEqual(len(data["rm"]), 7)
        self.assertGreater(data["rm"][3], data["rm"][0])
        r = op("battle_result", 1)
        self.assertEqual(r["status"], 1)
        self.assertEqual(r["combo"], 1)
        self.assertGreater(r["fee_temp"], 0)
        kart = next(c for c in r["card_list"] if c["type"] == 2)
        r = op("forward", kart["index"], 1)
        self.assertEqual(r["combo"], 2)
        data = self.cagir(7, 702, pl(1, 0, 0, 0, 0, 0, 0, 1))
        self.assertEqual(data["rm"][3], r["fee_temp"])
        r = op("leave")
        self.assertEqual(r["status"], 3)
        r = op("clear")
        self.assertEqual(r["status"], 0)
        self.assertGreater(r["fee_history"], 0)
        # Lua tarafı aynı veriyi 14/14xx ile alır
        self.assertEqual(self.cagir(14, 1401)["reward_match"]["status"], 0)

    def test_digerleri(self):
        self.assertIn("live_show", self.cagir(8, 801))
        self.assertEqual(self.cagir(60, 6003)["act_trial"]["trial_count"], 0)
        self.assertEqual(self.cagir(60, 6001, pl(1007))["qualifiy"]["lv"], 2)
        liste = self.cagir(40, 4001, pl(2))["rank_list"]
        self.assertEqual(len(liste), 30)
        self.assertIn(self.k["uin"], [e["u"] for e in liste])
        self.assertIn("updatelist", self.cagir(40, 4002, pl(2)))

    def test_bilinmeyen_tur_mac_pye_gider(self):
        msg = self.cagir(7, 701, pl(0, 0, 0, 100))["battlemsg"]
        self.assertEqual(msg["battle_type"], 0)
        self.assertEqual(self.cagir(7, 702, pl(1, 3, 1))["battlemsg"]["battle_type"], 0)


if __name__ == "__main__":
    unittest.main()
