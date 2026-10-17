"""OBB'deki conf_qte.assetbundle paketini yamalar: beceri betiklerinin kullandığı ama tabloda
olmayan buff tanımları (BuffInformation + BuffEffect) eklenir.

Neden: OBB'deki veri tabloları Lua betiklerinden eski. Betikler 36 buff id'si (1147-1176, 2036,
2097-2100, 3006) kullanıyor; C# PlayerBuffManager.addBuff tabloda bulamayınca null döndürüyor ve beceri
betiği hata veriyor (maç başlamıyor ya da beceri etkisiz kalıyor).

Nasıl: Oyun açılışta sunucudan Conf/<dil>/conf_time.txt ister; içindeki md5 cihazdaki
files!/assets/Conf/<dil>/conf_qte.assetbundle ile uyuşmazsa /res/ANDROID/Conf/<dil>/conf_qte.assetbundle
indirip kaydeder (ConfManager.loadConfTime / loadConf). Sunucu bu dosyayı yamalı paketle karşılar; OBB
değişmez.

Paket biçimi (Unity 4.6.9f1): UnityWeb v3, LZMA (lzma_alone) ile sıkıştırılmış tek SerializedFile
(biçim 9, little-endian). Tablolar MonoBehaviour nesneleri (XxxHolder: m_Name + data listesi).
Tip ağaçları pakette eksik olduğu için UnityPy okuyamıyor; bu modül nesneleri ham bayt olarak işler.

Kullanım (geliştirici; oyuncunun makinesinde gerekmez):
    python araclar/conf_yamala.py <main.obb> [cikti=sunucu/veri/conf_qte.assetbundle]
"""
import hashlib
import io
import lzma
import os
import struct
import sys
import zipfile

PAKET_ADI = "assets/Android/conf_qte.assetbundle"
CEVIRI_JSON = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "sunucu", "veri", "ceviri_tr.json")
VARSAYILAN_CIKTI = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "sunucu", "veri", "conf_qte.assetbundle")

# Beceri işlev kimlikleri (BuffEffect.skillFunctionID), mevcut tablodaki kullanımdan:
#   126 = isabet + p1 puan, 127 = saldırı x p2, 136 = tüm nitelikler x p2, 335 = topu tutamaz.


EFSANE_BUFF = 90001


def _buff(bid, ad, aciklama, tur=0, sn=0, yigin=1, iyi=1, tip=0, soz="0", fx1="0", fx2="0"):
    return {"buffId": bid, "effectType": 0, "buffIconID": 0, "buffType": [tip], "specialEffectWord": soz,
            "specialEffectOne": fx1, "specialEffectTwo": fx2, "buffName": ad, "buffDescription": aciklama,
            "buffRound": tur, "buffTime": sn, "buffSuperposition": yigin, "isGoodBuff": iyi, "isDot": 0,
            "isFrozen": 0}


def _etki(bid, islev, p1=0.0, p2=0.0, p3=0.0, p4=0.0):
    return {"buffId": bid, "skillFunctionID": islev, "skillFunctionParam1": float(p1),
            "skillFunctionParam2": float(p2), "skillFunctionParam3": float(p3), "skillFunctionParam4": float(p4)}


