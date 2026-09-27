param([Parameter(Mandatory=$true)][string[]]$Documents, [Parameter(Mandatory=$true)][string]$OutputDirectory)
$ErrorActionPreference = 'Stop'
$renderRoot = [System.IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Force -Path $renderRoot | Out-Null
foreach ($file in $Documents) {
    $wordRenderer = New-Object -ComObject Word.Application
    $wordRenderer.Visible = $false
    $wordRenderer.DisplayAlerts = 0
    $wordRenderer.AutomationSecurity = 3
    try {
        $inputDocument = (Resolve-Path -LiteralPath $file).Path
        $pdfDocument = Join-Path $renderRoot ([System.IO.Path]::GetFileNameWithoutExtension($inputDocument) + '.pdf')
        $document = $wordRenderer.Documents.Open($inputDocument, $false, $true, $false)
        try {
            $document.ExportAsFixedFormat($pdfDocument, 17)
            Write-Output $pdfDocument
        } finally { $document.Close(0); [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($document) }
    } finally {
        # Some Word installations exit after closing the last invisible document.
        try { $wordRenderer.Quit(0) } catch {
            if ($_.Exception.HResult -ne -2147023174) { throw }
        }
        [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($wordRenderer)
    }
}
