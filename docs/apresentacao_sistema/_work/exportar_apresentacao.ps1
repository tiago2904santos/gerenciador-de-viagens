$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
$pptx = Join-Path $root 'docs\apresentacao_sistema\Apresentacao_Completa_Sistema.pptx'
$pdf = Join-Path $root 'docs\apresentacao_sistema\Apresentacao_Completa_Sistema.pdf'
$render = Join-Path $root 'docs\apresentacao_sistema\_work\slides_renderizados'
New-Item -ItemType Directory -Force -Path $render | Out-Null
Get-ChildItem -LiteralPath $render -Filter 'Slide*.PNG' -File -ErrorAction SilentlyContinue | Remove-Item -Force
$powerPoint = New-Object -ComObject PowerPoint.Application
try {
    $presentation = $powerPoint.Presentations.Open($pptx, $true, $false, $false)
    try {
        $presentation.SaveAs($pdf, 32)
        $presentation.Export($render, 'PNG', 1280, 720)
    }
    finally {
        $presentation.Close()
    }
}
finally {
    $powerPoint.Quit()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($powerPoint) | Out-Null
}
Write-Output "pdf=$pdf"
Write-Output "render=$render"
