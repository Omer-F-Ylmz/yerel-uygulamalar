# Ben 10: Battle Ready

Cartoon Network'ün 2006 tarihli oyunu (geliştirici This Is Pop). **Flash değil, Shockwave (Adobe Director)**
oyunu: dosyası `game.dcr`. Bu yüzden Ruffle gibi Flash emülatörleri açamıyor; Shockwave Player 2019'da
kapandı ve tarayıcılar artık eklenti çalıştırmıyor.

[Flashpoint Archive](https://flashpointarchive.org/) bu oyunu koruma altına almış ve "Oynanabilir" olarak
işaretlemiş (Flashpoint kimliği `dbb21635-b0d5-78d9-a749-c4778a07e698`). Oyunun asıl sunucusundaki
dosyaları, eski Shockwave 10.1 oynatıcısıyla ve sahte bir yerel sunucu üzerinden çalıştırıyor; yani oyun
tamamen bilgisayarında çalışıyor.

## Kurulum (bir kez)

`ben10\kur.bat`:
1. Flashpoint Infinity 14.0.3'ü indirir (1.1 GB) ve `%USERPROFILE%\Flashpoint` klasörüne açar (~4 GB).
   Shockwave 10.1 oynatıcısı pakette hazır geliyor.
2. [CLIFp](https://github.com/oblivioncth/CLIFp)'yi (Flashpoint oyunlarını tek komutla açan araç) ekler.
3. Flashpoint'i bir kez kendi penceresiyle açar: liste yüklenince pencereyi kapat.

Gerekenler: Windows 10/11, Visual C++ 2015 x86 ve .NET Framework 4.7 (çoğu bilgisayarda zaten var).
Antivirüs uyarı verirse Flashpoint klasörünü izinli listesine ekle.

## Oynamak

`ben10\oyna.bat`. İlk seferde oyunun dosyası Flashpoint arşivinden indirilir, sonra internetsiz açılır.