# Tanımlar beceri açıklamalarından (SkillInfo) çıkarıldı; "(işaret)" olanlar yalnızca Lua'nın
# luaHasBuff ile baktığı işaret bufflarıdır, sayısal etkileri yoktur. Adlar Türkçe yazıldı; specialEffectWord
# (ekranda beliren kısa yazı) mevcut buff'larla aynı Çince anahtardır, çeviri sözlüğüyle çevrilir.
EK_BUFFLAR = [
    _buff(1147, "Tamamlama sayacı", "Tek elle tamamlama: güçlendirme alındığında sayar", yigin=99),
    _buff(1148, "Tamamlama sayacı+", "Tek elle tamamlama (20152): güçlendirme alındığında sayar", yigin=99),
    _buff(1149, "Mağrur", "Rakipteki her erkek oyuncu için saldırı +%10", yigin=3, soz="攻击力上升"),
    _buff(1150, "Küçümseyen Smaç - kritik", "Küçümseyen Smaç sürerken kesin kritik (işaret)"),
    _buff(1151, "SP1010 güçlendirme", "Ayrılmış (işaret)"),
    _buff(1152, "Gerçek Kong Kükremesi", "Saldırı +%10, 1 tur", tur=1, soz="攻击力上升", fx1="role_skill_damageUp"),
    _buff(1153, "Antrenman Kükremesi I", "Takım saldırısı +%5, 1 tur", tur=1, soz="攻击力上升"),
    _buff(1154, "SP1032 Birikim I", "Her enerji için saldırı +%5, 1 tur", tur=1, yigin=10, soz="攻击力上升"),
    _buff(1155, "SP1032 Birikim II", "Her enerji için saldırı +%8, 1 tur", tur=1, yigin=10, soz="攻击力上升"),
    _buff(1156, "Daha Hızlı Eller", "Sevimli Tanrı / Işık Hızı Üçlük güçlendirme (işaret)"),
    _buff(1157, "Çağın Lideri - pozisyon 4", "Küçük Top Çağı hasar artışı (işaret)", yigin=99),
    _buff(1158, "Çağın Lideri - pozisyon 3", "Küçük Top Çağı hasar artışı (işaret)", yigin=99),
    _buff(1159, "Antrenman Kükremesi II", "Takım saldırısı +%10, 1 tur", tur=1, soz="攻击力上升"),
    _buff(1160, "Antrenman Kükremesi III", "Takım saldırısı +%15, 1 tur", tur=1, soz="攻击力上升"),
    _buff(1161, "İmparatorun Heybeti", "Eşleşen rakibin dayanıklılık tüketimi artar (özel etki)"),
    _buff(1162, "Takımı Yüreklendir", "Tüm takımın tüm nitelikleri +%5, yığılır", yigin=99, soz="全属性上升"),
    _buff(1163, "Son Söz - pas", "Pası alan şut atar (işaret)", tur=1),
    _buff(1164, "Yanıltma Güçlendirme Sv1", "SP1030: Yanıltma güçlendirme (işaret)", tur=1),
    _buff(1165, "Yanıltma Güçlendirme Sv2", "SP1030: Yanıltma güçlendirme (işaret)", tur=1),
    _buff(1166, "Yanıltma Güçlendirme Sv3", "SP1030: Yanıltma güçlendirme (işaret)", tur=1),
    _buff(1167, "Yanıltma (toplu) Güçlendirme Sv1", "SP1030: Yanıltma güçlendirme (işaret)", tur=1),
    _buff(1168, "Yanıltma (toplu) Güçlendirme Sv2", "SP1030: Yanıltma güçlendirme (işaret)", tur=1),
    _buff(1169, "Yanıltma (toplu) Güçlendirme Sv3", "SP1030: Yanıltma güçlendirme (işaret)", tur=1),
    _buff(1170, "35 Saniye Efsanesi Sv1", "İsabet %100, hasar +%25, 3 tur", tur=3, soz="麦迪时刻",
          fx1="role_skill_damageUp", fx2="role_skill_handHot"),
    _buff(1171, "35 Saniye Efsanesi Sv2", "İsabet %100, hasar +%30, 3 tur", tur=3, soz="麦迪时刻",
          fx1="role_skill_damageUp", fx2="role_skill_handHot"),
    _buff(1172, "35 Saniye Efsanesi Sv3", "İsabet %100, hasar +%35, 3 tur", tur=3, soz="麦迪时刻",
          fx1="role_skill_damageUp", fx2="role_skill_handHot"),
    _buff(1173, "35 Saniye Efsanesi işareti A", "McGrady Hamlesi sayacı (işaret)", tur=3),
    _buff(1174, "35 Saniye Efsanesi işareti B", "McGrady Hamlesi sayacı (işaret)", tur=3),
    _buff(1175, "35 Saniye Efsanesi işareti C", "McGrady Hamlesi sayacı (işaret)", tur=3),
    _buff(1176, "Zamanı Tersine Çevir", "Moral sıfırlandıktan sonra takım işareti", tur=1),
    _buff(2036, "Hasar Güçlendirme", "Hasar +%75", soz="攻击力上升", fx1="role_skill_damageUp"),
    _buff(2097, "Gerçek Sevimlilik", "Topu tutamaz, 3 tur", tur=3, iyi=0, tip=9, soz="混乱", fx1="role_skill_chaos"),
    _buff(2098, "Savunma Kırma", "Hasar azaltma etkileri geçici olarak çalışmaz, 1 tur", tur=1, iyi=0, tip=5, soz="破防"),
    _buff(2099, "As Düellosu - hücum", "Eşleşen oyuncu düellosu (işaret)"),
    _buff(2100, "As Düellosu - savunma", "Eşleşen oyuncu düellosu (işaret)", iyi=0),
    _buff(3006, "Boyun Eğmeyen İrade", "Dayanıklılık yeniler ve hasar azaltma verir, 2 tur", tur=2, soz="伤害减免"),
    # Yerel "Efsane Modu" işareti (Skill_Yerel_Efsane): player_formula bu buff'a bakar.
    _buff(EFSANE_BUFF, "Efsane Modu", "Bloklanamaz, bloğu ve top çalması kesin, dayanıklılığı tükenmez"),
]

