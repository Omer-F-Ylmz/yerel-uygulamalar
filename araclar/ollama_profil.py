"""Normal Claude Code profilindeki özellikleri Ollama profiline (~/.claude-ollama) aktarır.

  python ollama_profil.py hepsi      -> skill, ajan, komut, eklenti ve MCP sunucularının hepsini aktarır
  python ollama_profil.py mcp        -> MCP sunucularını listeler, seçtiklerini aktarır
  python ollama_profil.py durum      -> iki profilde ne olduğunu gösterir
  python ollama_profil.py onar       -> hiçbir şeyi kapatmadan "Prompt is too long" ve hookify hatasını giderir
  python ollama_profil.py hafiza     -> claude-mem'i ücretsiz Gemini anahtarına geçirir
  python ollama_profil.py sifirla    -> Ollama profilindeki aktarılmış her şeyi siler (giriş/oturum kalır)

MCP sunucuları Ollama profilinde doğrudan değil, mcp_kapi.py üzerinden bağlanır: model her mesajda
yüzlerce araç tanımı yerine yalnızca iki araç (mcp_ara, mcp_cagir) görür, sunucuların hepsi yine kullanılabilir.

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
KAPI_AD = "mcp-kapi"
KAPI_KAYNAK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mcp_kapi.py")
KAPI_PY = os.path.join(YENI, "mcp_kapi.py")
KAPI_AYAR = os.path.join(YENI, "mcp_kapi.json")


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
    yeni.pop("disableAllHooks", None)  # hafif moddan çıkış
    json_yaz(yeni_yol, yeni)
    print("  eklenti secimleri aktarildi (%d eklenti)" % len(eski.get("enabledPlugins", {})))


def mcp_sunuculari():
    """Normal profildeki kullanıcı ve proje düzeyindeki MCP sunucuları."""
    j = json_oku(ESKI_JSON)
    sunucular = {}
    for proje in j.get("projects", {}).values():
        sunucular.update(proje.get("mcpServers") or {})
    sunucular.update(j.get("mcpServers", {}))
    return sunucular


def kapi_sunuculari():
    return json_oku(KAPI_AYAR).get("mcpServers", {})


def kapi_kur(eklenecek):
    """Sunucuları kapının ayarına ekler; profilde doğrudan duranları da kapıya taşır."""
    yeni = json_oku(YENI_JSON)
    kapi = kapi_sunuculari()
    dogrudan = yeni.pop("mcpServers", {}) or {}
    for proje in yeni.get("projects", {}).values():
        dogrudan.update(proje.pop("mcpServers", None) or {})
    dogrudan.pop(KAPI_AD, None)
    kapi.update(dogrudan)
    kapi.update(eklenecek)
    json_yaz(KAPI_AYAR, {"mcpServers": kapi})
    shutil.copy2(KAPI_KAYNAK, KAPI_PY)
    yeni["mcpServers"] = {KAPI_AD: {"type": "stdio", "command": sys.executable, "args": [KAPI_PY, KAPI_AYAR]}}
    json_yaz(YENI_JSON, yeni)
    return kapi


def mcp_aktar(adlar):
    sunucular = mcp_sunuculari()
    secilen = {ad: sunucular[ad] for ad in adlar if ad in sunucular}
    toplam = kapi_kur(secilen)
    print("  %d MCP sunucusu aktarildi (kapida toplam %d; model yalnizca 2 arac gorur)" % (len(secilen), len(toplam)))


def hepsi():
    print("Aktariliyor: %s  ->  %s" % (ESKI, YENI))
    klasorleri_aktar()
    eklenti_ayarlarini_aktar()
    mcp_aktar(list(mcp_sunuculari()))
    hookify_onar()


def mcp_sec():
    sunucular = sorted(mcp_sunuculari())
    mevcut = set(kapi_sunuculari())
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


HOOKIFY_SIM = (
    "# Ollama profili onarimi: eski hookify surumleri 'hookify' paketini eklenti klasorunun ustunde\n"
    "# ariyor, eklenti onbellekte surum klasorunde durunca bulamiyordu. Bu paket eklentinin kendisini gosterir.\n"
    "import os\n"
    "__path__ = [os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))]\n")


def hookify_onar():
    """'Hookify import error: No module named hookify' hatasını giderir (iki profilde de)."""
    onarilan = 0
    for kok in (ESKI, YENI):
        for klasor, alt, dosyalar in os.walk(os.path.join(kok, "plugins")):
            alt[:] = [a for a in alt if a not in ATLA]
            if os.path.basename(klasor) != "hooks" or not os.path.isdir(os.path.join(os.path.dirname(klasor), "core")):
                continue
            if not any(_icerir(os.path.join(klasor, d), "hookify") for d in dosyalar if d.endswith(".py")):
                continue
            hedef = os.path.join(klasor, "hookify", "__init__.py")
            os.makedirs(os.path.dirname(hedef), exist_ok=True)
            with open(hedef, "w", encoding="utf-8") as f:
                f.write(HOOKIFY_SIM)
            onarilan += 1
    if onarilan:
        print("  hookify onarildi (%d kopya)" % onarilan)


def _icerir(yol, metin):
    try:
        with open(yol, encoding="utf-8", errors="replace") as f:
            return ("from %s." % metin) in f.read()
    except OSError:
        return False


def onar():
    """Hiçbir şeyi kapatmadan istemi küçültür: MCP'leri kapıya alır, hookify'ı onarır.
    Önceki 'hafif mod' kapattıklarını da geri açar."""
    eklenti_ayarlarini_aktar()
    yedek = os.path.join(YENI, "mcp_yedek.json")
    eski_yedek = json_oku(yedek)
    toplam = kapi_kur(eski_yedek)
    if eski_yedek:
        os.remove(yedek)
    print("  %d MCP sunucusu kapidan bagli: hepsi acik, model yalnizca 2 arac goruyor" % len(toplam))
    hookify_onar()
    print("\nTamam. MCP'lerin calistigini gormek icin menude 'MCP baglanti testi'ni sec.")


def hafiza():
    """claude-mem'in gözlem sağlayıcısını ücretsiz Gemini anahtarına geçirir (iki profil de kullanır)."""
    yol = os.path.join(EV, ".claude-mem", "settings.json")
    ayar = json_oku(yol)
    print("claude-mem hafizasi su an: %s" % ayar.get("CLAUDE_MEM_PROVIDER", "claude"))
    print("Ucretsiz Gemini anahtari: https://aistudio.google.com/app/apikey  (kart gerekmez)")
    anahtar = input("Anahtari yapistir (vazgecmek icin bos Enter): ").strip()
    if not anahtar:
        print("Degisiklik yapilmadi.")
        return
    ayar.update({
        "CLAUDE_MEM_PROVIDER": "gemini",
        "CLAUDE_MEM_GEMINI_API_KEY": anahtar,
        "CLAUDE_MEM_GEMINI_MODEL": "gemini-flash-lite-latest",  # ücretsizde dakikada en çok istek
        "CLAUDE_MEM_GEMINI_RATE_LIMITING_ENABLED": "true",
        "CLAUDE_MEM_SKIP_SUBAGENT_OBSERVATIONS": "true",  # ücretsiz kotayı alt ajanlar tüketmesin
    })
    json_yaz(yol, ayar)
    print("Tamam: claude-mem artik Gemini ile calisiyor (yeniden baslatmak gerekmez).")


