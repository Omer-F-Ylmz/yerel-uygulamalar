# İnceleme notları

## Oyun
- Streetball Hero - 2017 Finals MVP, SeaStar Game, paket `com.seastar.gpplay.streetball`
- Sürüm 1.1.8 (`apk/com.seastar.gpplay.streetball.apk`), OBB: `main.31.com.seastar.gpplay.streetball.obb`

## Teknik yapı
- Unity (Mono) + uLua. C# kabuk `Assembly-CSharp.dll`, oyun mantığı Lua betiklerinde.
- Lua betikleri OBB içinde `assets/Lua/` altında (2278 dosya). Şifre: her bayt XOR 0xFF.
  Çözmek için: `python araclar/lua_coz.py <assets/Lua> <cikis>`
- Açılışta CDN'den kaynak güncellemesi kontrolü var (`PanUpdateRescources`, `PanCheckPersistantResources`).

## Ağ
- HTTP: `http://{host}:{port}/login`, `/get_user_info`, `/client`, `/change_team`, `/op_bag`,
  `/player_advance`, `/player_break`, `/player_dress_equip`, `/player_skill_uplevel`, `/gm`, `/gm_tool`
- TCP: `SocketClientNew` / `LuaTcpManager`, paketler Lua tarafında `SplitPackage` ile çözülüyor.
- **Asıl kullanılan istek biçimi** (yerel sunucu bunu karşılıyor, bkz. `sunucu/cekirdek.py`): HTTP POST form
  verisi `session_id, proto, proto_sub, param (JSON), sign`; `sign = md5(veri + "!1AQaq#3")`. Örnek: `7/705`
  = proto 7, proto_sub 705 (maç başlat). İstemci cevabı yalnızca metinde `"result":0` geçiyorsa başarılı
  sayar (sıkışık JSON, `null` yok); hata `{"result":-1,"error":"HintXxx"}`. İşleyiciler `sunucu/sunucu.py`
  ve `sunucu/*.py` içindeki `kur(yon, durum)` fonksiyonlarında `yon.proto(ana, alt)` ile kaydediliyor.
- İstemcideki Lua hataları `999/1` isteğiyle sunucuya gelir, `sunucu/kayit/istemci_hatalari.txt`'ye yazılır.
- Kodda geçen eski adresler: `139.224.32.217`, `192.168.80.11`, `192.168.88.15`, `localhost:6688`.

## OBB doğrulaması ve yama yöntemi
- Unity (UnityPlayer.a(String)) OBB'nin son 65558 baytının MD5'ini hesaplar ve APK'daki
  `settings.xml` içindeki kimlikle (`3ba6210fc2cdd614a85041cc833fd97e`) karşılaştırır.
  OBB değişirse reddedilir ve StreamingAssets APK'dan okunmaya çalışılır (oyun logoda kalır).
- Bu yüzden OBB orijinal bırakılır. Yamalı Lua'lar oyunun üzerine yazma klasörüne konur:
  `/sdcard/Android/data/com.seastar.gpplay.streetball/files!/assets/Lua/` (LuaScriptMgr.LoaderSuperStar
  önce buraya bakar, dosyalar yine XOR 0xFF şifreli olmalı). `deleteDownloadFile` bu klasöre dokunmaz.

## Maç yükleme donması (%0/%1'de kalma) - sebebi ve çözümü
- `MatchLoader.InitBattleTeamInfo` her oyuncuya `99999` numaralı "ortak beceri"yi ekliyor; OBB'deki
  SkillInfo tablosunda (conf_qte.assetbundle, 699 beceri) bu beceri yok (canlı sunucunun güncel tablosunda
  vardı). C# `PlayerSkillData` tabloda olmayan beceride null'a erişip çöküyor.
- Çökme Lua -> C# (`initPlayerInfo`) -> Lua iç içe çağrının ortasında olduğundan hata mesajı çıkmıyor,
  oyun tamamen donuyor. Genel kural: C#'tan çağrılan Lua'da ya da Lua'dan çağrılan C#'ta çıkan her hata
  logcat'e düşmeden donmaya dönüşür; bu yüzden iz noktaları (999/2, kayit/mac_izi.txt) kullanıldı.
- Çözüm (araclar/obb_yamala.py): tabloda olmayan beceriler listeden çıkarılır; PlayerAttribute'teki
  iç içe çağrı xpcall ile sarıldı. Bütün Lua dosyaları yama klasörüne kopyalanıyor (baslat.bat).


## Maç yüklendi ama başlamıyor (başlangıç ekranında kalma) - sebebi ve çözümü
- Yükleme bitince C# `enterStart()` sahadaki her oyuncu için beceri betiklerini (`Skill_QTE/...`) çağırır.
  OBB'deki BuffInformation tablosu betiklerden eski: betiklerin kullandığı 36 buff id'si (1147-1176, 2036,
  2097-2100, 3006) tabloda yok. Örnek: `Skill_Passive_DiWangDeWeiShi:22: attempt to index local 'buff1'`.
  Hata `enterStart`'ı `setState(Gaming)`'e gelmeden kesiyor, maç hiç başlamıyor.
- Çözüm (araclar/obb_yamala.py, `betik_koruma`): Skill_QTE/, Skill/, Battle/ altındaki her modülün bütün
  fonksiyonları pcall ile sarılır. Hata veren beceri atlanır (nil döner), hata bir kez 999/2 ile sunucuya
  "BETIK HATA modül.fonksiyon: mesaj" olarak bildirilir (kayit/mac_izi.txt). 16 betik XOR dışında
  şifreli (Skill_Active_HanDi vb.), onlar olduğu gibi bırakılır.
- Tablo tamamlama (araclar/conf_yamala.py): 36 eksik buff BuffInformation + BuffEffect tablolarına eklenir ve
  yamalı paket `sunucu/veri/conf_qte.assetbundle` olarak depoda durur. Oyun açılışta `Conf/<dil>/conf_time.txt`
  md5'ini cihazdaki `files!/assets/Conf/<dil>/conf_qte.assetbundle` ile karşılaştırır; uyuşmazsa paketi
  `/res/ANDROID/Conf/<dil>/conf_qte.assetbundle` adresinden indirip kaydeder (ConfManager.loadConfTime/loadConf).
  Sunucu bu adreste yamalı paketi, conf_time.txt'de onun md5'ini verir. OBB'ye dokunulmaz.
  Lua tarafındaki kopya (BuffInformation_LuaTab) LuaConfManager.lua yamasıyla tamamlanır (buff_lua_eki).
- Paket biçimi: UnityWeb v3 (Unity 4.6.9f1), lzma_alone (512 KB sözlük, boyut yazılı), tek SerializedFile biçim 9,
  little-endian, nesneler 8 hizalı; tip ağacı olmadığı için UnityPy okuyamıyor, ham bayt işleniyor.
  Kayıt düzeni BuffInformation: int×3, int[] (sayı+elemanlar), 5 metin (uzunluk+bayt, 4 hizalı), int×3, 3 bool
  (her biri 4 bayt). BuffEffect: int, int, 4 double. Yeniden üretmek: `python araclar/conf_yamala.py main.obb`.
- pcall koruması yine de durur: eksik başka bir şey çıkarsa beceri atlanır ve `BETIK HATA` izi düşer.
