$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

python -m pip install -r requirements.txt pyinstaller
python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --onefile `
    --name WarDogsArtillery `
    --collect-all customtkinter `
    app.py

Write-Host "Ready: dist\WarDogsArtillery.exe"
