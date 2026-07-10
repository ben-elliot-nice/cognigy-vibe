# cognigy-setup.ps1 — Bootstrap script for Windows
# Installs uv if absent, then runs the cognigy-vibe setup wizard.

$ErrorActionPreference = "Stop"

if (-not (Get-Command uvx -ErrorAction SilentlyContinue)) {
    Write-Host "uv not found — installing uv..."
    powershell -ExecutionPolicy Bypass -c "irm https://astral.sh/uv/install.ps1 | iex"
    # Reload PATH
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "User") + ";" + $env:PATH
    if (-not (Get-Command uvx -ErrorAction SilentlyContinue)) {
        Write-Error "uv installed but uvx not on PATH. Open a new terminal and re-run this script."
        exit 1
    }
}

uvx --from cognigy-vibe-mcp cognigy-vibe-setup @args