# ---------------------------------------------------------------- yerel beceri: Efsane Modu
# Pasif beceri; betik araclar/obb_yamala.py içinde (Skill_QTE/Skill_Yerel_Efsane.lua). Oyuncuya sunucu
# (sunucu/mac.py EFSANE_*) maç beceri listesiyle verir. Maç başında isaret buff'ını ekler, dayanıklılık
# tüketimini kapatır, blok/çalma bekleme sürelerini sıfırlar.
EFSANE_BECERI = 90001
EK_BECERILER = [{
    "skillId": EFSANE_BECERI, "skillName": "Efsane Modu",
    "skillDescription": "Şutları bloklanamaz; arkadan gelen blokları ve top çalmaları kesin başarılı olur; "
                        "dayanıklılığı hiç tükenmez.",
    "portraitDescription": "", "skillScript": "Skill_QTE/Skill_Yerel_Efsane", "skillType": 3,
    "skillCoolDown": 0, "energyCost": 0, "actionType": [0], "isNoBall": 0, "skillIcon": "ShuaiQi",
    "damageParameter": 1.0, "initCount": 0, "maxCount": 0, "initCoolDown": 0, "skillClass": 0,
    "superSkillType": [1], "targetType": 0, "skillPriority": 0, "cooperation": 0, "weightAdd": 1,
    "isWeightAskScript": 0, "isDizzyLimit": 1, "isPKLimit": 0, "isChaosLimit": 0, "atkPressureUse": 0,
    "atkPressureGoal": 0, "skillIconColor": 3, "skillDisplayType": 5,
}]

EK_BUFF_ETKILERI = [
    _etki(1149, 127, 0, 1.10),
    _etki(1152, 127, 0, 1.10),
    _etki(1153, 127, 0, 1.05),
    _etki(1154, 127, 0, 1.05),
    _etki(1155, 127, 0, 1.08),
    _etki(1159, 127, 0, 1.10),
    _etki(1160, 127, 0, 1.15),
    _etki(1162, 136, 0, 1.05),
    _etki(1170, 126, 100), _etki(1170, 127, 0, 1.25),
    _etki(1171, 126, 100), _etki(1171, 127, 0, 1.30),
    _etki(1172, 126, 100), _etki(1172, 127, 0, 1.35),
    _etki(2036, 127, 0, 1.75),
    _etki(2097, 335),
]


# ---------------------------------------------------------------- Lua tarafı (BuffInformation_LuaTab)

def _lua_deger(v):
    if isinstance(v, list):
        return "{" + ",".join(str(x) for x in v) + "}"
    if isinstance(v, str):
        return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return str(v)


# Lua tarafında da tamamlanacak tablolar: (tablo adı, anahtar alan, kayıtlar)
LUA_EK_TABLOLAR = (("BuffInformation", "buffId", EK_BUFFLAR), ("SkillInfo", "skillId", EK_BECERILER))


def buff_lua_eki():
    """LuaConfManager.lua sonuna eklenecek parça: Lua tarafındaki BuffInformation ve SkillInfo tablolarını
    tamamlar. (Betikler LuaConfManager.getBuffInformation(id).isGoodBuff, MatchLoader yaması
    LuaConfManager.getSkillInfo(id) gibi alanlara bakıyor.)"""
    satirlar = ["\r\n-- yerel sunucu yamasi: betiklerin kullandigi, tabloda olmayan buff/beceri tanimlari\r\n"]
    for tablo, anahtar, kayitlar in LUA_EK_TABLOLAR:
        satirlar.append("YEREL_EK_%s = {\r\n" % tablo)
        for b in kayitlar:
            alanlar = ",".join("%s=%s" % (k, _lua_deger(v)) for k, v in b.items())
            satirlar.append("\t{" + alanlar + "},\r\n")
        satirlar.append("}\r\n")
        satirlar.append(
            "local yerel_%(t)s_onjson = %(t)sReader.OnJsonCall\r\n"
            "function %(t)sReader.OnJsonCall(data)\r\n"
            "\tyerel_%(t)s_onjson(data)\r\n"
            "\tif %(t)s_keydata == nil then %(t)s_keydata = {} end\r\n"
            "\tif %(t)s_data == nil then %(t)s_data = {} end\r\n"
            "\tfor _, b in ipairs(YEREL_EK_%(t)s) do\r\n"
            "\t\tif %(t)s_keydata[\"key_\" .. b.%(a)s] == nil then\r\n"
            "\t\t\t%(t)s_keydata[\"key_\" .. b.%(a)s] = b\r\n"
            "\t\t\ttable.insert(%(t)s_data, b)\r\n"
            "\t\tend\r\n"
            "\tend\r\nend\r\n" % {"t": tablo, "a": anahtar})
    return "".join(satirlar)


# ---------------------------------------------------------------- Unity serileştirme (little-endian)

def _i32(v):
    return struct.pack("<i", v)


def _metin(t):
    b = t.encode("utf-8")
    return _i32(len(b)) + b + b"\0" * ((-len(b)) % 4)


def _bool(v):
    return bytes([1 if v else 0, 0, 0, 0])


