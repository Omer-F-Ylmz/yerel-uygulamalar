"""MCP kapısı: bütün MCP sunucularını tek bir sunucunun arkasında toplar.

Claude Code, Anthropic dışı bir adrese (Ollama, OpenRouter) bağlanınca araç aramayı kapatıp
her MCP aracının tanımını her mesajda modele gönderiyor; çok sunucu olunca istem modele sığmıyor
("Prompt is too long"). Bu kapı modele yalnızca iki araç gösterir:
  mcp_ara   -> sunuculardaki araçları arar, bulduklarının parametrelerini verir
  mcp_cagir -> bulunan aracı asıl sunucusunda çalıştırır
Hiçbir sunucu kapatılmaz; hepsi ilk kullanıldığında bağlanır.

  python mcp_kapi.py <ayar.json>            -> Claude Code'un başlattığı MCP sunucusu (stdio)
  python mcp_kapi.py <ayar.json> --dene     -> sunuculara bağlanıp araç sayılarını yazar

ayar.json, Claude Code'daki gibi {"mcpServers": {...}} biçimindedir (stdio, http, sse).
Yalnızca Python standart kütüphanesini kullanır.
"""
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request

PROTOKOL = "2025-06-18"
BAGLANTI_SURESI = 90  # npx ilk çalıştırmada paketi indirebiliyor
CAGRI_SURESI = 600
ISTEMCI = {"name": "mcp-kapi", "version": "1.0"}


def log(*a):
    print("[mcp-kapi]", *a, file=sys.stderr, flush=True)


def degisken_ac(deger):
    """Claude Code'daki gibi ${AD} ve ${AD:-varsayilan} açar."""
    if isinstance(deger, str):
        return re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}",
                      lambda m: os.environ.get(m.group(1), m.group(2) or ""), deger)
    if isinstance(deger, list):
        return [degisken_ac(x) for x in deger]
    if isinstance(deger, dict):
        return {k: degisken_ac(v) for k, v in deger.items()}
    return deger


class Istemci:
    """Bir alt sunucuyla JSON-RPC konuşan ortak taban; taşıma alt sınıflarda."""

    def __init__(self, ad, ayar):
        self.ad, self.ayar = ad, degisken_ac(ayar)
        self.sayac = 0
        self.kilit = threading.Lock()
        self.bekleyen = {}
        self.araclar = None

    def _yeni_id(self):
        with self.kilit:
            self.sayac += 1
            return self.sayac

    def _gelen(self, mesaj):
        """Alt sunucudan gelen mesaj: yanıtsa bekleyene ilet, istekse cevapla."""
        if "id" in mesaj and ("result" in mesaj or "error" in mesaj):
            k = self.bekleyen.get(mesaj["id"])
            if k:
                k.put(mesaj)
        elif "id" in mesaj and "method" in mesaj:
            if mesaj["method"] == "roots/list":
                self._gonder({"jsonrpc": "2.0", "id": mesaj["id"], "result": {"roots": []}})
            elif mesaj["method"] == "ping":
                self._gonder({"jsonrpc": "2.0", "id": mesaj["id"], "result": {}})
            else:
                self._gonder({"jsonrpc": "2.0", "id": mesaj["id"],
                              "error": {"code": -32601, "message": "desteklenmiyor"}})

    def istek(self, yontem, param=None, sure=CAGRI_SURESI):
        no = self._yeni_id()
        kuyruk = queue.Queue()
        self.bekleyen[no] = kuyruk
        try:
            self._gonder({"jsonrpc": "2.0", "id": no, "method": yontem, "params": param or {}})
            try:
                yanit = kuyruk.get(timeout=sure)
            except queue.Empty:
                raise RuntimeError("%s: %s %d sn icinde yanit vermedi" % (self.ad, yontem, sure))
        finally:
            self.bekleyen.pop(no, None)
        if "error" in yanit:
            raise RuntimeError("%s: %s" % (self.ad, yanit["error"].get("message", yanit["error"])))
        return yanit["result"]

    def bildir(self, yontem, param=None):
        self._gonder({"jsonrpc": "2.0", "method": yontem, "params": param or {}})

    def baslat(self):
        self._ac()
        self.istek("initialize", {"protocolVersion": PROTOKOL, "capabilities": {"roots": {}},
                                  "clientInfo": ISTEMCI}, BAGLANTI_SURESI)
        self.bildir("notifications/initialized")
        araclar, imlec = [], None
        while True:
            sonuc = self.istek("tools/list", {"cursor": imlec} if imlec else {}, BAGLANTI_SURESI)
            araclar += sonuc.get("tools", [])
            imlec = sonuc.get("nextCursor")
            if not imlec:
                break
        self.araclar = araclar

    def kapat(self):
        pass


