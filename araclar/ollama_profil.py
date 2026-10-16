"""Normal Claude Code profilindeki özellikleri Ollama profiline (~/.claude-ollama) aktarır.

  python ollama_profil.py hepsi      -> skill, ajan, komut, eklenti ve MCP sunucularının hepsini aktarır
  python ollama_profil.py mcp        -> MCP sunucularını listeler, seçtiklerini aktarır
  python ollama_profil.py durum      -> iki profilde ne olduğunu gösterir
  python ollama_profil.py sifirla    -> Ollama profilindeki aktarılmış her şeyi siler (giriş/oturum kalır)

Aktarılmayanlar: kimlik bilgileri, oturum geçmişi, hook'lar ve settings.json'daki env ayarları
(env içindeki ANTHROPIC_BASE_URL gibi ayarlar Ollama bağlantısını bozar).
"""
import json
import os
import shutil
import sys

EV = os.path.expanduser("~")
ESKI = os.path.join(EV, ".claude")
YENI = os.path.join(EV, ".claude-ollama")
ESKI_JSON = os.path.join(EV, ".claude.json")
YENI_JSON = os.path.join(YENI, ".claude.json")
KLASORLER = ("skills", "agents", "commands", "plugins")


def json_oku(yol):
    try:
        with open(yol, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def json_yaz(yol, veri):
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    gecici = yol + ".tmp"
    with open(gecici, "w", encoding="utf-8") as f:
        json.dump(veri, f, ensure_ascii=False, indent=2)
    os.replace(gecici, yol)


def say(klasor):
    return len(os.listdir(klasor)) if os.path.isdir(klasor) else 0


ATLA = {".git", "node_modules", "__pycache__"}


def kopyala(kaynak, hedef, sayac, ziyaret=None):
    """Bağlantıları (symlink/junction) gerçek yerine çözerek kopyalar; var olanın üzerine yazar.
    shutil.copytree göreli bağlantıları kırık sanıp sessizce atladığı için kendi yürüyüşümüz."""
    ziyaret = ziyaret if ziyaret is not None else set()  # yalnızca şu anki yolun ataları (döngü kontrolü)
    gercek = os.path.realpath(kaynak)
    if gercek in ziyaret:  # kendi atasını gösteren bağlantı: sonsuz döngü olurdu
        return
    if os.path.islink(hedef):  # önceki yarım denemeden kalan bağlantı: gerçek klasörle değiştir
        try:
            os.unlink(hedef)
        except OSError:
            os.rmdir(hedef)
    os.makedirs(hedef, exist_ok=True)
    try:
        girdiler = os.listdir(gercek)
    except OSError:
        sayac["atlanan"] += 1
        return
    ziyaret.add(gercek)
    for ad in girdiler:
        if ad in ATLA:
            continue
        k, h = os.path.join(gercek, ad), os.path.join(hedef, ad)
        cozulmus = os.path.realpath(k)
        try:
            if os.path.isdir(cozulmus):
                kopyala(cozulmus, h, sayac, ziyaret)
            elif os.path.isfile(cozulmus):
                if os.path.islink(h) or (os.path.exists(h) and not os.path.isfile(h)):
                    os.remove(h) if not os.path.isdir(h) else shutil.rmtree(h)
                shutil.copy2(cozulmus, h)
            else:
                sayac["atlanan"] += 1  # gerçekten kırık bağlantı
        except OSError:
            sayac["atlanan"] += 1
    ziyaret.discard(gercek)


def klasorleri_aktar():
    for ad in KLASORLER:
        kaynak, hedef = os.path.join(ESKI, ad), os.path.join(YENI, ad)
        if not os.path.isdir(kaynak):
            continue
        sayac = {"atlanan": 0}
        kopyala(kaynak, hedef, sayac)
        print("  %-9s %d oge aktarildi%s" % (ad, say(kaynak), ("  (%d dosya kopyalanamadi, atlandi)"
                                                              % sayac["atlanan"]) if sayac["atlanan"] else ""))


def eklenti_ayarlarini_aktar():
    """settings.json'dan yalnızca eklenti seçimlerini alır; env/hook/izin ayarlarına dokunmaz."""
    eski = json_oku(os.path.join(ESKI, "settings.json"))
    yeni_yol = os.path.join(YENI, "settings.json")
    yeni = json_oku(yeni_yol)
    for anahtar in ("enabledPlugins", "extraKnownMarketplaces"):
        if anahtar in eski:
            yeni[anahtar] = eski[anahtar]
    json_yaz(yeni_yol, yeni)
    print("  eklenti secimleri aktarildi (%d eklenti)" % len(eski.get("enabledPlugins", {})))


def mcp_sunuculari():
    return json_oku(ESKI_JSON).get("mcpServers", {})


def mcp_aktar(adlar):
    sunucular = mcp_sunuculari()
    yeni = json_oku(YENI_JSON)
    hedef = yeni.setdefault("mcpServers", {})
    for ad in adlar:
        if ad in sunucular:
            hedef[ad] = sunucular[ad]
    json_yaz(YENI_JSON, yeni)
    print("  %d MCP sunucusu aktarildi" % len([a for a in adlar if a in sunucular]))


def hepsi():
    print("Aktariliyor: %s  ->  %s" % (ESKI, YENI))
    klasorleri_aktar()
    eklenti_ayarlarini_aktar()
    mcp_aktar(list(mcp_sunuculari()))
    print("\nUYARI: Her sey aktarildi. Model 'Prompt is too long' derse sifirla secenegini kullan,")
    print("sonra yalnizca ihtiyacin olanlari tek tek ekle.")


def mcp_sec():
    sunucular = sorted(mcp_sunuculari())
    mevcut = set(json_oku(YENI_JSON).get("mcpServers", {}))
    if not sunucular:
        print("Normal profilde MCP sunucusu bulunamadi.")
        return
    for i, ad in enumerate(sunucular, 1):
        print("  %2d. %s%s" % (i, ad, "   (zaten var)" if ad in mevcut else ""))
    cevap = input("\nAktarilacak numaralar (ornek: 1 3 5, hepsi icin: h): ").strip().lower()
    if cevap in ("h", "hepsi"):
        secilen = sunucular
    else:
        secilen = [sunucular[int(x) - 1] for x in cevap.replace(",", " ").split()
                   if x.isdigit() and 0 < int(x) <= len(sunucular)]
    mcp_aktar(secilen)


def durum():
    for baslik, kok, jsn in (("Normal profil", ESKI, ESKI_JSON), ("Ollama profili", YENI, YENI_JSON)):
        print("== %s (%s)" % (baslik, kok))
        for ad in KLASORLER:
            print("  %-9s %d" % (ad, say(os.path.join(kok, ad))))
        print("  mcp       %d" % len(json_oku(jsn).get("mcpServers", {})))


def sifirla():
    for ad in KLASORLER:
        shutil.rmtree(os.path.join(YENI, ad), ignore_errors=True)
    yeni = json_oku(YENI_JSON)
    if yeni:
        yeni.pop("mcpServers", None)
        json_yaz(YENI_JSON, yeni)
    ayar = os.path.join(YENI, "settings.json")
    if os.path.exists(ayar):
        s = json_oku(ayar)
        s.pop("enabledPlugins", None)
        s.pop("extraKnownMarketplaces", None)
        json_yaz(ayar, s)
    os.makedirs(os.path.join(YENI, "skills"), exist_ok=True)
    print("Ollama profili temizlendi (giris ve ayarlar duruyor).")


if __name__ == "__main__":
    komut = sys.argv[1] if len(sys.argv) > 1 else ""
    {"hepsi": hepsi, "mcp": mcp_sec, "durum": durum, "sifirla": sifirla}.get(
        komut, lambda: print(__doc__))()