def buff_bilgi_bayt(r):
    return (_i32(r["buffId"]) + _i32(r["effectType"]) + _i32(r["buffIconID"])
            + _i32(len(r["buffType"])) + b"".join(_i32(x) for x in r["buffType"])
            + _metin(r["specialEffectWord"]) + _metin(r["specialEffectOne"]) + _metin(r["specialEffectTwo"])
            + _metin(r["buffName"]) + _metin(r["buffDescription"])
            + _i32(r["buffRound"]) + _i32(r["buffTime"]) + _i32(r["buffSuperposition"])
            + _bool(r["isGoodBuff"]) + _bool(r["isDot"]) + _bool(r["isFrozen"]))


def buff_etki_bayt(r):
    return struct.pack("<ii4d", r["buffId"], r["skillFunctionID"], r["skillFunctionParam1"],
                       r["skillFunctionParam2"], r["skillFunctionParam3"], r["skillFunctionParam4"])


def _oku_i32(b, o):
    return struct.unpack_from("<i", b, o)[0], o + 4


def _oku_metin(b, o):
    n, o = _oku_i32(b, o)
    s = b[o:o + n].decode("utf-8")
    o += n
    return s, (o + 3) & ~3


def mono_adi(raw):
    """MonoBehaviour ham verisi: m_GameObject(8) m_Enabled(4) m_Script(8) m_Name(metin) data..."""
    ad, o = _oku_metin(raw, 20)
    return ad, o


def buff_bilgi_oku(raw):
    ad, o = mono_adi(raw)
    n, o = _oku_i32(raw, o)
    kayitlar = []
    for _ in range(n):
        r = {}
        r["buffId"], o = _oku_i32(raw, o)
        r["effectType"], o = _oku_i32(raw, o)
        r["buffIconID"], o = _oku_i32(raw, o)
        c, o = _oku_i32(raw, o)
        r["buffType"] = list(struct.unpack_from("<%di" % c, raw, o))
        o += 4 * c
        for k in ("specialEffectWord", "specialEffectOne", "specialEffectTwo", "buffName", "buffDescription"):
            r[k], o = _oku_metin(raw, o)
        r["buffRound"], o = _oku_i32(raw, o)
        r["buffTime"], o = _oku_i32(raw, o)
        r["buffSuperposition"], o = _oku_i32(raw, o)
        for k in ("isGoodBuff", "isDot", "isFrozen"):
            r[k] = raw[o]
            o += 4
        kayitlar.append(r)
    if o != len(raw):
        raise ValueError("BuffInformation beklenmedik uzunluk: %d != %d" % (o, len(raw)))
    return kayitlar


def buff_etki_oku(raw):
    ad, o = mono_adi(raw)
    n, o = _oku_i32(raw, o)
    kayitlar = []
    for _ in range(n):
        v = struct.unpack_from("<ii4d", raw, o)
        o += 40
        kayitlar.append(_etki(*v))
    if o != len(raw):
        raise ValueError("BuffEffect beklenmedik uzunluk: %d != %d" % (o, len(raw)))
    return kayitlar


def kayit_bayt(kayit, alanlar):
    """conf_duzenleri.json düzeniyle ([(ad, tür)]) bir kaydı serileştirir."""
    return b"".join(_yaz_alan(kayit[ad], tur) for ad, tur in alanlar)


def tablo_ekle(raw, ekler, bayt_fn):
    """Holder nesnesine kayıt ekler: başlık + sayı + eski kayıtlar (olduğu gibi) + yeni kayıtlar."""
    ad, o = mono_adi(raw)
    n, _ = _oku_i32(raw, o)
    return raw[:o] + _i32(n + len(ekler)) + raw[o + 4:] + b"".join(bayt_fn(r) for r in ekler)


# ---------------------------------------------------------------- UnityWeb paketi ve SerializedFile

def _cstr(b, o):
    e = b.index(b"\0", o)
    return b[o:e].decode(), e + 1


def paketi_ac(paket):
    """UnityWeb -> (üst bilgi sözlüğü, iç dosya adı, SerializedFile baytları)"""
    o = 0
    imza, o = _cstr(paket, o)
    if imza != "UnityWeb":
        raise ValueError("UnityWeb paketi degil: %r" % imza)
    surum = struct.unpack_from(">i", paket, o)[0]
    o += 4
    oyuncu_surumu, o = _cstr(paket, o)
    motor_surumu, o = _cstr(paket, o)
    _en_az, baslik_boyu, seviye_indir, seviye_sayisi = struct.unpack_from(">IIII", paket, o)
    yuk = lzma.decompress(paket[baslik_boyu:], format=lzma.FORMAT_ALONE)
    sayi = struct.unpack_from(">i", yuk, 0)[0]
    if sayi != 1:
        raise ValueError("pakette %d dosya var, 1 bekleniyordu" % sayi)
    ad, p = _cstr(yuk, 4)
    basla, uzunluk = struct.unpack_from(">II", yuk, p)
    ust = {"surum": surum, "oyuncu": oyuncu_surumu, "motor": motor_surumu, "seviye_indir": seviye_indir,
           "seviye_sayisi": seviye_sayisi, "veri_basligi": basla}
    return ust, ad, yuk[basla:basla + uzunluk]


