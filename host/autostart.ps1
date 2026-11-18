param([switch]$Enable)
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$lnk = Join-Path ([Environment]::GetFolderPath('Startup')) 'StreamDeck.lnk'
if ($Enable) {
    $pyw = (Get-Command pythonw -ErrorAction SilentlyContinue).Source
    if (-not $pyw) { Write-Host "pythonw not found - install Python from python.org (tick 'Add to PATH')."; exit 1 }
    $s = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)
    $s.TargetPath = $pyw
    $s.Arguments = '"' + (Join-Path $dir 'streamdeck.py') + '"'
    $s.WorkingDirectory = $dir
    $s.Save()
    Write-Host "Autostart enabled. Stream Deck will start after you log in to Windows."
} else {
    if (Test-Path $lnk) { Remove-Item $lnk; Write-Host "Autostart disabled." } else { Write-Host "Autostart was not enabled." }
}