def kapi_dene():
    if not os.path.exists(KAPI_AYAR):
        print("Kapida sunucu yok. Once 'Her seyi aktar' ya da 'Onar' sec.")
        return
    import subprocess
    subprocess.call([sys.executable, KAPI_PY, KAPI_AYAR, "--dene"])


def durum():
    for baslik, kok, jsn in (("Normal profil", ESKI, ESKI_JSON), ("Ollama profili", YENI, YENI_JSON)):
        print("== %s (%s)" % (baslik, kok))
        for ad in KLASORLER:
            print("  %-9s %d" % (ad, say(os.path.join(kok, ad))))
        mcp = json_oku(jsn).get("mcpServers", {})
        if KAPI_AD in mcp:
            print("  mcp       %d (kapidan; model 2 arac goruyor)" % len(kapi_sunuculari()))
        else:
            print("  mcp       %d" % len(mcp))
        ayar = json_oku(os.path.join(kok, "settings.json"))
        print("  eklenti   %d acik%s" % (sum(1 for v in ayar.get("enabledPlugins", {}).values() if v),
                                      ", hook'lar kapali" if ayar.get("disableAllHooks") else ""))


def sifirla():
    for ad in KLASORLER:
        shutil.rmtree(os.path.join(YENI, ad), ignore_errors=True)
    yeni = json_oku(YENI_JSON)
    if yeni:
        yeni.pop("mcpServers", None)
        json_yaz(YENI_JSON, yeni)
    for yol in (KAPI_AYAR, os.path.splitext(KAPI_AYAR)[0] + "_araclar.json"):
        if os.path.exists(yol):
            os.remove(yol)
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
    {"hepsi": hepsi, "mcp": mcp_sec, "onar": onar, "hafiza": hafiza,
     "kapi": kapi_dene, "durum": durum, "sifirla": sifirla}.get(
        komut, lambda: print(__doc__))()
