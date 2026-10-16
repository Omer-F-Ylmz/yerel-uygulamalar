# Ollama'daki Claude Code için hazır promptlar

Bu promptları `ollama_claude.bat` ile açtığın Claude Code'a sırayla yapıştır. Proje yöneticisi sensin:
model her adımda ne yaptığını anlatacak, sen sonucu kontrol edip bir sonraki promptu vereceksin.

## Kullanım kuralları

1. **Her seferinde tek prompt.** Model işini bitirip özet verene kadar yenisini yapıştırma.
2. **Yeni iş = `/clear`.** Bir bölüm bitince `/clear` yaz, sonra sıradaki bölümün ilk promptunu ver.
   Bedava modellerin hafızası kısa, eski konuşma kafasını karıştırır.
3. **Önce plan, sonra iş.** Promptların çoğu "önce plan yap, onay bekle" diyor. Planı oku, mantıklıysa
   `devam et` yaz, değilse neyi beğenmediğini söyle.
4. **İzin sorarsa oku.** Dosya silme, `git push`, büyük indirme gibi şeylere hemen "evet" deme.
5. **Takılırsa:** en alttaki "Takıldığında" promptlarını kullan.
6. **Ultracode kapalı olsun.** Ultracode çok ajanlı çalışma modu; bedava modellerde bağlamı doldurup
   "Autocompact is thrashing" hatasına yol açıyor. Ekranın sağ altında "ultracode" yazıyorsa kapat.
7. **Model ve rapor:** Menüden en büyük bağlamlı modeli seç (1: nemotron-3-ultra). Proje klasöründeki
   CLAUDE.md modele büyük dosyaları bütün okumamasını ve her işin sonunda RAPOR yazmasını söylüyor.
