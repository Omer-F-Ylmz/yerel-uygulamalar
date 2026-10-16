# Proje kuralları

Kapanmış Streetball Hero (Android) oyununu yerel sunucuyla oynatan proje. Genel bakış: README.md, NOTLAR.md.

## Büyük dosyaları bütün olarak okuma
Bu dosyalar bağlam penceresini tek seferde doldurur. Sadece `grep`, `head` ya da küçük bir Python
betiğiyle aradığın parçayı çıkar:
- `sunucu/veri/*.json` (mac_verisi 700 KB, ceviri_tr 670 KB, diğerleri 100-170 KB)
- `teshis.txt` (emülatör kaydı, 500 KB): önce `grep -n -i "error\|exception\|lua" teshis.txt | head -50`
- `sunucu/kayit/` altındaki kayıtlar, çözülmüş Lua klasörü ve OBB/APK dosyaları
Kod dosyalarını (sunucu/*.py) okuyabilirsin; 400 satırdan uzunsa parça parça oku.

## Çalışma şekli
- Tek başına çalış: alt ajan, Workflow ya da paralel ajan başlatma.
- Kullanıcı açıkça istemedikçe `git push` yapma. OBB dosyasını asla değiştirme.
- Değişiklikten sonra testleri çalıştır: `python -m unittest discover -s sunucu/testler`

## Her cevabın sonunda RAPOR
Her iş bitiminde (yarım kalsa da) şu başlıkla bitir:

RAPOR
- Yaptıklarım: (madde madde)
- Değişen dosyalar: (yoksa "yok")
- Sonuç / bulgular:
- Sıradaki adım önerim:
