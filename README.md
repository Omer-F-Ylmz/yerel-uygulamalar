# Streetball Hero · yerel sunucu

Kapanmış Streetball Hero (2017 Finals MVP) oyununu kendi bilgisayarında çalışan bir sunucuyla, tek başına oynamak için.
Her şey açık ve sınırsız başlar; yaptığın her şey bilgisayarına kaydedilir. Tarayıcıdan açılan bir yönetim paneli var.

## Gerekenler

- **Python 3** — [python.org](https://www.python.org/downloads/). Kurarken **"Add python.exe to PATH"** kutusunu işaretle.
- **LDPlayer 9** (Android emülatörü) — [ldplayer.net](https://www.ldplayer.net/). Başka emülatör de olur ama LDPlayer önerilir.
  LDPlayer'da: *Ayarlar → Diğer ayarlar → ADB hata ayıklama → "Yerel bağlantıyı aç"*.
- `apk` klasöründe 1.1.8 APK'sı ve OBB (zaten var: XAPK'dan çıkardığın dosyalar).

## Kurulum (bir kez)

1. `guncelle.bat` → en güncel sunucu kodunu çeker.
2. LDPlayer'ı aç, ana ekran gelsin.
3. `kur.bat` → OBB'yi yamalar, oyunu emülatöre kurar, yamalı OBB'yi yerine kopyalar.

## Oynamak (her seferinde)

1. LDPlayer'ı aç.
2. `baslat.bat` → emülatörü sunucuya bağlar, sunucuyu başlatır, paneli tarayıcıda açar.
   **Bu pencere açık kaldığı sürece sunucu çalışır.**
3. Emülatörde Streetball Hero'yu aç. Giriş ekranında istediğin bir hesap adı yaz ve gir.

## Yönetim paneli

`http://localhost:8881/panel` (sunucu açıkken).

- Altın, elmas, enerji, VIP, takım seviyesi ve adı
- Tüm oyuncuları açma / tek tek ya da hepsini fulleme (seviye, yıldız, kalite, beceri, antrenman)
- Kadro seçimi, çanta eşyaları, tüm bölümleri 3 yıldız yapma
- Kaydı yedek olarak indirme, sıfırlama

Oyun verileri girişte yüklendiği için paneldeki değişiklikleri oyunda görmek için **oyundan çıkıp tekrar giriş yap**.

## Kayıt

Tüm ilerleme `sunucu/kayit/kayit.json` dosyasında. Bu dosyayı kopyalayarak yedek alabilirsin.
Silersen her şey baştan (ama yine her şey açık ve sınırsız) başlar.

## Sorun giderme

| Belirti | Çözüm |
| --- | --- |
| `kur.bat` "adb bulunamadı" diyor | LDPlayer kurulu mu? Değilse [platform-tools](https://developer.android.com/tools/releases/platform-tools)'u indir, `platform-tools` klasörünü bu klasöre koy. |
| "Açık bir emülatör bulunamadı" | Emülatör açık ve ADB yerel bağlantısı açık olmalı (yukarıdaki ayar). |
| Oyun açılışta "ağ" hatası verip bekliyor | `baslat.bat` penceresi açık mı? Emülatörü sonradan açtıysan `baslat.bat`'ı kapatıp yeniden çalıştır. |
| Başka bir sorun | `baslat.bat` penceresindeki son satırların ekran görüntüsünü gönder. |

## Klasörler

| Klasör | İçerik |
| --- | --- |
| `sunucu/` | Yerel sunucu (Python, ek paket gerekmez), panel, kayıt |
| `araclar/` | OBB yama, Lua çözme, veri çıkarma, emülatör kurulum araçları |
| `apk/` | Orijinal APK ve OBB (OBB Git'e girmez) |
| `NOTLAR.md` | Tersine mühendislik notları |
