"""mac.py işleyicilerinin duman testi: python -m unittest discover -s sunucu/testler"""
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

# lua/MatchLoader.lua:32 tutorial_data'nın anahtar yapısı
UST = {"ts_begin", "ladder_count", "battle_type", "battle_id", "droplist_id", "enemy_uin", "scene", "status",
       "is_home_team", "possession", "remaining_time", "self_hp", "enemy_hp", "battle_player_self",
       "battle_player_enemy", "cheer_self", "cheer_enemy", "team_level_self", "team_level_enemy",
       "team_icon_self", "team_icon_enemy", "team_name_self", "team_name_enemy", "skill_cd"}
DALGA = {"team", "cheer", "skill", "strength"}
OYUNCU = {"id", "enemy_id", "level", "break_level", "color", "pos", "skill_list", "attr"}
ATTR = {"fight", "morale", "attackMorale", "defendMorale", "shot", "dribble", "rebound", "block", "defend",
        "noBallAbility", "crossOver", "entranceEnergy", "energyRecoverSpeed", "crit", "moraleRecover",
        "powerRecover", "skillDamage", "fightCourage", "versatile", "critValue", "endurance", "toughness",
        "passivation", "mastery"}
AMIGO = {"id", "level", "gears"}


def null_yok(nesne):
    if nesne is None:
        return False
    if isinstance(nesne, dict):
        return all(null_yok(v) for v in nesne.values())
    if isinstance(nesne, list):
        return all(null_yok(v) for v in nesne)
    return True


