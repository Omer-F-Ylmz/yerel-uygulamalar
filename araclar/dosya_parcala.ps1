# Bir klasördeki büyük dosyaları GitHub sınırına (100 MB) takılmayacak 45 MB'lık parçalara böler.
#   powershell -File dosya_parcala.ps1 <kaynak klasör> <hedef klasör>
param([string]$kaynak, [string]$hedef)
$ErrorActionPreference = 'Stop'
$dosyalar = Get-ChildItem $kaynak -File | Where-Object { $_.Extension -in '.apk', '.xapk', '.apks', '.obb', '.zip', '.rar', '.7z' }
if (-not $dosyalar) { Write-Host "$kaynak klasorunde .apk/.xapk/.obb bulunamadi." -ForegroundColor Red; exit 1 }
New-Item -ItemType Directory -Force $hedef | Out-Null
Get-ChildItem $hedef | Remove-Item -Recurse
foreach ($d in $dosyalar) {
    $giris = [IO.File]::OpenRead($d.FullName)
    $tampon = New-Object byte[] (45MB)
    $i = 0
    while (($n = $giris.Read($tampon, 0, $tampon.Length)) -gt 0) {
        $cikis = [IO.File]::Create((Join-Path $hedef ('{0}.parca{1:D2}' -f $d.Name, $i)))
        $cikis.Write($tampon, 0, $n)
        $cikis.Close()
        $i++
    }
    $giris.Close()
    Write-Host "$($d.Name) -> $i parca" -ForegroundColor Green
}