class StdioIstemci(Istemci):
    def _ac(self):
        komut = self.ayar["command"]
        komut = shutil.which(komut) or komut  # Windows'ta npx -> npx.cmd
        ortam = dict(os.environ)
        ortam.update({k: str(v) for k, v in (self.ayar.get("env") or {}).items()})
        self.surec = subprocess.Popen(
            [komut] + [str(x) for x in self.ayar.get("args", [])], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=ortam, cwd=self.ayar.get("cwd"),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.yazma = threading.Lock()
        threading.Thread(target=self._oku, daemon=True).start()

    def _oku(self):
        for satir in self.surec.stdout:
            try:
                self._gelen(json.loads(satir))
            except ValueError:
                continue  # sunucunun stdout'a yazdığı düz metin
        for k in list(self.bekleyen.values()):
            k.put({"error": {"message": "sunucu kapandi"}})

    def _gonder(self, mesaj):
        with self.yazma:
            self.surec.stdin.write((json.dumps(mesaj) + "\n").encode("utf-8"))
            self.surec.stdin.flush()

    def kapat(self):
        try:
            self.surec.kill()
        except Exception:
            pass


def sse_olaylari(yanit):
    """text/event-stream gövdesinden (olay, veri) çiftleri üretir."""
    olay, veri = "message", []
    for ham in yanit:
        satir = ham.decode("utf-8", "replace").rstrip("\r\n")
        if not satir:
            if veri:
                yield olay, "\n".join(veri)
            olay, veri = "message", []
        elif satir.startswith("event:"):
            olay = satir[6:].strip()
        elif satir.startswith("data:"):
            veri.append(satir[5:].lstrip())
    if veri:
        yield olay, "\n".join(veri)


class HttpIstemci(Istemci):
    """Streamable HTTP taşıması: her mesaj bir POST, yanıt JSON ya da SSE."""

    def _ac(self):
        self.oturum = None
        self.surum = None

    def _basliklar(self):
        b = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        b.update(self.ayar.get("headers") or {})
        if self.oturum:
            b["Mcp-Session-Id"] = self.oturum
        if self.surum:
            b["MCP-Protocol-Version"] = self.surum
        return b

    def _gonder(self, mesaj):
        if "id" in mesaj and "method" in mesaj:  # istek: yanıtı uzun sürebilir, ayrı iş parçacığında
            threading.Thread(target=self._post, args=(mesaj,), daemon=True).start()
        else:  # bildirim/yanıt: sıralı kalsın diye hemen gönder
            self._post(mesaj)

    def _post(self, mesaj):
        istek = urllib.request.Request(self.ayar["url"], data=json.dumps(mesaj).encode("utf-8"),
                                       headers=self._basliklar(), method="POST")
        try:
            with urllib.request.urlopen(istek, timeout=CAGRI_SURESI) as yanit:
                self.oturum = yanit.headers.get("Mcp-Session-Id") or self.oturum
                tur = yanit.headers.get("Content-Type", "")
                if "text/event-stream" in tur:
                    for _, veri in sse_olaylari(yanit):
                        try:
                            self._gelen(json.loads(veri))
                        except ValueError:
                            pass
                else:
                    govde = yanit.read()
                    if govde.strip():
                        cevap = json.loads(govde)
                        for m in cevap if isinstance(cevap, list) else [cevap]:
                            self._gelen(m)
        except Exception as e:
            if "id" in mesaj and "method" in mesaj:
                k = self.bekleyen.get(mesaj["id"])
                if k:
                    k.put({"error": {"message": "baglanti hatasi: %s" % e}})

    def baslat(self):
        super().baslat()
        self.surum = PROTOKOL


class SseIstemci(Istemci):
    """Eski SSE taşıması: GET ile olay akışı, mesajlar akışın verdiği adrese POST."""

    def _ac(self):
        self.adres = queue.Queue()
        threading.Thread(target=self._dinle, daemon=True).start()
        try:
            self.gonderme = self.adres.get(timeout=BAGLANTI_SURESI)
        except queue.Empty:
            raise RuntimeError("%s: SSE baglantisi kurulamadi" % self.ad)

    def _dinle(self):
        b = {"Accept": "text/event-stream"}
        b.update(self.ayar.get("headers") or {})
        try:
            with urllib.request.urlopen(urllib.request.Request(self.ayar["url"], headers=b)) as yanit:
                for olay, veri in sse_olaylari(yanit):
                    if olay == "endpoint":
                        self.adres.put(urllib.parse.urljoin(self.ayar["url"], veri))
                    else:
                        try:
                            self._gelen(json.loads(veri))
                        except ValueError:
                            pass
        except Exception as e:
            log(self.ad, "SSE koptu:", e)
        for k in list(self.bekleyen.values()):
            k.put({"error": {"message": "SSE baglantisi koptu"}})

    def _gonder(self, mesaj):
        b = {"Content-Type": "application/json"}
        b.update(self.ayar.get("headers") or {})
        istek = urllib.request.Request(self.gonderme, data=json.dumps(mesaj).encode("utf-8"),
                                       headers=b, method="POST")
        urllib.request.urlopen(istek, timeout=60).read()


def istemci_yap(ad, ayar):
    tur = ayar.get("type") or ("stdio" if "command" in ayar else "http")
    return {"stdio": StdioIstemci, "sse": SseIstemci}.get(tur, HttpIstemci)(ad, ayar)


class Kapi:
    def __init__(self, ayar_yolu):
        self.ayar_yolu = ayar_yolu
        with open(ayar_yolu, encoding="utf-8") as f:
            self.sunucular = json.load(f).get("mcpServers", {})
        self.onbellek_yolu = os.path.splitext(ayar_yolu)[0] + "_araclar.json"
        try:
            with open(self.onbellek_yolu, encoding="utf-8") as f:
                self.onbellek = json.load(f)
        except (OSError, ValueError):
            self.onbellek = {}
        self.istemciler, self.hatalar = {}, {}
        self.kilitler = {ad: threading.Lock() for ad in self.sunucular}

    def istemci(self, ad):
        """Sunucuya ilk istendiğinde bağlanır; bağlantı açık kalır."""
        if ad not in self.sunucular:
            raise RuntimeError("'%s' adinda sunucu yok. Var olanlar: %s" % (ad, ", ".join(self.sunucular)))
        with self.kilitler[ad]:
            if ad not in self.istemciler:
                i = istemci_yap(ad, self.sunucular[ad])
                try:
                    i.baslat()
                except Exception as e:
                    i.kapat()
                    self.hatalar[ad] = str(e)
                    raise
                self.hatalar.pop(ad, None)
                self.istemciler[ad] = i
                self.onbellek[ad] = [a["name"] for a in i.araclar]
                self._onbellek_yaz()
            return self.istemciler[ad]

    def _onbellek_yaz(self):
        try:
            with open(self.onbellek_yolu, "w", encoding="utf-8") as f:
                json.dump(self.onbellek, f, ensure_ascii=False)
        except OSError:
            pass

    def hepsine_baglan(self, adlar):
        is_parcaciklari = [threading.Thread(target=self._sessiz_baglan, args=(ad,), daemon=True) for ad in adlar]
        for t in is_parcaciklari:
            t.start()
        for t in is_parcaciklari:
            t.join(BAGLANTI_SURESI + 10)

    def _sessiz_baglan(self, ad):
        try:
            self.istemci(ad)
        except Exception as e:
            log(ad, "baglanamadi:", e)

    def ara(self, sorgu="", sunucu=None, adet=8):
        adlar = [sunucu] if sunucu else list(self.sunucular)
        if sunucu and sunucu not in self.sunucular:
            return "No server named '%s'. Servers: %s" % (sunucu, ", ".join(self.sunucular))
        self.hepsine_baglan([a for a in adlar if a not in self.istemciler])
        kelimeler = [k for k in re.split(r"[\s_\-./]+", sorgu.lower()) if k]
        adaylar = []
        for ad in adlar:
            for arac in (self.istemciler[ad].araclar if ad in self.istemciler else []):
                isim, aciklama = arac["name"].lower(), (arac.get("description") or "").lower()
                puan = sum(3 * (k in isim) + (k in aciklama) + 2 * (k in ad.lower()) for k in kelimeler)
                if puan or not kelimeler:
                    adaylar.append((puan, ad, arac))
        adaylar.sort(key=lambda x: -x[0])
        if not adaylar:
            return "No matching tools." + self._hata_ozeti(adlar)
        satirlar = ["%d matching tools (showing %d). Call one with mcp_cagir(sunucu, arac, argumanlar)."
                    % (len(adaylar), min(adet, len(adaylar)))]
        for _, ad, arac in adaylar[:adet]:
            satirlar.append("\n## sunucu=%s arac=%s\n%s\nparameters: %s" % (
                ad, arac["name"], (arac.get("description") or "").strip()[:1500],
                json.dumps(arac.get("inputSchema", {}), ensure_ascii=False)))
        if len(adaylar) > adet:
            satirlar.append("\nOther matches: " + ", ".join(
                "%s/%s" % (ad, a["name"]) for _, ad, a in adaylar[adet:adet + 40]))
        return "\n".join(satirlar) + self._hata_ozeti(adlar)

    def _hata_ozeti(self, adlar):
        h = ["%s: %s" % (a, self.hatalar[a]) for a in adlar if a in self.hatalar]
        return ("\n\nServers that failed to connect:\n" + "\n".join(h)) if h else ""

    def cagir(self, sunucu, arac, argumanlar):
        return self.istemci(sunucu).istek("tools/call", {"name": arac, "arguments": argumanlar or {}})

    def ozet(self):
        """Modelin aracın açıklamasında göreceği sunucu/araç adları listesi."""
        parcalar = []
        for ad in self.sunucular:
            adlar = self.onbellek.get(ad)
            parcalar.append("%s (%s)" % (ad, ", ".join(adlar)[:400] if adlar else "tools not listed yet"))
        metin = "; ".join(parcalar)
        return metin[:6000]

    def araclar(self):
        return [
            {"name": "mcp_ara",
             "description": "Search the tools of the user's MCP servers (they are not loaded directly to save "
                            "context). Returns matching tools with their parameter schemas; then run one with "
                            "mcp_cagir. Use an empty query with 'sunucu' to list one server's tools. "
                            "Servers and their tools: " + self.ozet(),
             "inputSchema": {"type": "object", "properties": {
                 "sorgu": {"type": "string", "description": "Keywords, e.g. 'create issue' or a tool name"},
                 "sunucu": {"type": "string", "description": "Optional: search only this server"}},
                 "required": ["sorgu"]}},
            {"name": "mcp_cagir",
             "description": "Run a tool of one of the user's MCP servers. Find the tool and its parameters "
                            "with mcp_ara first.",
             "inputSchema": {"type": "object", "properties": {
                 "sunucu": {"type": "string", "description": "Server name"},
                 "arac": {"type": "string", "description": "Tool name exactly as mcp_ara returned it"},
                 "argumanlar": {"type": "object", "description": "Tool arguments matching its schema"}},
                 "required": ["sunucu", "arac"]}},
        ]

    def arac_calistir(self, ad, arg):
        if ad == "mcp_ara":
            return {"content": [{"type": "text", "text": self.ara(arg.get("sorgu", ""), arg.get("sunucu") or None)}]}
        if ad == "mcp_cagir":
            argumanlar = arg.get("argumanlar") or {}
            if isinstance(argumanlar, str):  # bazı modeller nesneyi metin olarak yolluyor
                argumanlar = json.loads(argumanlar or "{}")
            sonuc = self.cagir(arg["sunucu"], arg["arac"], argumanlar)
            return {"content": sonuc.get("content", []), "isError": bool(sonuc.get("isError"))}
        raise RuntimeError("bilinmeyen arac: %s" % ad)

    def kapat(self):
        for i in self.istemciler.values():
            i.kapat()


def sunucu_dongusu(kapi):
    yazma = threading.Lock()

    def yaz(mesaj):
        with yazma:
            sys.stdout.write(json.dumps(mesaj, ensure_ascii=False) + "\n")
            sys.stdout.flush()

    def isle(mesaj):
        yontem, no = mesaj.get("method"), mesaj.get("id")
        try:
            if yontem == "initialize":
                sonuc = {"protocolVersion": mesaj.get("params", {}).get("protocolVersion", PROTOKOL),
                         "capabilities": {"tools": {}}, "serverInfo": ISTEMCI,
                         "instructions": "The user's MCP servers are reachable through mcp_ara (search) and "
                                         "mcp_cagir (call)."}
            elif yontem == "tools/list":
                sonuc = {"tools": kapi.araclar()}
            elif yontem == "tools/call":
                p = mesaj.get("params", {})
                try:
                    sonuc = kapi.arac_calistir(p.get("name"), p.get("arguments") or {})
                except Exception as e:
                    sonuc = {"content": [{"type": "text", "text": "Error: %s" % e}], "isError": True}
            elif yontem == "ping":
                sonuc = {}
            elif no is None:
                return  # bildirim
            else:
                yaz({"jsonrpc": "2.0", "id": no, "error": {"code": -32601, "message": "Method not found"}})
                return
            if no is not None:
                yaz({"jsonrpc": "2.0", "id": no, "result": sonuc})
        except Exception as e:
            if no is not None:
                yaz({"jsonrpc": "2.0", "id": no, "error": {"code": -32603, "message": str(e)}})

    for satir in sys.stdin:
        try:
            mesaj = json.loads(satir)
        except ValueError:
            continue
        threading.Thread(target=isle, args=(mesaj,), daemon=True).start()
    kapi.kapat()


def dene(kapi):
    print("Sunuculara baglaniliyor (ilk sefer biraz surebilir)...")
    bas = time.time()
    kapi.hepsine_baglan(list(kapi.sunucular))
    for ad in kapi.sunucular:
        if ad in kapi.istemciler:
            print("  TAMAM  %-25s %d arac" % (ad, len(kapi.istemciler[ad].araclar)))
        else:
            print("  HATA   %-25s %s" % (ad, kapi.hatalar.get(ad, "zaman asimi")))
    print("Sure: %.0f sn" % (time.time() - bas))
    kapi.kapat()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    k = Kapi(sys.argv[1])
    if "--dene" in sys.argv:
        dene(k)
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stdin.reconfigure(encoding="utf-8")
        sunucu_dongusu(k)