def paketi_kapat(ust, ad, sf):
    """SerializedFile -> UnityWeb (özgün paketle aynı yapı: lzma_alone, 512 KB sözlük, bilinen boyut)."""
    ic = struct.pack(">i", 1) + ad.encode() + b"\0" + struct.pack(">II", ust["veri_basligi"], len(sf))
    ic += b"\0" * (ust["veri_basligi"] - len(ic))
    yuk = ic + sf
    sikisik = lzma.compress(yuk, format=lzma.FORMAT_ALONE,
                            filters=[{"id": lzma.FILTER_LZMA1, "dict_size": 1 << 19, "lc": 3, "lp": 0, "pb": 2}])
    sikisik = sikisik[:5] + struct.pack("<q", len(yuk)) + sikisik[13:]  # özgün pakette boyut yazılı
    baslik_boyu = 9 + 4 + len(ust["oyuncu"]) + 1 + len(ust["motor"]) + 1 + 16 + 8 * ust["seviye_sayisi"] + 4 + 4 + 1
    toplam = baslik_boyu + len(sikisik)
    baslik = (b"UnityWeb\0" + struct.pack(">i", ust["surum"]) + ust["oyuncu"].encode() + b"\0"
              + ust["motor"].encode() + b"\0"
              + struct.pack(">IIII", toplam, baslik_boyu, ust["seviye_indir"], ust["seviye_sayisi"])
              + struct.pack(">II", len(sikisik), len(yuk)) * ust["seviye_sayisi"]
              + struct.pack(">II", toplam, ust["veri_basligi"]) + b"\0")
    assert len(baslik) == baslik_boyu
    return baslik + sikisik


def nesne_tablosu(sf):
    """Biçim 9 SerializedFile: nesne tablosunu (konum, [(path_id, bas, boy, tip, sinif, silik)]) bulur.
    Tip ağacı çözmeden: 20 baytlık girişler zinciri veri bölümünü boşluksuz (8 hizalı) kaplamalı."""
    veri_basi = struct.unpack_from(">I", sf, 12)[0]
    veri_boyu = len(sf) - veri_basi
    for konum in range(16, veri_basi - 24):
        sayi = struct.unpack_from("<i", sf, konum)[0]
        if not 1 <= sayi <= 100000 or konum + 4 + 20 * sayi > veri_basi:
            continue
        girisler, bitis, iyi = [], 0, True
        for k in range(sayi):
            g = struct.unpack_from("<iIIihh", sf, konum + 4 + 20 * k)
            if g[1] != (bitis + 7) & ~7 or g[2] <= 0:
                iyi = False
                break
            girisler.append(g)
            bitis = g[1] + g[2]
        if iyi and bitis == veri_boyu:
            return konum + 4, girisler
    raise ValueError("nesne tablosu bulunamadi")


def sf_yamala(sf, degistir, zorunlu=None):
    """degistir: {m_Name: fn(raw)->raw}. MonoBehaviour (sınıf 114) nesnelerini ada göre bulup değiştirir,
    veri bölümünü yeniden dizer, tabloyu ve dosya boyunu günceller. Diğer baytlar olduğu gibi kalır."""
    veri_basi = struct.unpack_from(">I", sf, 12)[0]
    konum, girisler = nesne_tablosu(sf)
    yeni_veri, yeni_girisler, degisen = bytearray(), [], set()
    for path_id, bas, boy, tip, sinif, silik in girisler:
        raw = sf[veri_basi + bas: veri_basi + bas + boy]
        if sinif == 114:
            ad, _ = mono_adi(raw)
            if ad in degistir:
                raw = degistir[ad](raw)
                degisen.add(ad)
        yeni_veri += b"\0" * ((-len(yeni_veri)) % 8)
        yeni_girisler.append((path_id, len(yeni_veri), len(raw), tip, sinif, silik))
        yeni_veri += raw
    eksik = set(degistir if zorunlu is None else zorunlu) - degisen
    if eksik:
        raise ValueError("pakette bulunamayan tablolar: %s" % sorted(eksik))
    ust = bytearray(sf[:veri_basi])
    for k, g in enumerate(yeni_girisler):
        struct.pack_into("<iIIihh", ust, konum + 20 * k, *g)
    struct.pack_into(">I", ust, 4, veri_basi + len(yeni_veri))
    return bytes(ust) + bytes(yeni_veri)


# ---------------------------------------------------------------- genel tablo düzeni (çeviri için)
# Tip ağacı yok; her holder'ın alan düzeni OBB'deki JSON ikizinden (conf_json_qte.assetbundle) çıkarılır:
# JSON değer türleri aday düzeni verir (sayı: int32 / double / float), ham veri ilk kayıt üstünde geri
# izlemeli (DFS) denenerek doğrulanır, sonra bütün kayıtlar okunup JSON ile karşılaştırılır.