8. **Model ne yaparsa yapsın `git push` yapmasın.** Sonucu beğenirsen bana "şu değişikliği yaptı" de,
   birlikte bakıp gönderelim. (Push'u yanlış dala yaparsa `guncelle.bat` karışır.)

---

## 0. Isınma: projeyi tanıt (her yeni oturumda bir kez)

```
Bu klasör, kapanmış "Streetball Hero" Android oyununu kendi bilgisayarımda yerel bir sunucuyla
oynamak için yazılmış bir proje. Hiçbir dosyayı değiştirme, sadece oku ve öğren:
- README.md ve NOTLAR.md dosyalarını oku.
- sunucu/ klasöründeki dosyaların her birinin ne işe yaradığını tek cümleyle yaz.
- araclar/ klasöründeki araçları tek cümleyle yaz.
Sonunda bana en fazla 15 satırlık bir özet ver: oyun sunucuyla nasıl konuşuyor, kayıt nerede tutuluyor,
oyuna yama nasıl gidiyor.
```

---

## 1. Streetball: maç yüklenirken %0'da donma

**Bilinen durum:** Lobi, mağaza, eşyalar, gelişim çalışıyor. Bir maça girince yükleme ekranı %0'da
kalıyor. Sunucu `7/705` (maç başlat) isteğine cevap veriyor ama oyun sonra hiçbir şey istemiyor ve
Lua hatası da düşmüyor. Şüpheliler: oyuncu başına 17-18 beceri gönderiyoruz (eğitim maçındaki örnekte
3-4 var), nitelik sayıları çok büyük, rakip id'leri.

### 1.1 Kodu tanı (değişiklik yok)

```
Görev: Streetball Hero'da maç yükleme ekranının %0'da donmasını araştıracağız. Bu adımda HİÇBİR dosyayı
değiştirme.

1. sunucu/mac.py dosyasını oku. 7/705 isteğine verilen cevabı hangi fonksiyon üretiyor? Cevabın JSON
   yapısını (anahtarlar ve iç içe yapı) madde madde çıkar.
2. sunucu/testler/test_mac.py dosyasını oku; "tutorial_data" ile karşılaştırma yapan testi bul.
3. Testleri çalıştır: python -m unittest discover -s sunucu/testler
   Sonucu bana söyle.
4. Bana şunu yaz: 7/705 cevabımız, eğitim maçı örneğinden (tutorial_data) hangi noktalarda farklı?
   (beceri sayısı, nitelik değerlerinin büyüklüğü, rakip id'leri, eksik/fazla anahtar)
```

### 1.2 Oyunun Lua kodunu çıkar

```
Oyunun istemci kodu OBB dosyasının içinde, şifreli Lua betikleri olarak duruyor. OBB aslında bir zip
dosyası; apk klasörünün içinde (alt klasörlerde de olabilir) adı "main.*.obb" ile eşleşen dosya.
İçindeki assets/Lua/ altındaki .lua dosyalarının her baytı 0xFF ile XOR'lanmış.

1. OBB'yi bul. OBB'yi ASLA değiştirme, sadece oku.
2. Küçük bir Python betiğiyle zip'in içindeki assets/Lua/ klasörünü lua_cozulmus/ klasörüne çıkar ve
   .lua dosyalarını çöz. Yardım: araclar/lua_coz.py klasör çözüyor, araclar/obb_yamala.py zipten okumayı
   gösteriyor. lua_cozulmus/ klasörünü .gitignore'a ekle (git'e girmesin).
3. Kaç dosya çıktığını ve MatchLoader.lua, MatchManager.lua dosyalarının yolunu yaz.
```

### 1.3 Yükleme ekranı neyi bekliyor?

```
lua_cozulmus/ klasöründeki Lua koduyla çalışacağız, değişiklik yapma.

1. MatchLoader.lua ve MatchManager.lua'yı oku. 7/705 cevabı geldikten sonra yükleme çubuğu (progress)
   hangi adımlarla ilerliyor? Her adımı dosya:satır ile listele.
2. %0'dan ilerlemesi için tamamlanması gereken İLK adım ne? O adım 7/705 cevabından hangi alanları
   kullanıyor (oyuncu id'si, beceri id'leri, sahne id'si, rakip takım...)?
3. Bu alanlardan herhangi biri oyunun yapılandırma tablosunda karşılığı olmayan bir id ise ne olur?
   Hata mı verir, yoksa sessizce sonsuza kadar mı bekler? Kanıtını kod satırıyla göster.
4. Sonunda en olası 3 sebebi, kanıtlarıyla, olasılık sırasıyla yaz.
```

### 1.4 Düzelt (önce plan)

```
1.3'te bulduğun en olası sebebi düzeltelim.
Önce bana bir plan yaz: hangi dosyada neyi değiştireceksin, neden. Planı onaylamadan kod yazma.
Kurallar:
- Değişiklik sunucu/ tarafında olsun; OBB'ye dokunma.
- Mevcut testler bozulmasın; düzeltme için yeni bir test ekle (sunucu/testler/test_mac.py).
- Bitince testleri çalıştır: python -m unittest discover -s sunucu/testler
```

Planı onaylayınca model kodu yazar. Sonra oyunda dene: `baslat.bat` → oyunda bir Elite maçı aç.
Hâlâ donuyorsa `kayit_gonder.bat` çalıştır ve şu promptu ver:

```
Maç yine %0'da dondu. teshis.txt dosyasındaki emülatör kaydını ve sunucu/kayit/istemci_hatalari.txt
dosyasını (varsa) oku. "Unity", "Lua", "error", "exception" geçen satırları ve 7/705'ten sonraki
istekleri bul. Ne gördüğünü yaz ve 1.3'teki listede sıradaki sebebe geçmemiz gerekiyor mu, söyle.
```

### 1.5 Yükleme ekranındaki Çince ipuçları

```
Yükleme ekranındaki ipucu yazıları hâlâ Çince. Çeviri sistemi şöyle çalışıyor: sunucu/veri/ceviri_tr.json
sözlüğü, araclar/obb_yamala.py ile oyuna Ceviri.lua olarak gidiyor ve LuaConfManager tabloları bir kez
çeviriyor. Değişiklik yapmadan önce:
1. lua_cozulmus/ içinde yükleme ipuçlarının hangi tablodan ya da dosyadan okunduğunu bul.
2. Bu metinler neden çeviriye girmiyor (farklı tablo mu, kodun içine gömülü mü, çeviriden önce mi
   yükleniyor)?
3. Çözüm planını yaz, onay bekle.
```

---

## 2. Ben 10 Savaşa Hazır (Flash oyunu)

### 2.1 Araştırma (kod yok)

```
Yeni bir iş: "Ben 10 Savaşa Hazır" adlı eski Adobe Flash tarayıcı oyununu kendi bilgisayarımda
(Windows) çalıştırmak istiyorum. Flash 2020'de kapandı. Bu adımda kod yazma, sadece araştır.
1. Oyunun İngilizce adını ve hangi sitede yayınlandığını bul (Cartoon Network Türkiye olabilir;
   Ben 10 oyunlarının İngilizce adları farklı).
2. Flashpoint arşivinde (BlueMaxima's Flashpoint) var mı? Var ise hangi adla?
3. Oyunu çalıştırmanın yolları: Flashpoint, Ruffle (Flash öykünücüsü), bağımsız Flash Player
   projektörü. Her biri için artı/eksi yaz.
4. Oyun bir sunucuyla konuşuyor mu (skor, kayıt, giriş)? Konuşuyorsa bu yerel olarak nasıl taklit edilir?
Bulduklarını kaynak linkleriyle ver. Emin olmadığın şeyi "emin değilim" diye işaretle.
```

### 2.2 Kurulum planı

```
2.1'deki araştırmaya göre en kolay ve sağlam yolu seç. Bana adım adım bir kurulum planı yaz: ne
indirilecek (resmi kaynaktan), nereye konacak, hangi .bat dosyalarını oluşturacaksın. Bu proje
klasöründe "ben10/" adında ayrı bir klasör kullan, Streetball dosyalarına dokunma. Onay bekle.
```

### 2.3 Uygula

```
Planı onaylıyorum, uygula. Her adımdan sonra ne yaptığını tek satırla yaz. Sonunda ben10/README.md
dosyasına oyunu nasıl açacağımı 5 adımı geçmeyecek şekilde yaz.
```

---

## 3. Tokyo Ghoul oyunları (önce kapandılar mı?)

```
İki mobil oyunu araştır, kod yazma:
1. "Tokyo Ghoul: Dark War"
2. "Tokyo Ghoul :re invoke"
Her biri için: hâlâ açık mı, kapandıysa ne zaman kapandı (kaynakla)? Hangi oyun motoruyla yapılmış
(Unity mi, Cocos mu)? APK'sı güvenilir bir arşivde (APKMirror, APKPure, Internet Archive) var mı?
Kapandıysa, Streetball Hero'da yaptığımız gibi yerel sunucuyla çalıştırmak ne kadar zor olur:
kolay / orta / zor, sebebiyle. Hâlâ açık olan oyun için hiçbir şey yapmayacağız; sadece "açık" yaz.
```

---

## Takıldığında

**Model döngüye girdi ya da aynı şeyi tekrarlıyor:**
```
Dur. Şu ana kadar ne denedin, ne öğrendin, neyin işe yaramadığını 5 maddede yaz. Sonra farklı bir yol öner.
```

**Çok büyük bir iş yapmaya kalktı:**
```
Bu çok büyük. Sadece ilk küçük adımı yap ve dur.
```

**Bir şeyi bozdu:**
```
Son değişikliğin bir şeyi bozdu. git diff ile ne değiştirdiğini göster, sonra bozulan kısmı geri al
(git checkout -- <dosya>). Başka dosyaya dokunma.
```

**Emin olmadan konuşuyor:**
```
Bunu kodda/kaynakta gördün mü, yoksa tahmin mi? Gördüysen dosya:satır ya da link ver.
```

**Rapor yazmadan durdu:**
```
Ne yaptığını ve nerede kaldığını CLAUDE.md'deki RAPOR biçiminde yaz.
```

**"Autocompact is thrashing" yazdı:** Bir dosya bağlama sığmayacak kadar büyük. `/clear` yaz ve
promptun sonuna şunu ekleyerek tekrar ver: `Büyük dosyaları bütün okuma, grep ile ara.`

**"Prompt is too long" ya da çok yavaşladı:** `/compact` yaz; olmazsa `/clear` yazıp bulunduğun bölümün
promptunu baştan ver.

---

## Toplu görev (sen yokken hepsini sırayla yapsın)

Önce `/clear`, sağ altta **auto mode on** olsun (izin için beklemesin). Sonra bunu yapıştır:

```
Ben yokum, sana soru soramazsın. Aşağıdaki görevleri sırayla, tek başına yap. Takıldığın görevi raporda
"TAKILDI: sebep" diye yazıp bir sonrakine geç; hiçbir yerde durup onay bekleme.

KURALLAR
- Her adımın sonunda bulduklarını proje kökündeki RAPOR_OLLAMA.md dosyasına EKLE. Bağlamın sıfırlanırsa
  önce bu dosyayı oku ve kaldığın yerden devam et.
- Her iddiaya kaynak yaz (dosya:satır ya da link). Kanıtın yoksa başına "TAHMİN:" yaz. Sayı uydurma.
- Büyük dosyaları bütün okuma (CLAUDE.md'deki liste); grep, head ya da küçük Python betiği kullan.
- OBB'yi değiştirme. git commit ve git push yapma. Alt ajan/Workflow kullanma.

GÖREV A - Streetball maç yüklemesinin %0'da donması
A1. apk klasöründeki "main.*.obb" (zip dosyası) içinden assets/Lua/ klasörünü lua_cozulmus/ klasörüne
    çıkar, .lua dosyalarının her baytını 0xFF ile XOR'layarak çöz (bkz. araclar/lua_coz.py,
    araclar/obb_yamala.py). lua_cozulmus/ satırını .gitignore'a ekle.
A2. lua_cozulmus içinde MatchLoader.lua'yı bul; 32. satır civarındaki tutorial_data örneğinden şu
    değerleri GERÇEKTEN oku: oyuncu başına skill_list uzunluğu, attr.fight ve attr.morale değerleri,
    self_hp, enemy_hp, scene. Sonra sunucumuzun 7/705 cevabını üret (sunucu/testler/test_mac.py'deki gibi
    mac.battlemsg çağıran küçük bir Python betiğiyle) ve aynı alanları yazdır. İkisini tablo yap.
A3. 7/705 cevabı geldikten sonra yükleme çubuğunun nasıl ilerlediğini izle (MatchLoader.lua,
    MatchManager.lua ve çağırdıkları). %0'dan çıkmak için tamamlanması gereken ilk adımı ve o adımın
    cevaptan kullandığı alanları dosya:satır ile yaz. Bir id (beceri, oyuncu, sahne, rakip) yapılandırma
    tablosunda yoksa kod hata mı verir, sessizce mi bekler? Kanıtla.
A4. En olası 3 sebebi kanıtlarıyla sırala.
A5. En olası sebebi sunucu/ tarafında düzelt. Emin değilsen düzeltmeyi mac.py'nin başında açılıp
    kapatılabilen bir sabite bağla (varsayılan açık). Bunun için sunucu/testler/test_mac.py'ye test ekle.
    python -m unittest discover -s sunucu/testler çalıştır; hepsi geçmeli.
A6. Yükleme ekranındaki ipuçları Çince kalıyor. Sunucu/veri/ceviri_tr.json ile Ceviri.lua çevirisine
    neden girmediklerini bul (hangi tablo, ne zaman yükleniyor). Sadece sebep ve çözüm planı yaz.

GÖREV B - "Ben 10 Savaşa Hazır" (Flash oyunu) araştırması, kod yok
Oyunun İngilizce adı, Flashpoint arşivinde olup olmadığı, Ruffle/Flashpoint/Flash projektörü ile
çalıştırma seçenekleri (artı/eksi), sunucuya ihtiyaç duyup duymadığı. Kaynak linkleriyle yaz.

GÖREV C - Tokyo Ghoul oyunları araştırması, kod yok
"Tokyo Ghoul: Dark War" ve "Tokyo Ghoul :re invoke" için: açık mı kapandı mı (tarih ve kaynak), oyun
motoru, APK güvenilir bir arşivde var mı, yerel sunucuyla çalıştırma zorluğu (kolay/orta/zor ve neden).

BİTİŞ
RAPOR_OLLAMA.md'nin en başına 10 satırı geçmeyen bir ÖZET yaz: hangi görev bitti, hangisi takıldı,
hangi dosyaları değiştirdin, oyunda neyi denemem gerekiyor. Sonra CLAUDE.md'deki RAPOR biçimiyle bitir.
```

Dönünce: `RAPOR_OLLAMA.md` dosyasını aç, en baştaki ÖZET'i bana yapıştır. Değişiklikleri birlikte inceleyip
gönderelim.
