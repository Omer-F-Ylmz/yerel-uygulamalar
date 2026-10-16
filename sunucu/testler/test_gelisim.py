"""gelisim.py işleyicileri: python -m unittest discover -s sunucu/testler"""
import json
import os
import random
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cekirdek import Yonlendirici, json_yaz, param_coz  # noqa: E402
from durum import Durum, SINIR  # noqa: E402
import gelisim  # noqa: E402

GV = gelisim.GV


def null_yok(nesne):
    if nesne is None:
        return False
    if isinstance(nesne, dict):
        return all(null_yok(v) for v in nesne.values())
    if isinstance(nesne, list):
        return all(null_yok(v) for v in nesne)
    return True


class GelisimTesti(unittest.TestCase):
    def setUp(self):
        random.seed(1)
        self.gecici = tempfile.TemporaryDirectory()
        self.durum = Durum(os.path.join(self.gecici.name, "kayit.json"))
        self.k = self.durum.hesap_ac("test")
        self.yon = Yonlendirici()
        # sunucu.py'nin önceki kayıtları (get/rename) devralınmalı
        self.onceki_cagri = []
        self.yon.yollar["/ball_team"] = lambda **a: self.onceki_cagri.append(a) or {"result": 0, "data": {"x": 1}}
        gelisim.kur(self.yon, self.durum)
        self.pid = int(next(iter(self.k["oyuncular"])))

    def tearDown(self):
        self.gecici.cleanup()

    # ------------------------------------------------ yardımcılar
    def dogrula(self, cevap):
        self.assertEqual(cevap["result"], 0, cevap)
        self.assertTrue(null_yok(cevap), "JSON null var")
        json.loads(json_yaz(cevap))
        return cevap["data"]

    def yol(self, yol, **alanlar):
        alanlar = {k: (v if isinstance(v, str) else json.dumps(v)) for k, v in alanlar.items()}
        f = self.yon.yollar[yol]
        return self.dogrula(f(alanlar=alanlar, param=param_coz(alanlar.get("param", "")), oturum=None, istek=None))

    def op(self, yol, op, *liste):
        return self.yol(yol, op=op, param={"paramlist": list(liste)})

    def oyuncu_cevapta(self, data, pid):
        return next(p for p in data["team"]["player_lists"] if p["id"] == pid)

    def takim_cevabi_mi(self, data):
        self.assertIn("player_lists", data["team"])
        self.assertIn("select", data["team"])
        self.assertIn("backpack", data)
        self.assertEqual(data["updatelist"]["op_flag"], 1)
        self.assertIsInstance(data["updatelist"]["paramlist"], dict)

    def yeni_oyuncu(self, **degerler):
        o = self.k["oyuncular"][str(self.pid)]
        o.update(degerler)
        return o

    # ------------------------------------------------ oyuncu
    def test_ise_alma(self):
        del self.k["oyuncular"][str(self.pid)]
        parca, adet = GV["parca"][self.pid]
        self.k["canta"][str(parca)] = adet + 5
        data = self.yol("/player_compound", player_id=str(self.pid))
        self.takim_cevabi_mi(data)
        self.assertIn(str(self.pid), self.k["oyuncular"])
        self.assertEqual(self.k["canta"][str(parca)], 5)
        self.assertEqual(data["updatelist"]["paramlist"]["item_list"], [{"id": parca, "count": -adet}])
        self.oyuncu_cevapta(data, self.pid)

    def test_ise_alma_bilinmeyen_oyuncu_hata(self):
        f = self.yon.yollar["/player_compound"]
        self.assertEqual(f(alanlar={"player_id": "1"}, param={})["result"], -1)

    def test_yildiz_ve_kirilma_bedelsiz_de_calisir(self):
        self.yeni_oyuncu(break_level=3)
        self.k["gold"] = 0
        parca = GV["parca"][self.pid][0]
        self.k["canta"][str(parca)] = 0
        data = self.op("/player_star", "star_up", self.pid, 6)
        self.takim_cevabi_mi(data)
        self.assertEqual(self.oyuncu_cevapta(data, self.pid)["break_level"], 6)
        self.assertEqual(self.k["gold"], 0)
        data = self.yol("/player_break", player_id=str(self.pid))
        self.assertEqual(self.oyuncu_cevapta(data, self.pid)["break_level"], 7)
        self.op("/player_star", "star_up", self.pid, 999)
        self.assertEqual(self.k["oyuncular"][str(self.pid)]["break_level"], SINIR["yildiz"])

    def test_yildiz_bedeli_dusulur(self):
        self.yeni_oyuncu(break_level=1)
        altin = GV["yildiz"][self.pid][1][0]
        eski = self.k["gold"]
        data = self.op("/player_star", "star_up", self.pid, 2)
        self.assertEqual(self.k["gold"], eski - altin)
        self.assertEqual(data["updatelist"]["paramlist"]["gold"], -altin)

    def test_parca_degisimi(self):
        self.k["canta"]["26000"] = 10
        parca = GV["parca"][self.pid][0]
        self.k["canta"][str(parca)] = 0
        self.op("/player_star", "exchange", self.pid, 4)
        self.assertEqual(self.k["canta"]["26000"], 6)
        self.assertEqual(self.k["canta"][str(parca)], 4)

    def test_ilerleme_ve_giysi(self):
        self.yeni_oyuncu(color=5)
        data = self.yol("/player_dress_equip", player_id=str(self.pid), index="2")
        j = self.oyuncu_cevapta(data, self.pid)
        self.assertEqual(j["s_equipment_list"][0]["index"], 2)
        self.assertEqual(j["s_equipment_list"][0]["id"], gelisim.giysi_idleri(self.pid, 5)[2])
        data = self.yol("/player_advance", player_id=str(self.pid))
        j = self.oyuncu_cevapta(data, self.pid)
        self.assertEqual(j["color"], 6)
        self.assertEqual(j["s_equipment_list"], [])
        self.yeni_oyuncu(color=SINIR["renk"])
        data = self.yol("/player_advance", player_id=str(self.pid))
        self.assertEqual(self.oyuncu_cevapta(data, self.pid)["color"], SINIR["renk"])

    def test_antrenman(self):
        self.yeni_oyuncu(train=40)
        data = self.yol("/player_train_up", player_id=str(self.pid), train_type="2", isgrowup="0")
        j = self.oyuncu_cevapta(data, self.pid)
        self.assertEqual([t["level"] for t in j["train"]], [40, 40, 40, 40, 40])  # büyüme 1 -> tavan 40
        data = self.yol("/player_train_up", player_id=str(self.pid), train_type="0", isgrowup="1")
        self.assertEqual(self.oyuncu_cevapta(data, self.pid)["grow_up_cnts"], 2)
        data = self.yol("/player_train_up", player_id=str(self.pid), train_type="2", isgrowup="0")
        self.assertEqual([t["level"] for t in self.oyuncu_cevapta(data, self.pid)["train"]], [40, 41, 40, 40, 40])
        data = self.yol("/player_train_up", player_id=str(self.pid), train_type="0", isgrowup="0")
        self.assertEqual([t["level"] for t in self.oyuncu_cevapta(data, self.pid)["train"]], [41, 42, 41, 41, 41])
        self.assertEqual(self.k["oyuncular"][str(self.pid)]["train"], 41)

    def test_top_stili(self):
        pid = next(p for p in GV["stil"] if str(p) in self.k["oyuncular"])
        self.pid = pid
        stiller = gelisim.acik_stiller(pid, self.k["oyuncular"][str(pid)])
        self.assertTrue(stiller)
        sid = stiller[0]
        self.k["oyuncular"][str(pid)]["beceri_ozel"] = {str(sid): 5}
        data = self.op("/player_style", "up_lv", pid, sid)
        self.takim_cevabi_mi(data)
        self.assertEqual(data["styles"]["styles_points"], gelisim.STIL_PUANI)
        beceriler = {s["skill_id"]: s["skill_level"] for s in self.oyuncu_cevapta(data, pid)["s_skill_list"]}
        self.assertEqual(beceriler[sid], 6)
        data = self.op("/player_style", "buy_points")
        self.assertEqual(data["today_buy_num"], 0)

    def test_stil_becerileri_acik_gorunur(self):
        pid = next(p for p in GV["stil"] if str(p) in self.k["oyuncular"])
        data = self.op("/player_talent", "sync_talent")
        idler = {s["skill_id"] for s in self.oyuncu_cevapta(data, pid)["s_skill_list"]}
        self.assertTrue(set(GV["stil"][pid]) <= idler)

    def test_beceri_seviyesi(self):
        sid = self.k and gelisim.OYUNCU_VERI[self.pid]["beceriler"][0]
        self.yeni_oyuncu(beceri=3)
        data = self.yol("/player_skill_uplevel", player_id=str(self.pid), skill_id=str(sid))
        beceriler = {s["skill_id"]: s["skill_level"] for s in self.oyuncu_cevapta(data, self.pid)["s_skill_list"]}
        self.assertEqual(beceriler[sid], 4)

    def test_sihir_yuvasi_yoksa_dokunmaz_varsa_islenir(self):
        data = self.op("/player_magic", "magic_break", self.pid, 13110321, 1)
        self.takim_cevabi_mi(data)
        self.assertNotIn("magics", self.oyuncu_cevapta(data, self.pid))
        o = self.k["oyuncular"][str(self.pid)]
        o["magics"] = [{"magic_index": 1, "magic_id": 13110321, "level": 2, "exp": 0, "type": 1, "status": 0,
                        "unlock": 1, "skill_list": []},
                       {"magic_index": 3, "magic_id": 13350011, "level": 1, "exp": 0, "type": 3, "status": 1,
                        "unlock": 1, "skill_list": [{"skill_id": 10001, "skill_level": 1}]}]
        data = self.op("/player_magic", "magic_break", self.pid, 13110321, 1)
        self.assertEqual(self.oyuncu_cevapta(data, self.pid)["magics"][0]["level"], 3)
        self.op("/player_magic", "magic_activate", self.pid, 13110321, 1)
        self.assertEqual(o["magics"][0]["status"], 1)
        data = self.op("/player_magic", "magic_generic_random", self.pid, 13110321, 1)
        self.assertEqual(GV["sihir_tur"][data["magicId"]], 2)
        data = self.op("/player_magic", "magic_tx_random", self.pid, 13350011, 3, 1, 10001)
        self.assertIn(data["skillId"], GV["ozellik_havuzu"][3])
        self.op("/player_magic", "magic_tx_replace", self.pid, 3, 1, 10002)
        self.assertEqual(o["magics"][1]["skill_list"][0]["skill_id"], 10002)
        self.op("/player_magic", "magic_tx_dingxiang", self.pid, 13350011, 3, 1, 10002, 10003)
        self.assertEqual(o["magics"][1]["skill_list"][0]["skill_id"], 10003)
        yeni = next(m for m, t in GV["sihir_tur"].items() if t == 2)
        self.op("/player_magic", "magic_generic_replace", self.pid, 13110321, 1, yeni)
        self.assertEqual(o["magics"][0]["magic_id"], yeni)
        self.op("/player_magic", "magic_sublimation", self.pid, 1, yeni, 40057)
        self.op("/player_jewel", "dress_jewel", self.pid, 1, 13110321)
        self.assertEqual(o["magics"][0]["magic_id"], 13110321)
        self.op("/player_jewel", "drop_jewel", self.pid, 1)

    # ------------------------------------------------ eşya ve ekipman
    def test_esya_birlestirme(self):
        eid = next(e for e in GV["esya_birlesim"] if e in gelisim.ESYA_VERI)
        for malzeme, adet in GV["esya_birlesim"][eid]:
            self.k["canta"][str(malzeme)] = adet
        cevap = self.yon.protolar[(1, 101)](param={"id": eid}, alanlar={}, oturum=None, istek=None)
        data = self.dogrula(cevap)
        self.assertIn("backpack", data)
        self.assertEqual(self.k["canta"][str(eid)], 1)
        for malzeme, _ in GV["esya_birlesim"][eid]:
            self.assertEqual(self.k["canta"][str(malzeme)], 0)

    def test_ekipman(self):
        o = self.yeni_oyuncu()
        o["ekipman"] = {str(n): {"lv": 5, "blv": 0, "wlv": 0} for n in range(1, 7)}
        data = self.op("/player_equip", "strength", self.pid, 1, 3)  # tek seviye
        self.assertEqual(set(data), {"equip", "updatelist"})
        self.assertEqual(len(data["equip"]), 6)
        self.assertEqual(data["equip"][0]["lv"], 6)
        data = self.op("/player_equip", "strength", self.pid, 1, 1)  # gidebildiği yere kadar
        tavan = gelisim.guc_tavani(0, self.k["takim"]["seviye"])
        self.assertEqual(data["equip"][0]["lv"], tavan)
        data = self.op("/player_equip", "strength", self.pid, 1, 2)  # gruptaki üç yuva
        self.assertEqual([e["lv"] for e in data["equip"]], [tavan] * 3 + [5] * 3)
        data = self.op("/player_equip", "break", self.pid, 2, 2)  # ilk üç yuva
        self.assertEqual([e["blv"] for e in data["equip"]], [1, 1, 1, 0, 0, 0])
        data = self.op("/player_equip", "break", self.pid, 5, 1)
        self.assertEqual(data["equip"][4]["blv"], 1)
        data = self.op("/player_equip", "wake", self.pid, 1)
        self.assertEqual(data["equip"][0]["wlv"], 1)
        data = self.op("/player_equip", "recycle", self.pid, 1)
        self.assertEqual(data["equip"][0]["wlv"], 0)
        # takım cevapları da kayıttaki ekipmanı göstermeli
        team = self.op("/player_talent", "sync_talent")["team"]
        self.assertEqual(self.oyuncu_cevapta({"team": team}, self.pid)["equip"][1]["blv"], 1)

    def test_ekipman_tavanlari(self):
        data = self.op("/player_equip", "break", self.pid, 1, 1)
        self.assertEqual(data["equip"][0]["blv"], GV["ekipman_sinir"]["kirilma"])
        data = self.op("/player_equip", "wake", self.pid, 1)
        self.assertEqual(data["equip"][0]["wlv"], GV["ekipman_sinir"]["uyanis"])

    # ------------------------------------------------ amigolar
    def test_amigo_bilgisi_ve_secim(self):
        data = self.op("/cheer_leader", "get_cheer_info")
        self.assertEqual(len(data["cheer_leader"]["select_cheers"]), 3)
        ids = {c["id"] for c in data["cheer_leader"]["cheers"]}
        self.assertEqual(ids, {int(a) for a in self.k["amigolar"]})
        tur3 = next(a for a, t in GV["amigo_tur"].items() if t == 3)
        data = self.op("/cheer_leader", "change_cheer", tur3)
        self.assertEqual(data["cheer_leader"]["select_cheers"][2]["id"], tur3)
        self.assertIn("old", data["fight"])
        data = self.op("/cheer_leader", "change_cheer", 2001, 0, tur3)
        self.assertEqual([s["id"] for s in data["cheer_leader"]["select_cheers"]], [2001, 0, tur3])
        self.assertEqual(self.k["secili_amigolar"], [2001, tur3])

    def test_amigo_birlestir_seviye_kademe(self):
        del self.k["amigolar"]["2000"]
        data = self.op("/cheer_leader", "compound_cheer", 2000)
        amigo = next(c for c in data["cheer_leader"]["cheers"] if c["id"] == 2000)
        self.assertEqual((amigo["level"], amigo["index"]), (1, 1))
        self.k["canta"]["40066"] = 10
        data = self.op("/cheer_leader", "levelup_cheer", 2000, 40066, 10)
        amigo = next(c for c in data["cheer_leader"]["cheers"] if c["id"] == 2000)
        self.assertEqual(amigo["level"], 10)  # 1. kademe tavanı
        self.assertEqual(self.k["canta"]["40066"], 0)
        data = self.op("/cheer_leader", "active_cheer", 2000)
        amigo = next(c for c in data["cheer_leader"]["cheers"] if c["id"] == 2000)
        self.assertEqual(amigo["index"], 2)
        self.k["amigolar"]["2000"] = 50
        self.k["amigo_kademe"]["2000"] = 6
        data = self.op("/cheer_leader", "active_cheer", 2000)
        self.assertEqual(next(c for c in data["cheer_leader"]["cheers"] if c["id"] == 2000)["index"], 6)

    # ------------------------------------------------ takım
    def test_takim_ikonu_odul_ve_devralma(self):
        data = self.op("/ball_team", "reicon", 17)
        self.assertEqual(data["ballteam"]["icon"], 17)
        self.assertEqual(self.k["takim"]["ikon"], 17)
        eski = self.k["gold"] = 100
        data = self.op("/ball_team", "get_prize", 1)
        self.assertEqual(self.k["gold"], eski + GV["takim_odul"][1][0])
        self.assertIn("ballteam", data)
        self.op("/ball_team", "rename")
        self.assertEqual(len(self.onceki_cagri), 1)

    def test_oyuncu_json_sarmalayici_tek_sefer(self):
        m = gelisim.sunucu_modulu()
        ilk = m.oyuncu_json
        gelisim.kur(Yonlendirici(), self.durum)
        self.assertIs(m.oyuncu_json, ilk)
        self.assertTrue(m.oyuncu_json._gelisim)


if __name__ == "__main__":
    unittest.main()