JSON_PAKETI = "assets/Android/conf_json_qte.assetbundle"
DUZEN_DOSYASI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "conf_duzenleri.json")


def json_ikizleri(obb_yolu):
    """{tablo adı: JSON kayıt listesi} — OBB'deki conf_json_qte.assetbundle TextAsset'lerinden."""
    import json
    with zipfile.ZipFile(obb_yolu) as z:
        paket = z.read(JSON_PAKETI)
    ust, ad, sf = paketi_ac(paket)
    veri_basi = struct.unpack_from(">I", sf, 12)[0]
    _, girisler = nesne_tablosu(sf)
    sonuc = {}
    for path_id, bas, boy, tip, sinif, silik in girisler:
        if sinif != 49:  # TextAsset
            continue
        raw = sf[veri_basi + bas: veri_basi + bas + boy]
        ad, o = _oku_metin(raw, 0)
        metin, o = _oku_metin(raw, o)
        try:
            veri = json.loads(metin.lstrip("﻿"))
        except ValueError:
            continue
        if isinstance(veri, dict) and isinstance(veri.get("data"), list):
            sonuc[ad] = veri["data"]
    return sonuc


def _sayi_esit(a, b, tur):
    if not isinstance(b, (int, float)) or isinstance(b, bool):
        return False
    if tur == "i":
        return float(b) == float(a)
    if tur == "b":  # JSON'da 0/1 ama 10 gibi değerler de var; C# bool'a true olarak çevirmiş
        return (a != 0) == (b != 0)
    return abs(a - b) <= 1e-5 * max(1.0, abs(b))  # double alanlar float kesinliğinde yazılmış olabiliyor


def _alan_adaylari(deger):
    if isinstance(deger, bool):
        return ["i"]
    if isinstance(deger, int):
        return ["i", "d", "f", "b"]
    if isinstance(deger, float):
        return ["d", "f", "i"]
    if isinstance(deger, str):
        return ["s"]
    if isinstance(deger, list):
        if not deger:
            return ["ai", "as", "ad", "af"]
        if all(isinstance(x, str) for x in deger):
            return ["as"]
        if all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in deger):
            return ["ai", "ad", "af"] if all(isinstance(x, int) for x in deger) else ["ad", "af"]
    return []


def _oku_alan(raw, o, tur):
    if tur == "i" or tur == "b":  # bool: 1 bayt + 4'e hizalama -> int32 gibi okunur
        v = struct.unpack_from("<i", raw, o)[0]
        return v, o + 4
    if tur == "d":
        v = struct.unpack_from("<d", raw, o)[0]
        return v, o + 8
    if tur == "f":
        v = struct.unpack_from("<f", raw, o)[0]
        return v, o + 4
    if tur == "s":
        return _oku_metin(raw, o)
    if tur[0] == "a":
        n, o = _oku_i32(raw, o)
        if n < 0 or n > 100000:
            raise ValueError("dizi boyu")
        liste = []
        for _ in range(n):
            v, o = _oku_alan(raw, o, tur[1])
            liste.append(v)
        return liste, o
    raise ValueError(tur)


def _yaz_alan(v, tur):
    if tur == "i":
        return struct.pack("<i", int(v))
    if tur == "b":
        return struct.pack("<i", 1 if v else 0)
    if tur == "d":
        return struct.pack("<d", float(v))
    if tur == "f":
        return struct.pack("<f", float(v))
    if tur == "s":
        return _metin(v)
    if tur[0] == "a":
        return _i32(len(v)) + b"".join(_yaz_alan(x, tur[1]) for x in v)
    raise ValueError(tur)


def _alan_esit(okunan, json_deger, tur):
    if tur == "s":
        return okunan == json_deger
    if tur[0] == "a":
        return isinstance(json_deger, list) and len(okunan) == len(json_deger) and all(
            _alan_esit(a, b, tur[1]) for a, b in zip(okunan, json_deger))
    return _sayi_esit(okunan, json_deger, tur)


def _kayit_oku(raw, o, anahtarlar, duzen):
    r = {}
    for k, tur in zip(anahtarlar, duzen):
        r[k], o = _oku_alan(raw, o, tur)
    return r, o


