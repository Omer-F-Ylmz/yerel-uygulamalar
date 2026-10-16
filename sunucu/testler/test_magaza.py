"""magaza.py işleyicilerinin duman testi: python -m unittest discover -s sunucu/testler"""
import json
import os
import random
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cekirdek import Yonlendirici, basarili, hata, json_yaz  # noqa: E402
from durum import Durum  # noqa: E402
import magaza  # noqa: E402

# StoreDataManager.InitData / CardStage.OnReceive'ın okuduğu alanlar
STORE = {"ce", "rl", "rl_y", "ts", "ts_p", "ts_c", "cp", "cp_t", "cc", "ts_m", "cm", "ts_s", "cs", "cs_fd",
         "ts_g", "cg_fd", "ctpl", "lk"}
DROPLIST = {"player_list", "item_list", "cheer_list", "magic_list", "gold", "gem", "star"}


def null_yok(nesne):
    if nesne is None:
        return False
    if isinstance(nesne, dict):
        return all(null_yok(v) for v in nesne.values())
    if isinstance(nesne, list):
        return all(null_yok(v) for v in nesne)
    return True


class MagazaTesti(unittest.TestCase):
    def setUp(self):
        random.seed(3)
        self.gecici = tempfile.TemporaryDirectory()
        self.durum = Durum(os.path.join(self.gecici.name, "kayit.json"))
        self.durum.hesap_ac("test")
        self.yon = Yonlendirici()
        # sunucu.py'nin kayıtlarının yerine geçen basit sahteler
        self.yon.protolar[(12, 1201)] = lambda **_: basarili({"team": {"player_lists": []}})
        self.yon.yollar["/gem_shop"] = lambda alanlar, **_: (basarili({"eski": 1}) if alanlar.get("op") == "get_card_info"
                                                             else hata("HintBallTeamError"))
        self.yon.yollar["/activity"] = lambda **_: basarili({"activity": {"status": []}})
        magaza.kur(self.yon, self.durum)

    def tearDown(self):
        self.gecici.cleanup()

    def dogrula(self, cevap):
        self.assertEqual(cevap["result"], 0, cevap)
        self.assertTrue(null_yok(cevap), "JSON null var")
        json.loads(json_yaz(cevap))
        return cevap["data"]

    def cagir(self, proto, sub, param=None):
        return self.dogrula(self.yon.protolar[(proto, sub)](alanlar={}, param=param or {}, oturum="t", istek=None))

    def yol(self, ad, op, param=None):
        return self.dogrula(self.yon.yollar[ad](alanlar={"op": op}, param=param or {}, oturum="t", istek=None))

    def test_store_bilgi(self):
        store = self.cagir(34, 3401)["store"]
        self.assertEqual(set(store), STORE)
        self.assertIsInstance(store["rl"], list)
        self.assertIsInstance(store["rl_y"], list)

    def test_vip(self):
        vip = self.cagir(35, 3501)["vip"]
        self.assertEqual(vip["lv"], 15)
        self.assertEqual(vip["gem"], 200000)       # data_vip[15].recharge_gem: çubuk dolu
        paket = self.cagir(35, 3502, {"vip": 15, "droplistid": 1030015})
        self.assertEqual(paket["vip"]["vip_package"], [{"vip": 15}])
        self.assertEqual(self.yon.protolar[(35, 3502)](param={"vip": 15})["result"], -1)  # ikinci kez alınmaz

    def test_oyuncu_cekilisi_ucretsiz_sonra_ucretli(self):
        gem0 = self.durum.veri["gem"]
        ilk = self.cagir(34, 3404)
        self.assertEqual(set(ilk["droplist"]), DROPLIST)
        self.assertEqual(self.durum.veri["gem"], gem0)             # ilk tekli ücretsiz
        self.assertGreater(ilk["store"]["ts_p"], 0)
        ikinci = self.cagir(34, 3404)
        self.assertEqual(ikinci["updatelist"]["paramlist"]["gem"], -magaza.AYAR["cost_one_player"])

    def test_onlu_cekilis_oyuncu_parcaya_doner(self):
        on = self.cagir(34, 3405)
        oyuncular = on["droplist"]["player_list"]
        self.assertGreaterEqual(len(oyuncular), 1)                 # 10'lu çekilişte en az bir garanti oyuncu
        o = oyuncular[0]
        parca, _ = magaza.MG["parca"][o["id"]]
        if o["chip"] > 0:                                          # oyuncu zaten var: parça verildi
            self.assertIn({"id": parca, "count": o["chip"]}, on["droplist"]["item_list"])
        self.assertEqual(on["updatelist"]["paramlist"]["gem"], -magaza.AYAR["cost_ten_player"] + on["droplist"]["gem"])
        self.assertEqual(on["store"]["cp"], 10)

    def test_yeni_oyuncu_takima_eklenir(self):
        k = self.durum.veri
        k["oyuncular"] = {p: o for p, o in k["oyuncular"].items() if p == "1007"}
        on = self.cagir(34, 3405)
        o = on["droplist"]["player_list"][0]
        self.assertEqual(o["chip"], 0)
        self.assertIn(str(o["id"]), k["oyuncular"])
        self.assertIn("team", on)

    def test_altin_ve_sureli_cekilis(self):
        tek = self.cagir(34, 3416)
        self.assertEqual(tek["store"]["cg_fd"], 1)
        on = self.cagir(34, 3417)
        self.assertEqual(on["updatelist"]["paramlist"]["gold"], -magaza.AYAR["cost_ten_gold"] + on["droplist"]["gold"])
        s = self.cagir(34, 3418)
        self.assertEqual(set(s["droplist"]), DROPLIST)
        combo = self.cagir(34, 3419)
        self.assertEqual(len(combo["dl"]), 6)
        lk = combo["store"]["lk"]
        self.assertGreater(lk, 0)
        self.assertEqual(self.cagir(34, 3401)["store"]["lk"], lk)  # bir kez bildirilir
        self.assertEqual(self.cagir(34, 3401)["store"]["lk"], 0)

    def test_diger_cekilisler(self):
        for sub in (3406, 3407, 3412, 3413, 3414, 3415):
            d = self.cagir(34, sub)
            self.assertEqual(set(d["droplist"]), DROPLIST)

    def test_banka(self):
        d = self.cagir(34, 3402, {"paramlist": [2]})
        self.assertEqual(len(d["exchangelist"]), 5)
        self.assertTrue(all(set(x) == {"g", "t"} for x in d["exchangelist"]))

    def test_kara_borsa(self):
        d = self.yol("/player_shop", "get_shop", {"paramlist": [2]})
        mallar = d["shop"]["goods_list"]
        self.assertEqual(len(mallar), 12)
        self.assertEqual(set(mallar[0]), {"item_id", "item_count", "count", "cost", "grid", "discount"})
        al = self.yol("/player_shop", "buy", {"paramlist": [2, mallar[0]["grid"]]})
        self.assertEqual(al["updatelist"]["paramlist"]["star"], -mallar[0]["cost"])
        self.assertEqual(al["shop"]["goods_list"][0]["item_count"], 0)
        self.yol("/player_shop", "manual_refresh", {"paramlist": [2]})

    def test_kisitli_takas_resimli(self):
        pl = self.cagir(51, 5101)["restriction"]["pl"]
        self.assertTrue(pl)
        self.cagir(51, 5102, {"paramlist": [pl[0]["i"]]})
        self.cagir(57, 5703, {"paramlist": [31001]})
        self.cagir(57, 5702, {"paramlist": [31001001, 1]})
        el = self.cagir(58, 5801)["el"]
        self.assertTrue(all(set(x) == {"i", "c", "b"} for x in el))
        self.cagir(58, 5803, {"paramlist": [12101010, 2]})

    def test_gem_shop_ve_etkinlik(self):
        self.assertEqual(self.yol("/gem_shop", "get_card_info")["eski"], 1)
        d = self.yol("/gem_shop", "get_free_gem")
        self.assertIn("gem", d["updatelist"]["paramlist"])
        durum = self.yol("/activity", "")["activity"]["status"]
        self.assertTrue(any(x["id"] == magaza.SURELI_YILDIZ_ETKINLIGI for x in durum))


if __name__ == "__main__":
    unittest.main()