class MacTesti(unittest.TestCase):
    def setUp(self):
        random.seed(1)
        self.gecici = tempfile.TemporaryDirectory()
        self.durum = Durum(os.path.join(self.gecici.name, "kayit.json"))
        self.durum.hesap_ac("test")
        self.yon = Yonlendirici()
        mac.kur(self.yon, self.durum)

    def tearDown(self):
        self.gecici.cleanup()

    def cagir(self, proto, sub, param):
        f = self.yon.protolar[(proto, sub)]
        cevap = f(alanlar={}, param=param, oturum="t", istek=None)
        self.assertEqual(cevap["result"], 0, cevap)
        self.assertTrue(null_yok(cevap), "JSON null var")
        json.loads(json_yaz(cevap))
        return cevap["data"]

    def battlemsg_dogrula(self, msg, dalga_sayisi=None):
        self.assertEqual(set(msg), UST)
        for taraf in ("battle_player_self", "battle_player_enemy"):
            for d in msg[taraf]:
                self.assertEqual(set(d), DALGA)
                self.assertEqual(len(d["team"]), 3)
                for a in d["cheer"]:
                    self.assertEqual(set(a), AMIGO)
                for p in d["team"]:
                    self.assertEqual(set(p), OYUNCU)
                    self.assertEqual(set(p["attr"]), ATTR)
                    self.assertTrue(all(isinstance(v, int) for v in p["attr"].values()))
                    self.assertGreater(p["attr"]["fight"], 8)  # player_formula.goalReduceMorale log() için
                    for s in p["skill_list"]:
                        self.assertEqual(set(s), {"skill_id", "skill_level"})
        self.assertEqual(len(msg["battle_player_self"]), 1)
        if dalga_sayisi:
            self.assertEqual(len(msg["battle_player_enemy"]), dalga_sayisi)

    def test_elite_akisi(self):
        data = self.cagir(16, 1602, {"stage": 0, "battle": 16000101, "star": 0})
        self.assertEqual(data["elite"]["cur_battle"], 16000101)
        msg = self.cagir(7, 705, {"paramlist": [16000101]})["battlemsg"]
        self.battlemsg_dogrula(msg, 1)
        self.assertEqual(msg["battle_type"], 6)
        biz = msg["battle_player_self"][0]
        rakip = msg["battle_player_enemy"][0]
        print("\nbiz:", [(p["id"], p["attr"]["fight"], p["attr"]["morale"]) for p in biz["team"]], biz["cheer"],
              "\nrakip:", [(p["id"], p["attr"]["fight"], p["attr"]["morale"]) for p in rakip["team"]])
        self.assertEqual(self.cagir(7, 711, {"paramlist": [50]})["code"], 0)
        once = self.durum.veri["gold"] = 1000
        sonuc = self.cagir(7, 702, {"paramlist": [1, 2, 1, 1, 1, 100, 100, 0]})
        bm = sonuc["battlemsg"]
        for ad in ("exp", "gold", "gem", "star", "exp_team", "item_list", "player_exp_old", "player_exp_new"):
            self.assertIn(ad, bm)
        self.assertEqual(len(bm["player_exp_old"]), 3)
        self.assertEqual(bm["player_exp_old"], bm["player_exp_new"])  # oyuncular azami seviyede
        self.assertEqual(self.durum.veri["elite"]["16000101"], 2)
        self.assertEqual(self.durum.veri["gold"], once + bm["gold"])
        self.assertEqual(sonuc["updatelist"]["paramlist"].get("gold"), bm["gold"])
        liste = self.cagir(16, 1601, {})["elite"]["stage_list"]
        self.assertEqual(liste[0]["battle_list"][0]["star"], 2)

    def test_hikaye_akisi(self):
        bilgi = self.cagir(2, 1, {})["story"]
        sid = bilgi["stage_list"][0]["id"]
        bid = mac.MV["hikaye"][sid][2]
        self.cagir(2, 2, {"stage": sid, "battle": bid})
        msg = self.cagir(7, 705, {"paramlist": [bid]})["battlemsg"]
        self.battlemsg_dogrula(msg, len(mac.MV["mac"][bid][3]))
        self.assertEqual(msg["battle_type"], 2)
        bm = self.cagir(7, 702, {"paramlist": [1, 3, 1, 1, 1, 100, 100, 0]})["battlemsg"]
        self.assertGreater(bm["gold"], 0)
        self.assertIn("story", self.cagir(2, 3, {"result": 1}))

    def test_battle_begin_ve_kayip(self):
        msg = self.cagir(7, 701, {"paramlist": [7, 123456, 0, 0]})["battlemsg"]
        self.battlemsg_dogrula(msg)
        bm = self.cagir(7, 702, {"paramlist": [0, 0, 0, 1, 1, 100, 100, 0]})["battlemsg"]
        self.assertEqual(bm["gold"], 0)

    def test_elite_sandik_ve_supurme(self):
        bid = next(iter(mac.MV["elite_mac_sandik"]))
        data = self.cagir(16, 1606, {"stage": 0, "battle": bid})
        mac_ = [b for s in data["elite"]["stage_list"] for b in s["battle_list"] if b["battle_id"] == bid][0]
        self.assertEqual(mac_["battle_status"], 2)
        data = self.cagir(16, 1607, {"stage": 0, "star": 5})
        self.assertEqual(data["elite"]["stage_list"][0]["chests_list"][0]["status"], 1)
        data = self.cagir(16, 1605, {"stage": 0, "battle": 16000101, "count": 5})
        self.assertEqual(len(data["resultlist"]), 5)
        self.assertIn("player_exp_new", data["elite"]["battle_result"])
        for sub in (1608, 1609, 1610):
            self.assertIn("elite", self.cagir(16, sub, {"stage": 0, "battle": 16000101}))

    def test_tum_maclar_kurulur(self):
        k = self.durum.veri
        for bid, m in mac.MV["mac"].items():
            if m[0] in (2, 6):
                msg = mac.battlemsg(k, bid, m[0], m[1], m[3], m[2], m[4])
                self.battlemsg_dogrula(msg, len(m[3]))

    def test_formul_ornek(self):
        # 1050, seviye 1, yıldız 1, renk 0, antrenman 0: yalnızca PlayerStarUpValue[1050][1]
        o = {"level": 1, "break_level": 1, "color": 0, "train": 0}
        self.assertEqual(mac.nitelik_hesapla(1050, o), mac.MV["oyuncu"][1050]["y"][0])
        self.assertEqual(mac.guc_hesapla([35, 10, 1, 1, 20, 1, 1, 1, 25, 20]), 23)  # tutorial rakibi 1051


if __name__ == "__main__":
    unittest.main()
