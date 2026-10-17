"""araclar/conf_yamala.py: veri tablosu paketi yaması (sentetik veriyle, OBB gerekmez)."""
import os
import struct
import sys
import unittest

KOK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(KOK, "araclar"))

import conf_yamala as cy  # noqa: E402


def mono_basligi(ad):
    """MonoBehaviour ham başlığı: m_GameObject(8) m_Enabled(4) m_Script(8) m_Name"""
    return b"\0" * 20 + cy._metin(ad)


def holder(ad, kayitlar, bayt_fn):
    return mono_basligi(ad) + cy._i32(len(kayitlar)) + b"".join(bayt_fn(r) for r in kayitlar)


def sahte_sf(nesneler):
    """Biçim 9 SerializedFile: başlık(16) + doldurma + nesne tablosu + sıfırlar + veri (8 hizalı)."""
    veri, girisler = bytearray(), []
    for k, (sinif, raw) in enumerate(nesneler):
        veri += b"\0" * ((-len(veri)) % 8)
        girisler.append((k + 1, len(veri), len(raw), sinif, sinif, 0))
        veri += raw
    tablo = cy._i32(len(girisler)) + b"".join(struct.pack("<iIIihh", *g) for g in girisler)
    ust = bytearray(b"\0" * 16 + b"\xAB" * 30 + tablo)  # 30 bayt sahte tip bilgisi
    veri_basi = (len(ust) + 63) & ~63
    ust += b"\0" * (veri_basi - len(ust))
    struct.pack_into(">IIII", ust, 0, len(tablo) + 30, veri_basi + len(veri), 9, veri_basi)
    return bytes(ust) + bytes(veri)


