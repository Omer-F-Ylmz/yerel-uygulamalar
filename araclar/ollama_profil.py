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


def klasorleri_aktar():
    for ad in KLASORLER:
        kaynak, hedef = os.path.join(ESKI, ad), os.path.join(YENI, ad)
        if not os.path.isdir(kaynak):
            continue
        try:
            # symlinks=False: bağlantının gösterdiği içerik kopyalanır (Windows'ta var olan bağlantı hatası olmaz)
            shutil.copytree(kaynak, hedef, dirs_exist_ok=True, symlinks=False, ignore_dangling_symlinks=True,
                            ignore=shutil.ignore_patterns(".git", "node_modules", "__pycache__"))
            atlanan = 0
        except shutil.Error as hata:
            atlanan = len(hata.args[0]) if hata.args and isinstance(hata.args[0], list) else 1
        print("  %-9s %d oge aktarildi%s" % (ad, say(kaynak),
                                             ("  (%d dosya kopyalanamadi, atlandi)" % atlanan) if atlanan else ""))


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
