"""Claude Code kurulumunu arkadaşlarla paylaşılabilir bir eklenti pazarına (plugin marketplace) çevirir.

Kaynak : %USERPROFILE%\\.claude  (skills, agents, commands) ve %USERPROFILE%\\.claude.json (MCP sunucuları)
Çıktı  : Masaüstü\\claude-kurulum-paketi  (ya da ilk argüman)

Pakete GİRMEYENLER: kimlik bilgileri, oturum geçmişi, hafıza, önbellekler, hook'lar ve
settings.json (yerel yol ve anahtar içerebilir). MCP ayarlarındaki env/headers değerleri
${DEGISKEN} yer tutucusuna çevrilir. Gizli anahtar deseni içeren dosyalar pakete alınmaz ve
RAPOR.txt'de listelenir. Paketi GitHub'a göndermeden önce RAPOR.txt'yi mutlaka oku.
"""
import json
import os
import re
import shutil
import sys

EV = os.path.expanduser("~")
KAYNAK = os.path.join(EV, ".claude")
SAHIP = os.environ.get("USERNAME") or os.environ.get("USER") or "kullanici"
AZAMI_DOSYA = 5 * 1024 * 1024
METIN_UZANTI = {".md", ".txt", ".json", ".yaml", ".yml", ".py", ".js", ".ts", ".sh", ".ps1", ".bat",
                ".toml", ".cfg", ".ini", ".html", ".css", ".xml", ".csv", ""}
GIZLI_DESENLER = [
    (r"sk-ant-[A-Za-z0-9_\-]{10,}", "Anthropic anahtarı"),
    (r"sk-(proj-)?[A-Za-z0-9]{20,}", "OpenAI benzeri anahtar"),
    (r"gh[pousr]_[A-Za-z0-9]{20,}", "GitHub token"),
    (r"github_pat_[A-Za-z0-9_]{20,}", "GitHub token"),
    (r"AKIA[0-9A-Z]{16}", "AWS anahtarı"),
    (r"xox[abposr]-[A-Za-z0-9\-]{10,}", "Slack token"),
    (r"AIza[0-9A-Za-z_\-]{30,}", "Google API anahtarı"),
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "Özel anahtar"),
    (r"(?i)bearer\s+[A-Za-z0-9._\-]{20,}", "Bearer token"),
    (r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*[\"']?[A-Za-z0-9_\-./+=]{16,}", "anahtar/şifre ataması"),
]
GIZLI_RE = [(re.compile(d), ad) for d, ad in GIZLI_DESENLER]


def gizli_bul(yol):
    if os.path.splitext(yol)[1].lower() not in METIN_UZANTI:
        return None
    try:
        with open(yol, encoding="utf-8", errors="ignore") as f:
            metin = f.read()
    except OSError:
        return None
    for desen, ad in GIZLI_RE:
        if desen.search(metin):
            return ad
    return None


def lisans_var(klasor):
    for kok, _, dosyalar in os.walk(klasor):
        for d in dosyalar:
            if d.upper().startswith(("LICENSE", "LICENCE", "COPYING")):
                return True
    return False


def klasor_kopyala(kaynak, hedef, rapor):
    """Gizli bilgi içeren ve çok büyük dosyaları atlayarak kopyalar; atlananları rapora yazar."""
    for kok, klasorler, dosyalar in os.walk(kaynak):
        klasorler[:] = [k for k in klasorler if k not in (".git", "node_modules", "__pycache__", ".venv")]
        for d in dosyalar:
            k = os.path.join(kok, d)
            goreli = os.path.relpath(k, kaynak)
            if os.path.islink(k):
                continue
            if os.path.getsize(k) > AZAMI_DOSYA:
                rapor["buyuk"].append(os.path.relpath(k, KAYNAK))
                continue
            neden = gizli_bul(k)
            if neden:
                rapor["gizli"].append("%s  (%s)" % (os.path.relpath(k, KAYNAK), neden))
                continue
            h = os.path.join(hedef, goreli)
            os.makedirs(os.path.dirname(h), exist_ok=True)
            shutil.copy2(k, h)


def eklenti_yaz(kok, ad, aciklama):
    yol = os.path.join(kok, "plugins", ad)
    os.makedirs(os.path.join(yol, ".claude-plugin"), exist_ok=True)
    with open(os.path.join(yol, ".claude-plugin", "plugin.json"), "w", encoding="utf-8") as f:
        json.dump({"name": ad, "description": aciklama, "version": "1.0.0", "author": {"name": SAHIP}},
                  f, ensure_ascii=False, indent=2)
    return yol