class ConfYamaTesti(unittest.TestCase):
    def test_buff_kayit_gidis_donus(self):
        ornek = [cy._buff(1000, "天生扣将", "açıklama", tur=1, yigin=2, iyi=1, tip=3, soz="x"),
                 cy._buff(1001, "强心剂", "", iyi=0)]
        raw = holder("BuffInformation", ornek, cy.buff_bilgi_bayt)
        okunan = cy.buff_bilgi_oku(raw)
        self.assertEqual(okunan, ornek)
        etkiler = [cy._etki(1000, 127, 0, 1.1), cy._etki(1001, 126, 20)]
        self.assertEqual(cy.buff_etki_oku(holder("BuffEffect", etkiler, cy.buff_etki_bayt)), etkiler)

    def test_tablo_ekle(self):
        raw = holder("BuffInformation", [cy._buff(1000, "a", "b")], cy.buff_bilgi_bayt)
        yeni = cy.tablo_ekle(raw, cy.EK_BUFFLAR, cy.buff_bilgi_bayt)
        idler = [r["buffId"] for r in cy.buff_bilgi_oku(yeni)]
        self.assertEqual(idler, [1000] + [r["buffId"] for r in cy.EK_BUFFLAR])

    def test_eksik_bufflar_tam(self):
        beklenen = set(range(1147, 1177)) | {2036, 2097, 2098, 2099, 2100, 3006, cy.EFSANE_BUFF, cy.EFSANE_YUKSELIS, cy.EFSANE_YUKSELIS_AOMINE}
        self.assertEqual({r["buffId"] for r in cy.EK_BUFFLAR}, beklenen)
        self.assertTrue({r["buffId"] for r in cy.EK_BUFF_ETKILERI} <= beklenen)
        for r in cy.EK_BUFFLAR:  # C# specialEffectOne.Length > 1 ise efekt arar: boş yerine "0"
            self.assertTrue(len(r["specialEffectOne"]) == 1 or r["specialEffectOne"].startswith("role_"))

    def test_sf_yamala(self):
        bilgi = holder("BuffInformation", [cy._buff(1000, "a", "b")], cy.buff_bilgi_bayt)
        etki = holder("BuffEffect", [cy._etki(1000, 127, 0, 1.1)], cy.buff_etki_bayt)
        sf = sahte_sf([(114, bilgi), (28, b"\x01\x02\x03"), (114, etki), (114, holder("Diger", [], cy.buff_bilgi_bayt))])
        self.assertEqual(cy.sf_yamala(sf, {}), sf)  # değişiklik yoksa bayt bayt aynı
        yeni = cy.sf_yamala(sf, {"BuffInformation": lambda r: cy.tablo_ekle(r, cy.EK_BUFFLAR, cy.buff_bilgi_bayt),
                                 "BuffEffect": lambda r: cy.tablo_ekle(r, cy.EK_BUFF_ETKILERI, cy.buff_etki_bayt)})
        self.assertEqual(struct.unpack_from(">I", yeni, 4)[0], len(yeni))
        veri_basi = struct.unpack_from(">I", yeni, 12)[0]
        _, girisler = cy.nesne_tablosu(yeni)
        self.assertEqual(len(girisler), 4)
        sinif28 = [g for g in girisler if g[4] == 28][0]
        self.assertEqual(yeni[veri_basi + sinif28[1]: veri_basi + sinif28[1] + 3], b"\x01\x02\x03")
        g0 = girisler[0]
        okunan = cy.buff_bilgi_oku(yeni[veri_basi + g0[1]: veri_basi + g0[1] + g0[2]])
        self.assertEqual(len(okunan), 1 + len(cy.EK_BUFFLAR))
        with self.assertRaises(ValueError):
            cy.sf_yamala(sf, {"YokBoyleTablo": lambda r: r})

    def test_paket_gidis_donus(self):
        ust = {"surum": 3, "oyuncu": "3.x.x", "motor": "4.6.9f1", "seviye_indir": 1, "seviye_sayisi": 1,
               "veri_basligi": 52}
        sf = sahte_sf([(114, holder("BuffInformation", [], cy.buff_bilgi_bayt))])
        paket = cy.paketi_kapat(ust, "CAB-17c962b447b106e4794206f2433ce792", sf)
        self.assertTrue(paket.startswith(b"UnityWeb\0"))
        ust2, ad2, sf2 = cy.paketi_ac(paket)
        self.assertEqual((ust2, ad2, sf2), (ust, "CAB-17c962b447b106e4794206f2433ce792", sf))
        # başlıktaki toplam boy ve lzma'daki açık boyut özgün paket gibi yazılmış olmalı
        self.assertEqual(struct.unpack_from(">I", paket, 9 + 4 + 6 + 8)[0], len(paket))
        self.assertEqual(struct.unpack_from("<q", paket, 60 + 5)[0], 52 + len(sf))

    def test_lua_eki(self):
        ek = cy.buff_lua_eki()
        self.assertIn("YEREL_EK_BuffInformation", ek)
        self.assertIn("function BuffInformationReader.OnJsonCall(data)", ek)
        self.assertEqual(ek.count("buffId="), len(cy.EK_BUFFLAR))
        self.assertEqual(ek.count("skillId="), len(cy.EK_BECERILER))
        self.assertIn("function SkillInfoReader.OnJsonCall(data)", ek)
        self.assertIn('buffName="İmparatorun Heybeti"', ek)

    def test_uretilen_paket_varsa_dogru(self):
        yol = os.path.join(KOK, "sunucu", "veri", "conf_qte.assetbundle")
        if not os.path.exists(yol):
            self.skipTest("yamalı paket üretilmemiş")
        with open(yol, "rb") as f:
            s = cy.dogrula(f.read())
        idler = {r["buffId"] for r in s["buff"]}
        self.assertTrue({r["buffId"] for r in cy.EK_BUFFLAR} <= idler)
        self.assertGreater(len(s["etki"]), len(cy.EK_BUFF_ETKILERI))
        self.assertIn(cy.EFSANE_BECERI, s["beceri"])

    def test_beceri_kaydi_duzenle_uyumlu(self):
        alanlar = cy.duzenleri_yukle()["SkillInfo"]
        for r in cy.EK_BECERILER:
            self.assertEqual(list(r.keys()), [a for a, _ in alanlar])
            raw = mono_basligi("SkillInfo") + cy._i32(1) + cy.kayit_bayt(r, alanlar)
            self.assertIsNone(cy.duzen_dogrula(raw, [r], alanlar))

    def test_duzen_dogrula_ve_cevir(self):
        alanlar = [["kimlik", "i"], ["ad", "s"], ["oran", "d"], ["kucuk", "f"], ["acik", "b"], ["liste", "ai"],
                   ["adlar", "as"]]
        kayitlar = [{"kimlik": 1, "ad": "天生扣将", "oran": 7.2, "kucuk": 1.5, "acik": 10, "liste": [1, 2],
                     "adlar": ["攻击力上升", "x"]},
                    {"kimlik": 2, "ad": "yok", "oran": 0, "kucuk": 0, "acik": 0, "liste": [], "adlar": []}]
        govde = b""
        for r in kayitlar:
            govde += (struct.pack("<i", r["kimlik"]) + cy._metin(r["ad"]) + struct.pack("<d", float(r["oran"]))
                      + struct.pack("<f", float(r["kucuk"])) + struct.pack("<i", 1 if r["acik"] else 0)
                      + cy._i32(len(r["liste"])) + b"".join(cy._i32(x) for x in r["liste"])
                      + cy._i32(len(r["adlar"])) + b"".join(cy._metin(x) for x in r["adlar"]))
        raw = mono_basligi("Deneme") + cy._i32(len(kayitlar)) + govde
        self.assertIsNone(cy.duzen_dogrula(raw, kayitlar, alanlar))  # bool 10 -> 1 kabul edilir
        self.assertIsNotNone(cy.duzen_dogrula(raw, kayitlar, alanlar[:-1]))
        self.assertIsNotNone(cy.duzen_dogrula(raw + b"\0", kayitlar, alanlar))
        sozluk = {"天生扣将": "Doğuştan Smaççı", "攻击力上升": "Saldırı arttı"}
        yeni, sayac = cy.tablo_cevir(raw, kayitlar, sozluk, alanlar)
        self.assertEqual(sayac, 2)
        okunan = []
        o = cy.mono_adi(yeni)[1] + 4
        for _ in kayitlar:
            r, o = cy._kayit_oku(yeni, o, [a for a, _ in alanlar], [t for _, t in alanlar])
            okunan.append(r)
        self.assertEqual(o, len(yeni))
        self.assertEqual(okunan[0]["ad"], "Doğuştan Smaççı")
        self.assertEqual(okunan[0]["adlar"], ["Saldırı arttı", "x"])
        self.assertEqual(okunan[0]["acik"], 1)
        self.assertAlmostEqual(okunan[0]["oran"], 7.2)
        # bilinen düzen yoksa JSON'dan çıkarım da aynı sonucu vermeli
        yeni2, sayac2 = cy.tablo_cevir(raw, kayitlar, sozluk)
        self.assertEqual((yeni2, sayac2), (yeni, sayac))

    def test_duzen_dosyasi(self):
        duzenler = cy.duzenleri_yukle()
        self.assertIn("BuffInformation", duzenler)
        self.assertEqual([a for a, _ in duzenler["BuffInformation"]], list(cy._buff(1, "a", "b").keys()))
        self.assertIn("LoadingTipsInfo", duzenler)


if __name__ == "__main__":
    unittest.main()
