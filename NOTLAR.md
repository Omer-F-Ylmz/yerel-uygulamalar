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

