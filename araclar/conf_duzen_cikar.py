"""conf_qte.assetbundle tablolarının alan düzenini (ad, tür) çözülmüş C# sınıflarından çıkarır ve
araclar/conf_duzenleri.json dosyasına yazar. conf_yamala.py bu dosyayla tablolardaki metinleri çevirir.

Geliştirici aracı: çözülmüş C# kaynak klasörü (ILSpy/dnSpy çıktısı, her sınıf ayrı .cs) ve main.obb gerekir.
    python araclar/conf_duzen_cikar.py <cs_klasoru> <main.obb>

Türler: i=int32 (enum dahil), b=bool (1 bayt + 4'e hizalama, JSON'da 0/1), f=float, d=double, s=metin,
ai/as/af/ad=diziler. Her düzen paketteki ham veriye karşı doğrulanır; uymayan tablo yazılmaz.
"""
import json
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import conf_yamala as cy  # noqa: E402

TIP = {"int": "i", "uint": "i", "bool": "b", "float": "f", "double": "d", "string": "s",
       "int[]": "ai", "string[]": "as", "float[]": "af", "double[]": "ad"}


def sinif_duzeni(kod):
    enums = set(re.findall(r"public enum (\w+)", kod))
    alanlar = []
    for m in re.finditer(r"^\tpublic ([\w\[\]<>\.]+) (\w+);", kod, re.M):
        tip, isim = m.group(1), m.group(2)
        if tip in enums:
            tur = "i"
        elif tip.endswith("[]") and tip[:-2] in enums:
            tur = "ai"
        elif tip in TIP:
            tur = TIP[tip]
        else:
            return None, "desteklenmeyen tür %s %s" % (tip, isim)
        alanlar.append([isim, tur])
    return alanlar, None


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    cs_klasoru, obb = argv[1], argv[2]
    ikizler = cy.json_ikizleri(obb)
    ust, _, sf = cy.paketi_ac(cy.obb_paketi(obb))
    veri_basi = struct.unpack_from(">I", sf, 12)[0]
    _, girisler = cy.nesne_tablosu(sf)
    sonuc, sorun = {}, []
    for path_id, bas, boy, tip, sinif, silik in girisler:
        if sinif != 114:
            continue
        raw = sf[veri_basi + bas: veri_basi + bas + boy]
        ad, _ = cy.mono_adi(raw)
        yol = os.path.join(cs_klasoru, ad + ".cs")
        if not os.path.exists(yol):
            sorun.append((ad, "cs dosyası yok"))
            continue
        with open(yol, encoding="utf-8", errors="replace") as f:
            alanlar, hata = sinif_duzeni(f.read())
        if hata:
            sorun.append((ad, hata))
            continue
        kayitlar = ikizler.get(ad, [])
        if kayitlar and [a for a, _ in alanlar] != list(kayitlar[0].keys()):
            sorun.append((ad, "alan sırası JSON ile uyuşmuyor"))
            continue
        hata = cy.duzen_dogrula(raw, kayitlar, alanlar)
        if hata:
            sorun.append((ad, hata))
            continue
        sonuc[ad] = alanlar
    cikti = cy.DUZEN_DOSYASI
    with open(cikti, "w", encoding="utf-8") as f:
        json.dump(sonuc, f, ensure_ascii=False, indent=0)
    print("yazildi: %s (%d tablo)" % (cikti, len(sonuc)))
    for ad, h in sorun:
        print("atlandi:", ad, "-", h)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
