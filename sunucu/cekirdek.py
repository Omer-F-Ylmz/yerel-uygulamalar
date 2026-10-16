"""HTTP çatısı: form ayrıştırma, imza kontrolü, cevap zarfı.

İstemci her isteği application/x-www-form-urlencoded POST olarak yollar:
  session_id, proto, proto_sub, param (JSON metni), sign
sign = md5(<sign hariç alanlar> + "!1AQaq#3"). İstemci cevabı "\"result\":0"
alt dizesini arayarak başarılı sayar, bu yüzden JSON boşluksuz yazılmalı.
"""
import hashlib
import json
import logging
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

IMZA_ANAHTARI = "!1AQaq#3"
log = logging.getLogger("sunucu")


def json_yaz(nesne):
    return json.dumps(nesne, separators=(",", ":"), ensure_ascii=False)


def basarili(data=None, **ust):
    zarf = {"result": 0, "data": data if data is not None else {}}
    zarf.update(ust)
    return zarf


def hata(kod="HintServerError"):
    return {"result": -1, "error": kod}


def imza_dogru(ham_govde):
    """İmzayı ham gövdeden doğrular; yalnızca kayıt için, istemci zaten umursamıyor."""
    parcalar = ham_govde.split("&")
    imza = None
    kalan = []
    for p in parcalar:
        if p.startswith("sign="):
            imza = p[5:]
        else:
            kalan.append(p)
    if imza is None:
        return False
    metin = urllib.parse.unquote_plus("&".join(kalan))
    return hashlib.md5((metin + IMZA_ANAHTARI).encode("utf-8")).hexdigest() == imza


def form_coz(ham_govde):
    alanlar = {}
    for p in ham_govde.split("&"):
        if not p:
            continue
        k, _, v = p.partition("=")
        alanlar[urllib.parse.unquote_plus(k)] = urllib.parse.unquote_plus(v)
    return alanlar


def param_coz(metin):
    if not metin:
        return {}
    try:
        return json.loads(metin)
    except ValueError:
        log.warning("param JSON değil: %r", metin[:200])
        return {}


class Ham:
    """JSON zarfı olmadan gönderilecek cevap (XML, metin, dosya)."""

    def __init__(self, govde, tur="text/plain; charset=utf-8", durum=200):
        self.govde = govde.encode("utf-8") if isinstance(govde, str) else govde
        self.tur = tur
        self.durum = durum


class Yonlendirici:
    """Yol (/login), proto/proto_sub (/client) ve ön ek (/res/...) için işleyici kaydı."""

    def __init__(self):
        self.yollar = {}
        self.protolar = {}
        self.onekler = []

    def onek(self, on):
        def kaydet(f):
            self.onekler.append((on, f))
            return f
        return kaydet

    def yol(self, ad):
        def kaydet(f):
            self.yollar[ad] = f
            return f
        return kaydet

    def proto(self, proto, sub):
        def kaydet(f):
            self.protolar[(int(proto), int(sub))] = f
            return f
        return kaydet


def http_sunucu_kur(adres, port, yonlendirici, oturum_bul):
    class Isleyici(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):
            pass

        def _cevapla(self, nesne, durum=200):
            if isinstance(nesne, Ham):
                govde, tur, durum = nesne.govde, nesne.tur, nesne.durum
            else:
                govde, tur = json_yaz(nesne).encode("utf-8"), "application/json; charset=utf-8"
            self.send_response(durum)
            self.send_header("Content-Type", tur)
            self.send_header("Content-Length", str(len(govde)))
            self.end_headers()
            self.wfile.write(govde)

        def _isle(self, ham):
            yol = urllib.parse.unquote(urllib.parse.urlsplit(self.path).path)
            for on, f in yonlendirici.onekler:
                if yol.startswith(on):
                    log.info("GET %s", yol)
                    try:
                        ek = {"govde": ham} if getattr(f, "govde_ister", False) else {}
                        return f(yol=yol[len(on):], istek=self, **ek)
                    except Exception:
                        log.exception("%s işlenirken hata", yol)
                        return Ham("", durum=500)
            yol = yol.rstrip("/") or "/"
            if "?" in self.path and not ham:
                ham = urllib.parse.urlsplit(self.path).query
            alanlar = form_coz(ham)
            oturum = oturum_bul(alanlar.get("session_id"))
            if yol == "/client":
                anahtar = (int(alanlar.get("proto") or 0), int(alanlar.get("proto_sub") or 0))
                f = yonlendirici.protolar.get(anahtar)
                etiket = "client %s/%s" % anahtar
            else:
                f = yonlendirici.yollar.get(yol)
                etiket = yol
            param = param_coz(alanlar.get("param", ""))
            if f is None:
                # Boş "başarılı" cevap bazı ekranları kilitliyor; hata cevabında istemci maskeyi kapatıp
                # kısa bir uyarı gösterir ve devam eder.
                log.warning("BILINMEYEN %s alanlar=%s", etiket, {k: v[:300] for k, v in alanlar.items()})
                return hata("HintBallTeamError")
            log.info("%s param=%s", etiket, json_yaz(param)[:300])
            try:
                return f(alanlar=alanlar, param=param, oturum=oturum, istek=self)
            except Exception:
                log.exception("%s işlenirken hata", etiket)
                return hata()

        def do_POST(self):
            uzunluk = int(self.headers.get("Content-Length") or 0)
            ham = self.rfile.read(uzunluk).decode("utf-8", "replace")
            self._cevapla(self._isle(ham))

        def do_GET(self):
            self._cevapla(self._isle(""))

    sunucu = ThreadingHTTPServer((adres, port), Isleyici)
    sunucu.daemon_threads = True
    return sunucu