def tablo_duzeni(raw, kayitlar):
    """(veri başlangıcı, alan adları, alan türleri) ya da None. Türler: i d f s ai as ad af."""
    if not kayitlar:
        return None
    anahtarlar = list(kayitlar[0].keys())
    ad, o = mono_adi(raw)
    n, o = _oku_i32(raw, o)
    if n != len(kayitlar):
        return None
    ilk = kayitlar[0]
    adaylar = [_alan_adaylari(ilk[k]) for k in anahtarlar]
    if any(not a for a in adaylar):
        return None
    sonuc = []

    def dfs(i, konum, secim):
        if i == len(anahtarlar):
            sonuc.append(list(secim))
            return True
        for tur in adaylar[i]:
            try:
                v, yeni = _oku_alan(raw, konum, tur)
            except (struct.error, ValueError, UnicodeDecodeError):
                continue
            if yeni > len(raw) or not _alan_esit(v, ilk[anahtarlar[i]], tur):
                continue
            secim.append(tur)
            if dfs(i + 1, yeni, secim):
                return True
            secim.pop()
        return False

    if not dfs(0, o, []):
        return None
    duzen = sonuc[0]
    konum = o
    try:
        for kayit in kayitlar:
            okunan, konum = _kayit_oku(raw, konum, anahtarlar, duzen)
            for k, tur in zip(anahtarlar, duzen):
                if not _alan_esit(okunan[k], kayit[k], tur):
                    return None
    except (struct.error, ValueError, UnicodeDecodeError):
        return None
    if konum != len(raw):
        return None
    return o, anahtarlar, duzen


def duzen_dogrula(raw, kayitlar, alanlar):
    """Verilen [(ad, tür)] düzeniyle bütün kayıtları okur; hata açıklaması ya da None döner."""
    try:
        _, o = mono_adi(raw)
        n, o = _oku_i32(raw, o)
        if n != len(kayitlar):
            return "kayit sayisi %d != %d" % (n, len(kayitlar))
        for kayit in kayitlar:
            for isim, tur in alanlar:
                v, o = _oku_alan(raw, o, tur)
                if not _alan_esit(v, kayit[isim], tur):
                    return "deger uyusmadi %s=%r/%r" % (isim, v, kayit[isim])
        if o != len(raw):
            return "bitis %d != %d" % (o, len(raw))
    except (struct.error, ValueError, UnicodeDecodeError, KeyError) as e:
        return "okuma hatasi %s" % e
    return None


def duzenleri_yukle():
    if not os.path.exists(DUZEN_DOSYASI):
        return {}
    import json
    with open(DUZEN_DOSYASI, encoding="utf-8") as f:
        return json.load(f)


def tablo_cevir(raw, kayitlar, sozluk, bilinen=None):
    """Tablodaki metin alanlarını sözlükle çevirir; düzen çözülemezse (None, 0) döner.
    bilinen: conf_duzenleri.json'dan [(ad, tür)] listesi; doğrulanırsa kullanılır, yoksa JSON'dan çıkarılır."""
    d = None
    if bilinen and duzen_dogrula(raw, kayitlar, bilinen) is None:
        _, o = mono_adi(raw)
        d = (o + 4, [a for a, _ in bilinen], [t for _, t in bilinen])
    if d is None:
        d = tablo_duzeni(raw, kayitlar)
    if d is None:
        return None, 0
    o, anahtarlar, duzen = d
    if "s" not in duzen and "as" not in duzen:
        return raw, 0
    konum, parcalar, sayac = o, [raw[:o]], 0
    for _ in kayitlar:
        okunan, konum = _kayit_oku(raw, konum, anahtarlar, duzen)
        for k, tur in zip(anahtarlar, duzen):
            if tur == "s" and okunan[k] in sozluk:
                okunan[k] = sozluk[okunan[k]]
                sayac += 1
            elif tur == "as":
                sayac += sum(1 for x in okunan[k] if x in sozluk)
                okunan[k] = [sozluk.get(x, x) for x in okunan[k]]
            parcalar.append(_yaz_alan(okunan[k], tur))
    return b"".join(parcalar), sayac


# ---------------------------------------------------------------- üst düzey

