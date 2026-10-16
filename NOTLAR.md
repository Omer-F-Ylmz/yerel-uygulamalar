# İnceleme notları

## Oyun
- Streetball Hero - 2017 Finals MVP, SeaStar Game, paket `com.seastar.gpplay.streetball`
- Sürüm 1.1.8 (`apk/com.seastar.gpplay.streetball.apk`), OBB: `main.31.com.seastar.gpplay.streetball.obb`

## Teknik yapı
- Unity (Mono) + uLua. C# kabuk `Assembly-CSharp.dll`, oyun mantığı Lua betiklerinde.
- Lua betikleri `StreamingAssets/Lua/` altında, yani OBB içinde; şifreli olabilir (`ReadEncryLua`).
- Açılışta CDN'den kaynak güncellemesi kontrolü var (`PanUpdateRescources`, `PanCheckPersistantResources`).

## Ağ
- HTTP: `http://{host}:{port}/login`, `/get_user_info`, `/client`, `/change_team`, `/op_bag`,
  `/player_advance`, `/player_break`, `/player_dress_equip`, `/player_skill_uplevel`, `/gm`, `/gm_tool`
- TCP: `SocketClientNew` / `LuaTcpManager`, paketler Lua tarafında `SplitPackage` ile çözülüyor.
- Kodda geçen eski adresler: `139.224.32.217`, `192.168.80.11`, `192.168.88.15`, `localhost:6688`.
