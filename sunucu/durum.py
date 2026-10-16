"""Oyuncunun kalıcı durumu: tek hesap, tek dosya (sunucu/kayit/kayit.json).

Her değişiklikten sonra dosyaya yazılır, böylece oyundan çıkınca hiçbir şey kaybolmaz.
Yazma önce geçici dosyaya yapılır, yarım kalmış bir kayıt eskisini bozmaz.
"""
import copy
import json
import os
import threading

KOK = os.path.dirname(os.path.abspath(__file__))
VERI = json.load(open(os.path.join(KOK, "veri", "oyun_verisi.json"), encoding="utf-8"))
SINIR = VERI["sinirlar"]
OYUNCU_VERI = {o["id"]: o for o in VERI["oyuncular"]}
ESYA_VERI = {e["id"]: e for e in VERI["esyalar"]}
KAYIT_YOLU = os.path.join(KOK, "kayit", "kayit.json")

BOL = 99999999
CANTA_TURU = {1: "s_material", 2: "s_fragment", 3: "s_equipment", 4: "s_consumables", 5: "s_card"}


def full_oyuncu():
    return {"level": SINIR["oyuncu_seviye"], "exp": 0, "break_level": SINIR["yildiz"],
            "color": SINIR["renk"], "beceri": SINIR["beceri_seviye"], "train": SINIR["antrenman"]}


def baslangic_takimi():
    """Her pozisyondan (1 pivot, 2 skorer, 3 oyun kurucu) bir oyuncu seçer."""
    secili = []
    for pos in (1, 2, 3):
        aday = next((o["id"] for o in VERI["oyuncular"] if o["pozisyon"] == pos), None)
        if aday is None:
            aday = VERI["oyuncular"][pos - 1]["id"]
        secili.append({"pos": pos, "id": aday})
    return secili


def yeni_kayit(hesap):
    return {
        "hesap": hesap,
        "uin": 10001,
        "takim": {"ad": hesap or "Streetball", "ikon": 1, "seviye": SINIR["takim_seviye"], "exp": 0},
        "gold": BOL,
        "gem": BOL,
        "star": BOL,
        "rm_ticket": 99,
        "stamina": 9999,
        "vip": 15,
        "oyuncular": {str(o["id"]): full_oyuncu() for o in VERI["oyuncular"]},
        "secili": baslangic_takimi(),
        "canta": {str(e["id"]): 999 for e in VERI["esyalar"] if e["cantada"] and e["tur"] in (1, 2, 4)},
        "amigolar": {str(a): 50 for a in VERI["amigolar"]},  # 50: CheerLeaderLevelUp/TeamPlayerLevel tavanı
        "secili_amigolar": VERI["amigolar"][:4],
        "elite": {},
        "rehber": [],
    }


class Durum:
    def __init__(self, yol=KAYIT_YOLU):
        self.yol = yol
        self.kilit = threading.RLock()
        self.veri = None
        if os.path.exists(yol):
            with open(yol, encoding="utf-8") as f:
                self.veri = json.load(f)

    def hesap_ac(self, hesap):
        with self.kilit:
            if self.veri is None:
                self.veri = yeni_kayit(hesap)
                self.kaydet()
            return self.veri

    def kaydet(self):
        with self.kilit:
            os.makedirs(os.path.dirname(self.yol), exist_ok=True)
            gecici = self.yol + ".tmp"
            with open(gecici, "w", encoding="utf-8") as f:
                json.dump(self.veri, f, ensure_ascii=False, indent=1)
            os.replace(gecici, self.yol)

    def kopya(self):
        with self.kilit:
            return copy.deepcopy(self.veri)

    def sifirla(self):
        with self.kilit:
            hesap = (self.veri or {}).get("hesap", "")
            self.veri = yeni_kayit(hesap)
            self.kaydet()
