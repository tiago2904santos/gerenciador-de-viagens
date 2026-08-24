$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
$docx = Join-Path $root 'docs\apresentacao_sistema\_work\Manual_Funcional_Completo.docx'
$pdf = Join-Path $root 'docs\apresentacao_sistema\Manual_Funcional_Completo.pdf'
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {
    $document = $word.Documents.Open($docx, $false, $true)
    try {
        $document.ExportAsFixedFormat($pdf, 17)
    }
    finally {
        $document.Close($false)
    }
}
finally {
    $word.Quit()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
}
Write-Output "pdf=$pdf"
