$html = Get-Content 'C:\Users\samue\Downloads\PROYECTOS_GAMORA\django_comercializadora\comercializadora\fruta_system\fruta_system\core\templates\core\viaje_detail.html' -Raw
$idxstart = $html.IndexOf('  <div class="col-md-8">')
$idxend = $html.IndexOf('<div class="card">', $idxstart + 100)
while ($html.Substring($idxend, 100) -notmatch 'Pagos al Proveedor') {
    $idxend = $html.IndexOf('<div class="card">', $idxend + 10)
    if ($idxend -lt 0) { break }
}
Write-Host "Indices: $idxstart $idxend"
