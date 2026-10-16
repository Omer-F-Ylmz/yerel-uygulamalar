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
- Kodda geçen eski adresler: `139.224.32.217`, `192.168.80.11`, `192.168.88.15`, `localhost:6688`.

## OBB doğrulaması ve yama yöntemi
- Unity (UnityPlayer.a(String)) OBB'nin son 65558 baytının MD5'ini hesaplar ve APK'daki
  `settings.xml` içindeki kimlikle (`3ba6210fc2cdd614a85041cc833fd97e`) karşılaştırır.
  OBB değişirse reddedilir ve StreamingAssets APK'dan okunmaya çalışılır (oyun logoda kalır).
- Bu yüzden OBB orijinal bırakılır. Yamalı Lua'lar oyunun üzerine yazma klasörüne konur:
  `/sdcard/Android/data/com.seastar.gpplay.streetball/files!/assets/Lua/` (LuaScriptMgr.LoaderSuperStar
  önce buraya bakar, dosyalar yine XOR 0xFF şifreli olmalı). `deleteDownloadFile` bu klasöre dokunmaz.