def mcp_temizle(sunucular, rapor):
    """env/headers değerlerini ${AD} yer tutucusuna çevirir; komut satırındaki anahtar desenlerini işaretler."""
    temiz = {}
    for ad, ayar in sunucular.items():
        ayar = json.loads(json.dumps(ayar))
        for alan in ("env", "headers"):
            if isinstance(ayar.get(alan), dict):
                for k in list(ayar[alan]):
                    degisken = re.sub(r"[^A-Z0-9_]", "_", (ad + "_" + k).upper())
                    ayar[alan][k] = "${%s}" % degisken
                    rapor["mcp_degisken"].append("%s  ->  %s" % (degisken, ad))
        metin = json.dumps(ayar)
        if any(d.search(metin) for d, _ in GIZLI_RE):
            rapor["gizli"].append("MCP sunucusu '%s' (komut/adres içinde anahtar var, pakete alınmadı)" % ad)
            continue
        temiz[ad] = ayar
    return temiz


def kurulu_eklentiler():
    """Kurulu eklentileri ve geldikleri pazarları döner (kopyalanmaz, kurulum komutu olarak verilir)."""
    pazarlar, eklentiler = {}, []
    for dosya, hedef in (("known_marketplaces.json", "pazar"), ("installed_plugins.json", "eklenti")):
        yol = os.path.join(KAYNAK, "plugins", dosya)
        if not os.path.exists(yol):
            continue
        try:
            veri = json.load(open(yol, encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if hedef == "pazar":
            for ad, bilgi in veri.items():
                kaynak = (bilgi or {}).get("source", {}) if isinstance(bilgi, dict) else {}
                pazarlar[ad] = kaynak.get("repo") or kaynak.get("url") or kaynak.get("path") or ad
        else:
            liste = veri.get("plugins", veri) if isinstance(veri, dict) else {}
            eklentiler.extend(liste.keys() if isinstance(liste, dict) else [])
    return pazarlar, sorted(eklentiler)


KURULUM_REHBERI = """# Claude Code kurulum paketi

Bu depo bir Claude Code eklenti pazarıdır. Herkes kendi Claude hesabıyla kullanır.

## Kurulum

Claude Code'u açıp şunları yaz (`<github-kullanici>/<depo>` yerine bu deponun adresi):

```
/plugin marketplace add <github-kullanici>/<depo>
EKLENTILER
```

İstemediğin eklentiyi kurma; her eklenti modele giden metni büyütür.

## MCP anahtarları

MCP eklentisindeki anahtarlar boş bırakıldı. Kullanacağın sunucunun değişkenini kendi anahtarınla tanımla
(liste RAPOR.txt'de). Windows'ta: `setx DEGISKEN_ADI "anahtarin"` ve Claude Code'u yeniden aç.

## Diğer eklentiler

Paketi hazırlayanın kurduğu başka eklentiler EKLENTILER.md'de, kendi kaynaklarından kurulur.
"""


def main():
    cikis = sys.argv[1] if len(sys.argv) > 1 else os.path.join(EV, "Desktop", "claude-kurulum-paketi")
    if os.path.exists(cikis):
        shutil.rmtree(cikis)
    os.makedirs(os.path.join(cikis, ".claude-plugin"))
    rapor = {"gizli": [], "buyuk": [], "lisanssiz": [], "mcp_degisken": [], "eklenen": []}
    pazar_eklentileri = []

    skills = os.path.join(KAYNAK, "skills")
    if os.path.isdir(skills):
        yol = eklenti_yaz(cikis, "%s-skilller" % SAHIP.lower(), "Skill koleksiyonu")
        for ad in sorted(os.listdir(skills)):
            k = os.path.join(skills, ad)
            if os.path.isdir(k) and os.path.exists(os.path.join(k, "SKILL.md")):
                hedef = os.path.join(yol, "skills", ad)
                klasor_kopyala(k, hedef, rapor)
                if not os.path.exists(os.path.join(hedef, "SKILL.md")):
                    shutil.rmtree(hedef, ignore_errors=True)  # ana dosyası atlandıysa skill'i hiç koyma
                    continue
                rapor["eklenen"].append("skill: " + ad)
                if not lisans_var(k):
                    rapor["lisanssiz"].append(ad)
        pazar_eklentileri.append(("%s-skilller" % SAHIP.lower(), "Skill koleksiyonu"))

    for tur, aciklama in (("agents", "Alt ajanlar"), ("commands", "Eğik çizgi komutları")):
        k = os.path.join(KAYNAK, tur)
        if os.path.isdir(k) and os.listdir(k):
            ad = "%s-%s" % (SAHIP.lower(), "ajanlar" if tur == "agents" else "komutlar")
            yol = eklenti_yaz(cikis, ad, aciklama)
            klasor_kopyala(k, os.path.join(yol, tur), rapor)
            rapor["eklenen"].append("%s: %d dosya" % (tur, len(os.listdir(k))))
            pazar_eklentileri.append((ad, aciklama))

    claude_json = os.path.join(EV, ".claude.json")
    if os.path.exists(claude_json):
        try:
            sunucular = json.load(open(claude_json, encoding="utf-8")).get("mcpServers", {})
        except (OSError, ValueError):
            sunucular = {}
        temiz = mcp_temizle(sunucular, rapor)
        if temiz:
            ad = "%s-mcp" % SAHIP.lower()
            yol = eklenti_yaz(cikis, ad, "MCP sunucu ayarları (anahtarlar kişiye özel)")
            with open(os.path.join(yol, ".mcp.json"), "w", encoding="utf-8") as f:
                json.dump({"mcpServers": temiz}, f, ensure_ascii=False, indent=2)
            rapor["eklenen"].append("MCP: %d sunucu" % len(temiz))
            pazar_eklentileri.append((ad, "MCP sunucu ayarları"))

    with open(os.path.join(cikis, ".claude-plugin", "marketplace.json"), "w", encoding="utf-8") as f:
        json.dump({"name": "%s-kurulum" % SAHIP.lower(), "owner": {"name": SAHIP},
                   "plugins": [{"name": ad, "source": "./plugins/" + ad, "description": ac}
                               for ad, ac in pazar_eklentileri]}, f, ensure_ascii=False, indent=2)

    pazarlar, eklentiler = kurulu_eklentiler()
    with open(os.path.join(cikis, "EKLENTILER.md"), "w", encoding="utf-8") as f:
        f.write("# Kurulu eklentiler (kendi kaynaklarından kurulur)\n\n```\n")
        for ad, kaynak in sorted(pazarlar.items()):
            f.write("/plugin marketplace add %s\n" % kaynak)
        for e in eklentiler:
            f.write("/plugin install %s\n" % e)
        f.write("```\n")

    with open(os.path.join(cikis, "README.md"), "w", encoding="utf-8") as f:
        f.write(KURULUM_REHBERI.replace("PAZAR", "%s-kurulum" % SAHIP.lower())
                .replace("EKLENTILER", "\n".join("/plugin install %s@%s-kurulum" % (ad, SAHIP.lower())
                                                 for ad, _ in pazar_eklentileri)))

    with open(os.path.join(cikis, "RAPOR.txt"), "w", encoding="utf-8") as f:
        f.write("PAKETLEME RAPORU - GitHub'a gondermeden once oku\n\n")
        for baslik, anahtar in (("EKLENENLER", "eklenen"),
                                ("GIZLI BILGI SUPHESIYLE ALINMAYANLAR (kontrol et)", "gizli"),
                                ("5 MB'DAN BUYUK OLDUGU ICIN ALINMAYANLAR", "buyuk"),
                                ("LISANS DOSYASI BULUNAMAYAN SKILLLER (paylasmadan once kaynagina bak)", "lisanssiz"),
                                ("ARKADASLARIN TANIMLAMASI GEREKEN MCP DEGISKENLERI", "mcp_degisken")):
            f.write("== %s (%d)\n" % (baslik, len(rapor[anahtar])))
            for satir in rapor[anahtar]:
                f.write("  " + satir + "\n")
            f.write("\n")
    print("Paket hazir:", cikis)
    print("Eklenen:", len(rapor["eklenen"]), " Gizli suphesiyle alinmayan:", len(rapor["gizli"]),
          " Lisanssiz skill:", len(rapor["lisanssiz"]))
    print("Simdi RAPOR.txt dosyasini oku.")


if __name__ == "__main__":
    main()
