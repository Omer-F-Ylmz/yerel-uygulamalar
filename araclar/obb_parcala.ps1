# OBB dosyasını GitHub sınırına (100 MB) takılmayacak 45 MB'lık parçalara böler.
$ErrorActionPreference = 'Stop'
$kok = Split-Path -Parent $PSScriptRoot
$obb = Get-ChildItem (Join-Path $kok 'apk') -Recurse -Filter *.obb | Select-Object -First 1
if (-not $obb) { Write-Host "apk klasorunde .obb bulunamadi." -ForegroundColor Red; exit 1 }
$hedef = Join-Path $kok 'obb_parca'
New-Item -ItemType Directory -Force $hedef | Out-Null
Get-ChildItem $hedef -Filter 'parca*' | Remove-Item
$giris = [IO.File]::OpenRead($obb.FullName)
$tampon = New-Object byte[] (45MB)
$i = 0
while (($n = $giris.Read($tampon, 0, $tampon.Length)) -gt 0) {
    $cikis = [IO.File]::Create((Join-Path $hedef ('parca{0:D2}' -f $i)))
    $cikis.Write($tampon, 0, $n)
    $cikis.Close()
    $i++
}
$giris.Close()
Set-Content (Join-Path $hedef 'ad.txt') $obb.Name
Write-Host "$($obb.Name) -> $i parca" -ForegroundColor Green
