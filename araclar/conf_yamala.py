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
VARSAYILAN_CIKTI = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "sunucu", "veri", "conf_qte.assetbundle")

# Beceri işlev kimlikleri (BuffEffect.skillFunctionID), mevcut tablodaki kullanımdan:
#   126 = isabet + p1 puan, 127 = saldırı x p2, 136 = tüm nitelikler x p2, 335 = topu tutamaz.


def _buff(bid, ad, aciklama, tur=0, sn=0, yigin=1, iyi=1, tip=0, soz="0", fx1="0", fx2="0"):
    return {"buffId": bid, "effectType": 0, "buffIconID": 0, "buffType": [tip], "specialEffectWord": soz,
            "specialEffectOne": fx1, "specialEffectTwo": fx2, "buffName": ad, "buffDescription": aciklama,
            "buffRound": tur, "buffTime": sn, "buffSuperposition": yigin, "isGoodBuff": iyi, "isDot": 0,
            "isFrozen": 0}


def _etki(bid, islev, p1=0.0, p2=0.0, p3=0.0, p4=0.0):
    return {"buffId": bid, "skillFunctionID": islev, "skillFunctionParam1": float(p1),
            "skillFunctionParam2": float(p2), "skillFunctionParam3": float(p3), "skillFunctionParam4": float(p4)}


# Tanımlar beceri açıklamalarından (SkillInfo) çıkarıldı; "标记" olanlar yalnızca Lua'nın
# luaHasBuff ile baktığı işaret bufflarıdır, sayısal etkileri yoktur.
EK_BUFFLAR = [
    _buff(1147, "补扣计数", "单手补扣：获得增益时计数", yigin=99),
    _buff(1148, "补扣计数·强化", "单手补扣（20152）：获得增益时计数", yigin=99),
    _buff(1149, "傲娇", "敌方每有一位男性球员，攻击力提高10%", yigin=3, soz="攻击力上升"),
    _buff(1150, "蔑视灌篮·暴击", "蔑视灌篮进行中必定暴击 标记"),
    _buff(1151, "SP1010 增益", "预留 标记"),
    _buff(1152, "真·金刚怒吼功", "攻击力提高10%，持续1回合", tur=1, soz="攻击力上升", fx1="role_skill_damageUp"),
    _buff(1153, "特训·怒吼 I", "全队攻击力提高5%，持续1回合", tur=1, soz="攻击力上升"),
    _buff(1154, "SP1032 蓄力 I", "每点活力攻击力提高5%，持续1回合", tur=1, yigin=10, soz="攻击力上升"),
    _buff(1155, "SP1032 蓄力 II", "每点活力攻击力提高8%，持续1回合", tur=1, yigin=10, soz="攻击力上升"),
    _buff(1156, "更快的手速", "萌神/光速三分 强化 标记"),
    _buff(1157, "时代领袖·位置4", "小球时代伤害提升 标记", yigin=99),
    _buff(1158, "时代领袖·位置3", "小球时代伤害提升 标记", yigin=99),
    _buff(1159, "特训·怒吼 II", "全队攻击力提高10%，持续1回合", tur=1, soz="攻击力上升"),
    _buff(1160, "特训·怒吼 III", "全队攻击力提高15%，持续1回合", tur=1, soz="攻击力上升"),
    _buff(1161, "帝王の威势", "对位球员体力消耗提高（自定义效果）"),
    _buff(1162, "鼓舞队友", "全队全属性提升5%，可叠加", yigin=99, soz="全属性上升"),
    _buff(1163, "后出手的权力·传球", "接球后投篮 标记", tur=1),
    _buff(1164, "诱导术强化 Lv1", "SP1030：诱导术强化 标记", tur=1),
    _buff(1165, "诱导术强化 Lv2", "SP1030：诱导术强化 标记", tur=1),
    _buff(1166, "诱导术强化 Lv3", "SP1030：诱导术强化 标记", tur=1),
    _buff(1167, "诱导术（拿球）强化 Lv1", "SP1030：诱导术强化 标记", tur=1),
    _buff(1168, "诱导术（拿球）强化 Lv2", "SP1030：诱导术强化 标记", tur=1),
    _buff(1169, "诱导术（拿球）强化 Lv3", "SP1030：诱导术强化 标记", tur=1),
    _buff(1170, "35秒传奇 Lv1", "命中率100%，伤害提高25%，持续3回合", tur=3, soz="麦迪时刻",
          fx1="role_skill_damageUp", fx2="role_skill_handHot"),
    _buff(1171, "35秒传奇 Lv2", "命中率100%，伤害提高30%，持续3回合", tur=3, soz="麦迪时刻",
          fx1="role_skill_damageUp", fx2="role_skill_handHot"),
    _buff(1172, "35秒传奇 Lv3", "命中率100%，伤害提高35%，持续3回合", tur=3, soz="麦迪时刻",
          fx1="role_skill_damageUp", fx2="role_skill_handHot"),
    _buff(1173, "35秒传奇 标记 A", "麦氏绝技计数 标记", tur=3),
    _buff(1174, "35秒传奇 标记 B", "麦氏绝技计数 标记", tur=3),
    _buff(1175, "35秒传奇 标记 C", "麦氏绝技计数 标记", tur=3),
    _buff(1176, "逆转时空", "士气重置后全队 标记", tur=1),
    _buff(2036, "伤害强化", "伤害提高75%", soz="攻击力上升", fx1="role_skill_damageUp"),
    _buff(2097, "真·萌萌哒", "无法持球，持续3回合", tur=3, iyi=0, tip=9, soz="混乱", fx1="role_skill_chaos"),
    _buff(2098, "破防", "伤害减免效果暂时无效，持续1回合", tur=1, iyi=0, tip=5, soz="破防"),
    _buff(2099, "王牌の对决·进攻", "对位对决 标记"),
    _buff(2100, "王牌の对决·防守", "对位对决 标记", iyi=0),
    _buff(3006, "不屈意志", "回复体力并获得伤害减免，持续2回合", tur=2, soz="伤害减免"),
]

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