def conf_yamala(paket, ikizler=None, sozluk=None, rapor=None):
    """Ham conf_qte.assetbundle baytları -> yamalı paket baytları.
    ikizler: {tablo: JSON kayıtları} ve sozluk: {Çince: Türkçe} verilirse metin alanları da çevrilir.
    rapor (dict) verilirse tablo başına çevrilen metin sayısı / çözülemeyen tablolar yazılır."""
    ust, ad, sf = paketi_ac(paket)
    if sf_yamala(sf, {}) != sf:
        raise ValueError("SerializedFile yeniden dizimi ozgunle ayni degil; bicim varsayimi yanlis")
    ikizler, sozluk = ikizler or {}, sozluk or {}
    rapor = rapor if rapor is not None else {}
    duzenler = duzenleri_yukle()

    def cevir(ad, raw):
        if ad not in ikizler or not sozluk:
            return raw
        yeni, sayac = tablo_cevir(raw, ikizler[ad], sozluk, duzenler.get(ad))
        if yeni is None:
            rapor.setdefault("cozulemeyen", []).append(ad)
            return raw
        if sayac:
            rapor.setdefault("cevrilen", {})[ad] = sayac
        return yeni

    def bilgi(raw):
        raw = cevir("BuffInformation", raw)
        mevcut = {r["buffId"] for r in buff_bilgi_oku(raw)}
        ekler = [dict(r, specialEffectWord=sozluk.get(r["specialEffectWord"], r["specialEffectWord"]))
                 for r in EK_BUFFLAR if r["buffId"] not in mevcut]
        return tablo_ekle(raw, ekler, buff_bilgi_bayt)

    def etki(raw):
        var = {r["buffId"] for r in buff_etki_oku(raw)}
        return tablo_ekle(raw, [r for r in EK_BUFF_ETKILERI if r["buffId"] not in var], buff_etki_bayt)

    def beceri(raw):
        raw = cevir("SkillInfo", raw)
        alanlar = duzenler.get("SkillInfo")
        if not alanlar:
            raise ValueError("SkillInfo duzeni yok (conf_duzenleri.json)")
        _, o = mono_adi(raw)
        n, o = _oku_i32(raw, o)
        var = set()
        for _ in range(n):
            kayit, o = _kayit_oku(raw, o, [a for a, _ in alanlar], [t for _, t in alanlar])
            var.add(kayit["skillId"])
        return tablo_ekle(raw, [r for r in EK_BECERILER if r["skillId"] not in var],
                          lambda r: kayit_bayt(r, alanlar))

    degistir = {ad: (lambda raw, ad=ad: cevir(ad, raw)) for ad in ikizler}
    degistir["BuffInformation"] = bilgi
    degistir["BuffEffect"] = etki
    degistir["SkillInfo"] = beceri
    yeni_sf = sf_yamala(sf, degistir, zorunlu=("BuffInformation", "BuffEffect", "SkillInfo"))
    return paketi_kapat(ust, ad, yeni_sf)


def dogrula(paket):
    """Yamalı paketi açıp tabloları yeniden okur; (buff sayısı, etki sayısı) döner."""
    ust, ad, sf = paketi_ac(paket)
    veri_basi = struct.unpack_from(">I", sf, 12)[0]
    _, girisler = nesne_tablosu(sf)
    if struct.unpack_from(">I", sf, 4)[0] != len(sf):
        raise ValueError("dosya boyu basligi uyusmuyor")
    sonuc = {}
    for path_id, bas, boy, tip, sinif, silik in girisler:
        raw = sf[veri_basi + bas: veri_basi + bas + boy]
        if sinif != 114:
            continue
        ad, _ = mono_adi(raw)
        if ad == "BuffInformation":
            sonuc["buff"] = buff_bilgi_oku(raw)
        elif ad == "BuffEffect":
            sonuc["etki"] = buff_etki_oku(raw)
        elif ad == "SkillInfo":
            alanlar = duzenleri_yukle().get("SkillInfo")
            if alanlar:
                _, o = mono_adi(raw)
                n, o = _oku_i32(raw, o)
                idler = []
                for _ in range(n):
                    kayit, o = _kayit_oku(raw, o, [a for a, _ in alanlar], [t for _, t in alanlar])
                    idler.append(kayit["skillId"])
                if o != len(raw):
                    raise ValueError("SkillInfo beklenmedik uzunluk")
                sonuc["beceri"] = idler
    return sonuc


def obb_paketi(obb_yolu):
    with zipfile.ZipFile(obb_yolu) as z:
        return z.read(PAKET_ADI)


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    cikti = argv[2] if len(argv) > 2 else VARSAYILAN_CIKTI
    ozgun = obb_paketi(argv[1])
    sozluk = {}
    if os.path.exists(CEVIRI_JSON):
        import json
        with open(CEVIRI_JSON, encoding="utf-8") as f:
            sozluk = json.load(f)
    rapor = {}
    yamali = conf_yamala(ozgun, json_ikizleri(argv[1]), sozluk, rapor)
    for ad in rapor.get("cozulemeyen", []):
        print("duzeni cozulemedi (cevrilmedi):", ad)
    cevrilen = rapor.get("cevrilen", {})
    print("cevrilen metin: %d (tablo: %d)" % (sum(cevrilen.values()), len(cevrilen)))
    s = dogrula(yamali)
    idler = {r["buffId"] for r in s["buff"]}
    eksik = [r["buffId"] for r in EK_BUFFLAR if r["buffId"] not in idler]
    if eksik:
        raise SystemExit("dogrulama basarisiz, eksik: %s" % eksik)
    with open(cikti, "wb") as f:
        f.write(yamali)
    print("yazildi: %s (%d bayt, md5 %s)" % (cikti, len(yamali), hashlib.md5(yamali).hexdigest()))
    if EFSANE_BECERI not in s.get("beceri", []):
        raise SystemExit("dogrulama basarisiz: SkillInfo'da %d yok" % EFSANE_BECERI)
    print("buff: %d kayit (+%d), etki: %d kayit (+%d), beceri: %d kayit (+%d)" % (
        len(s["buff"]), len(EK_BUFFLAR), len(s["etki"]), len(EK_BUFF_ETKILERI), len(s["beceri"]), len(EK_BECERILER)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
