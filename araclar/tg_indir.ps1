# Tokyo Ghoul APK'larını indirtip tokyo_ghoul klasörüne toplar.
# Uptodown indirmeyi insan doğrulamasıyla (Cloudflare) koruduğu için sayfalar tarayıcıda açılır,
# kullanıcı iki kez "Download"a basar; dosyalar İndirilenler klasöründen otomatik alınır.
$ErrorActionPreference = 'Stop'
$kok = Split-Path -Parent $PSScriptRoot
$hedef = Join-Path $kok 'tokyo_ghoul'
New-Item -ItemType Directory -Force $hedef | Out-Null
$indirilenler = (New-Object -ComObject Shell.Application).NameSpace('shell:Downloads').Self.Path
$baslangic = Get-Date

$oyunlar = @(
    @{ ad = 'TOKYO GHOUL [:re birth]'; desen = '*re*birth*'; sayfa = 'https://tokyo-ghoul-re-birth.en.uptodown.com/android/download' },
    # Uptodown'da Dark War indirilemiyor; son surum 1.2.14 APKPure'da. Olmazsa Internet Archive'daki 1.1.6 iner.
    @{ ad = 'Tokyo Ghoul: Dark War 1.2.14'; desen = '*dark*war*'; haric = '*1.1.6*'; sayfa = 'https://apkpure.net/tokyo-ghoul-dark-war/org.gamesamba.TokyoGhoul/download';
       yedek = 'https://archive.org/download/TokyoGhoulDarkWarV1.1.6Android36Youtube/Tokyo%20Ghoul%20Dark%20War_v1.1.6_android36_youtube.apk' }
)

function Bul($desen, $haric = '-') {
    foreach ($yer in @($hedef, $indirilenler)) {
        $f = Get-ChildItem $yer -File -ErrorAction SilentlyContinue |
             Where-Object { $_.Name -like $desen -and $_.Name -notlike $haric -and $_.Extension -in '.apk', '.xapk' } |
             Sort-Object LastWriteTime -Descending | Select-Object -First 1
        if ($f) { return $f }
    }
    return $null
}

$eksik = $oyunlar | Where-Object { $_.sayfa -and -not (Bul $_.desen $_.haric) }
if ($eksik) {
    Write-Host ""
    Write-Host "Tarayicida $($eksik.Count) sayfa acilacak. Her birinde yesil 'Download' dugmesine bas." -ForegroundColor Yellow
    Write-Host "'Insan oldugunu dogrula' kutusu cikarsa isaretle. Iki indirme de bitince buraya don." -ForegroundColor Yellow
    foreach ($o in $eksik) { Start-Process $o.sayfa; Start-Sleep -Seconds 2 }
    Write-Host ""
    Write-Host "Indirilenler klasoru izleniyor: $indirilenler"
    $son = (Get-Date).AddMinutes(20)
    while ((Get-Date) -lt $son) {
        $kalan = $eksik | Where-Object {
            $f = Bul $_.desen $_.haric
            -not $f -or ((Get-Date) - $f.LastWriteTime).TotalSeconds -lt 5   # hâlâ yazılıyor
        }
        $parcali = Get-ChildItem $indirilenler -File -ErrorAction SilentlyContinue |
                   Where-Object { $_.Extension -in '.crdownload', '.part', '.partial' }
        if (-not $kalan -and -not $parcali) { break }
        Write-Host ("  bekleniyor: " + (($kalan | ForEach-Object { $_.ad }) -join ', ')) -NoNewline
        Write-Host "`r" -NoNewline
        Start-Sleep -Seconds 5
    }
    Write-Host ""
}

foreach ($o in $oyunlar) {
    $f = Bul $o.desen $o.haric
    if (-not $f -and $o.yedek) {
        Write-Host "$($o.ad) bulunamadi; Internet Archive'daki eski surum indiriliyor..." -ForegroundColor Yellow
        $yol = Join-Path $hedef 'tokyo-ghoul-dark-war-1.1.6.apk'
        & curl.exe -L --fail -o $yol $o.yedek
        if ($LASTEXITCODE -eq 0) { $f = Get-Item $yol }
    }
    if (-not $f) { Write-Host "$($o.ad) indirilemedi." -ForegroundColor Red; exit 1 }
    if ($f.DirectoryName -ne $hedef) { Move-Item -Force $f.FullName (Join-Path $hedef $f.Name); $f = Get-Item (Join-Path $hedef $f.Name) }
    Write-Host ("TAMAM  {0}  ({1:N1} MB)" -f $f.Name, ($f.Length / 1MB)) -ForegroundColor Green
}