def buff_lua_eki():
    """LuaConfManager.lua sonuna eklenecek parça: Lua tarafındaki BuffInformation tablosunu tamamlar.
    (Betikler LuaConfManager.getBuffInformation(id).isGoodBuff gibi alanlara bakıyor.)"""
    satirlar = ["\r\n-- yerel sunucu yamasi: betiklerin kullandigi, tabloda olmayan buff tanimlari\r\n",
                "YEREL_EK_BUFFLAR = {\r\n"]
    for b in EK_BUFFLAR:
        alanlar = ",".join("%s=%s" % (k, _lua_deger(v)) for k, v in b.items())
        satirlar.append("\t{" + alanlar + "},\r\n")
    satirlar.append("}\r\n")
    satirlar.append(
        "local yerel_buff_onjson = BuffInformationReader.OnJsonCall\r\n"
        "function BuffInformationReader.OnJsonCall(data)\r\n"
        "\tyerel_buff_onjson(data)\r\n"
        "\tif BuffInformation_keydata == nil then BuffInformation_keydata = {} end\r\n"
        "\tif BuffInformation_data == nil then BuffInformation_data = {} end\r\n"
        "\tfor _, b in ipairs(YEREL_EK_BUFFLAR) do\r\n"
        "\t\tif BuffInformation_keydata[\"key_\" .. b.buffId] == nil then\r\n"
        "\t\t\tBuffInformation_keydata[\"key_\" .. b.buffId] = b\r\n"
        "\t\t\ttable.insert(BuffInformation_data, b)\r\n"
        "\t\tend\r\n"
        "\tend\r\nend\r\n")
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


def sf_yamala(sf, degistir):
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
    eksik = set(degistir) - degisen
    if eksik:
        raise ValueError("pakette bulunamayan tablolar: %s" % sorted(eksik))
    ust = bytearray(sf[:veri_basi])
    for k, g in enumerate(yeni_girisler):
        struct.pack_into("<iIIihh", ust, konum + 20 * k, *g)
    struct.pack_into(">I", ust, 4, veri_basi + len(yeni_veri))
    return bytes(ust) + bytes(yeni_veri)


# ---------------------------------------------------------------- üst düzey

def conf_yamala(paket):
    """Ham conf_qte.assetbundle baytları -> yamalı paket baytları."""
    ust, ad, sf = paketi_ac(paket)
    if sf_yamala(sf, {}) != sf:
        raise ValueError("SerializedFile yeniden dizimi ozgunle ayni degil; bicim varsayimi yanlis")
    mevcut = set()

    def bilgi(raw):
        mevcut.update(r["buffId"] for r in buff_bilgi_oku(raw))
        return tablo_ekle(raw, [r for r in EK_BUFFLAR if r["buffId"] not in mevcut], buff_bilgi_bayt)

    def etki(raw):
        var = {r["buffId"] for r in buff_etki_oku(raw)}
        return tablo_ekle(raw, [r for r in EK_BUFF_ETKILERI if r["buffId"] not in var], buff_etki_bayt)

    yeni_sf = sf_yamala(sf, {"BuffInformation": bilgi, "BuffEffect": etki})
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
    yamali = conf_yamala(ozgun)
    s = dogrula(yamali)
    idler = {r["buffId"] for r in s["buff"]}
    eksik = [r["buffId"] for r in EK_BUFFLAR if r["buffId"] not in idler]
    if eksik:
        raise SystemExit("dogrulama basarisiz, eksik: %s" % eksik)
    with open(cikti, "wb") as f:
        f.write(yamali)
    print("yazildi: %s (%d bayt, md5 %s)" % (cikti, len(yamali), hashlib.md5(yamali).hexdigest()))
    print("buff: %d kayit (+%d), etki: %d kayit (+%d)" % (
        len(s["buff"]), len(EK_BUFFLAR), len(s["etki"]), len(EK_BUFF_ETKILERI)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
