<# :
@echo off
title yt-dlp Auto-Installer and Updater
echo ========================================================
echo  Automated Downloader: yt-dlp, FFmpeg, and Deno
echo ========================================================
echo.
powershell -NoProfile -ExecutionPolicy Bypass -Command "$env:SCRIPT_DIR='%~dp0'; Invoke-Expression -Command (Get-Content '%~f0' -Raw)"
echo.
echo ========================================================
echo IMPORTANT: Close this window and open a fresh PowerShell
echo window to start using the 'yt-dlp' command!
echo ========================================================
pause
exit /b
#>

$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

# ---------------------------------------------------------------
# Settings
# ---------------------------------------------------------------
# $false = refuse to install anything that has no published SHA-256.
# Set to $true only if you knowingly accept unverified downloads.
$AllowUnverified = $false
$UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'

if (-not $env:SCRIPT_DIR) { $env:SCRIPT_DIR = (Get-Location).Path }
$baseDir  = $env:SCRIPT_DIR.TrimEnd('\')
$toolDir  = Join-Path $baseDir 'ytdlp-tools'
$stampDir = Join-Path $toolDir '.installed'

# ---------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------

# Looks up a release asset through the GitHub API and returns its
# download URL plus the SHA-256 digest GitHub computed for it.
function Get-GitHubAsset {
    param(
        [string]$Repo,
        [string]$AssetName,
        [string]$Tag = ''   # empty = the repo's "latest release"
    )
    $api = if ($Tag) { "https://api.github.com/repos/$Repo/releases/tags/$Tag" }
           else      { "https://api.github.com/repos/$Repo/releases/latest" }

    $rel = Invoke-RestMethod -Uri $api -Headers @{ 'User-Agent' = $UA; 'Accept' = 'application/vnd.github+json' }
    $asset = $rel.assets | Where-Object { $_.name -eq $AssetName } | Select-Object -First 1
    if (-not $asset) { throw "Asset '$AssetName' not found in the $Repo release." }

    $sha = $null
    if ($asset.digest -and ($asset.digest -match '^sha256:([0-9a-fA-F]{64})$')) {
        $sha = $Matches[1].ToLower()
    }
    [pscustomobject]@{ Name = $asset.name; Url = $asset.browser_download_url; Sha256 = $sha; Tag = $rel.tag_name }
}

# Up to date = key file exists AND the hash recorded at last install
# matches the hash of the current release asset.
function Test-UpToDate {
    param([string]$Name, $Asset, [string]$KeyFile)
    $stamp = Join-Path $stampDir "$Name.sha256"
    if ($Asset.Sha256 -and (Test-Path $KeyFile) -and (Test-Path $stamp)) {
        return ((Get-Content $stamp -Raw).Trim() -eq $Asset.Sha256)
    }
    return $false
}

function Set-Stamp {
    param([string]$Name, $Asset)
    if ($Asset.Sha256) {
        Set-Content -Path (Join-Path $stampDir "$Name.sha256") -Value $Asset.Sha256 -Encoding Ascii
    }
}

# Downloads to <Destination>.part, verifies SHA-256, then moves into place.
# A failed or interrupted download never leaves a file at the real path.
function Save-Verified {
    param($Asset, [string]$Destination)

    if (-not $Asset.Sha256 -and -not $AllowUnverified) {
        throw "No published SHA-256 for $($Asset.Name). Refusing to install an unverified file."
    }

    $part = "$Destination.part"
    if (Test-Path $part) { Remove-Item $part -Force }

    try {
        $request = [System.Net.WebRequest]::Create($Asset.Url)
        $request.Method = 'GET'
        $request.UserAgent = $UA
        $response = $null; $stream = $null; $fileStream = $null
        try {
            $response    = $request.GetResponse()
            $totalLength = $response.ContentLength
            $stream      = $response.GetResponseStream()
            $fileStream  = New-Object System.IO.FileStream($part, [System.IO.FileMode]::Create)
            $buffer      = New-Object byte[] 81920
            $downloaded  = 0
            $stopwatch   = [System.Diagnostics.Stopwatch]::StartNew()

            while (($read = $stream.Read($buffer, 0, $buffer.Length)) -gt 0) {
                $fileStream.Write($buffer, 0, $read)
                $downloaded += $read
                if ($totalLength -gt 0 -and $stopwatch.ElapsedMilliseconds -gt 500) {
                    $percent = [math]::Floor(($downloaded / $totalLength) * 100)
                    Write-Progress -Activity "Downloading $($Asset.Name)" -Status "$percent% Complete" -PercentComplete $percent
                    $stopwatch.Restart()
                }
            }
            if ($totalLength -gt 0 -and $downloaded -ne $totalLength) {
                throw "Incomplete download ($downloaded of $totalLength bytes)."
            }
        } finally {
            if ($fileStream) { $fileStream.Close() }
            if ($stream)     { $stream.Close() }
            if ($response)   { $response.Close() }
            Write-Progress -Activity "Downloading $($Asset.Name)" -Completed
        }

        if ($Asset.Sha256) {
            $actual = (Get-FileHash -Path $part -Algorithm SHA256).Hash.ToLower()
            if ($actual -ne $Asset.Sha256) {
                throw "SHA-256 mismatch for $($Asset.Name). Expected $($Asset.Sha256) but got $actual. File discarded."
            }
            Write-Host "[OK] SHA-256 verified." -ForegroundColor Green
        } else {
            Write-Host "[WARN] No checksum available; installing UNVERIFIED file." -ForegroundColor Red
        }

        Move-Item -Path $part -Destination $Destination -Force
    } catch {
        if (Test-Path $part) { Remove-Item $part -Force -ErrorAction SilentlyContinue }
        throw
    }
}

# ---------------------------------------------------------------
# Main
# ---------------------------------------------------------------
foreach ($d in @($toolDir, $stampDir)) {
    if (!(Test-Path $d)) { New-Item -ItemType Directory -Path $d | Out-Null }
}

Write-Host "Creating portable toolkit at: $toolDir" -ForegroundColor Cyan
Write-Host ""

$failures = @()

# 1. yt-dlp
Write-Host "1/3 yt-dlp..." -ForegroundColor Yellow
try {
    $asset = Get-GitHubAsset -Repo 'yt-dlp/yt-dlp' -AssetName 'yt-dlp.exe'
    $exe = Join-Path $toolDir 'yt-dlp.exe'
    if (Test-UpToDate 'yt-dlp' $asset $exe) {
        Write-Host "[SKIP] yt-dlp is already up to date ($($asset.Tag))." -ForegroundColor Gray
    } else {
        Save-Verified -Asset $asset -Destination $exe
        Set-Stamp 'yt-dlp' $asset
        Write-Host "[DONE] yt-dlp $($asset.Tag) installed." -ForegroundColor Green
    }
} catch {
    Write-Host "[FAILED] yt-dlp: $($_.Exception.Message)" -ForegroundColor Red
    $failures += 'yt-dlp'
}

# 2. Deno
Write-Host "2/3 Deno..." -ForegroundColor Yellow
try {
    $asset = Get-GitHubAsset -Repo 'denoland/deno' -AssetName 'deno-x86_64-pc-windows-msvc.zip'
    if (Test-UpToDate 'deno' $asset (Join-Path $toolDir 'deno.exe')) {
        Write-Host "[SKIP] Deno is already up to date ($($asset.Tag))." -ForegroundColor Gray
    } else {
        $denoZip = Join-Path $toolDir 'deno.zip'
        try {
            Save-Verified -Asset $asset -Destination $denoZip
            Expand-Archive -Path $denoZip -DestinationPath $toolDir -Force
        } finally {
            if (Test-Path $denoZip) { Remove-Item $denoZip -Force }
        }
        Set-Stamp 'deno' $asset
        Write-Host "[DONE] Deno $($asset.Tag) installed." -ForegroundColor Green
    }
} catch {
    Write-Host "[FAILED] Deno: $($_.Exception.Message)" -ForegroundColor Red
    $failures += 'Deno'
}

# 3. FFmpeg (shared build)
Write-Host "3/3 FFmpeg..." -ForegroundColor Yellow
try {
    $asset = Get-GitHubAsset -Repo 'BtbN/FFmpeg-Builds' -Tag 'latest' -AssetName 'ffmpeg-master-latest-win64-gpl-shared.zip'
    if (Test-UpToDate 'ffmpeg' $asset (Join-Path $toolDir 'ffmpeg.exe')) {
        Write-Host "[SKIP] FFmpeg is already up to date." -ForegroundColor Gray
    } else {
        $ffmpegZip = Join-Path $toolDir 'ffmpeg.zip'
        $ffmpegExt = Join-Path $toolDir 'ffmpeg-ext'
        try {
            Save-Verified -Asset $asset -Destination $ffmpegZip
            if (Test-Path $ffmpegExt) { Remove-Item $ffmpegExt -Recurse -Force }
            Expand-Archive -Path $ffmpegZip -DestinationPath $ffmpegExt -Force
            $inner = Get-ChildItem -Path $ffmpegExt -Directory | Select-Object -First 1
            $bin = Join-Path $inner.FullName 'bin'
            if (!(Test-Path $bin)) { throw "Unexpected FFmpeg archive layout (no bin folder)." }
            Move-Item -Path (Join-Path $bin '*') -Destination $toolDir -Force
        } finally {
            if (Test-Path $ffmpegExt) { Remove-Item $ffmpegExt -Recurse -Force -ErrorAction SilentlyContinue }
            if (Test-Path $ffmpegZip) { Remove-Item $ffmpegZip -Force -ErrorAction SilentlyContinue }
        }
        Set-Stamp 'ffmpeg' $asset
        Write-Host "[DONE] FFmpeg installed." -ForegroundColor Green
    }
} catch {
    Write-Host "[FAILED] FFmpeg: $($_.Exception.Message)" -ForegroundColor Red
    $failures += 'FFmpeg'
}

# ---------------------------------------------------------------
# PATH
# ---------------------------------------------------------------
Write-Host ""
Write-Host "Configuring User PATH..." -ForegroundColor Cyan
$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
if ($userPath -eq $null) { $userPath = '' }

$paths = $userPath -split ';'
if ($paths -contains $toolDir) {
    Write-Host "[INFO] The path is already in your Environment Variables." -ForegroundColor Green
} else {
    $newPath = if ($userPath -eq '') { $toolDir } else { $userPath.TrimEnd(';') + ';' + $toolDir }
    [Environment]::SetEnvironmentVariable('Path', $newPath, 'User')
    Write-Host "[SUCCESS] Path successfully added to Windows!" -ForegroundColor Green
}

# ---------------------------------------------------------------
# Helper scripts
# ---------------------------------------------------------------
Write-Host ""
Write-Host "Generating relink-path.bat for future portability..." -ForegroundColor Cyan

$relinkScript = @'
<# :
@echo off
title Relink Toolkit Path
echo ========================================================
echo  Updating Windows PATH for your Toolkit...
echo  (This does NOT update the tools. To update yt-dlp,
echo   FFmpeg and Deno, re-run the original installer.)
echo ========================================================
powershell -NoProfile -ExecutionPolicy Bypass -Command "$env:SCRIPT_DIR='%~dp0'; Invoke-Expression -Command (Get-Content '%~f0' -Raw)"
echo.
echo ========================================================
echo IMPORTANT: Close this window and open a fresh PowerShell!
echo ========================================================
pause
exit /b
#>

$ErrorActionPreference = 'Stop'
$toolDir = $env:SCRIPT_DIR.TrimEnd('\')
Write-Host "Current Toolkit Location: $toolDir" -ForegroundColor Cyan
Write-Host "Checking Windows PATH..." -ForegroundColor Yellow
$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
if ($userPath -eq $null) { $userPath = '' }
$paths = $userPath -split ';'
if ($paths -contains $toolDir) {
    Write-Host "[INFO] This exact path is already in your Environment Variables." -ForegroundColor Green
} else {
    $newPath = if ($userPath -eq '') { $toolDir } else { $userPath.TrimEnd(';') + ';' + $toolDir }
    [Environment]::SetEnvironmentVariable('Path', $newPath, 'User')
    Write-Host "[SUCCESS] Path successfully updated to the new location!" -ForegroundColor Green
}
'@

Set-Content -Path (Join-Path $toolDir 'relink-path.bat') -Value $relinkScript -Encoding Ascii
# Remove the old, misleadingly named script from earlier versions
$oldUpdate = Join-Path $toolDir 'update.bat'
if (Test-Path $oldUpdate) { Remove-Item $oldUpdate -Force }

Write-Host "Generating uninstall.bat for clean removal..." -ForegroundColor Cyan

$uninstallScript = @'
<# :
@echo off
title Uninstall Toolkit
echo ========================================================
echo  Removing Toolkit from Windows PATH...
echo ========================================================
powershell -NoProfile -ExecutionPolicy Bypass -Command "$env:SCRIPT_DIR='%~dp0'; Invoke-Expression -Command (Get-Content '%~f0' -Raw)"
echo.
echo ========================================================
echo UNINSTALL COMPLETE. 
echo You can now close this window and safely delete this entire folder!
echo ========================================================
pause
exit /b
#>

$ErrorActionPreference = 'Stop'
$toolDir = $env:SCRIPT_DIR.TrimEnd('\')
Write-Host "Target Folder: $toolDir" -ForegroundColor Cyan
Write-Host "Cleaning Windows PATH..." -ForegroundColor Yellow

$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
if ($userPath -ne $null) {
    $paths = $userPath -split ';'
    # Filter out the toolkit directory and any empty strings
    $newPaths = $paths | Where-Object { $_ -ne $toolDir -and $_ -ne '' }
    $newPathString = $newPaths -join ';'
    
    if ($newPathString -ne $userPath) {
        [Environment]::SetEnvironmentVariable('Path', $newPathString, 'User')
        Write-Host "[SUCCESS] Toolkit path completely removed from Windows Environment Variables!" -ForegroundColor Green
    } else {
        Write-Host "[INFO] The path was not found in your Environment Variables (already clean)." -ForegroundColor Green
    }
}
'@

Set-Content -Path (Join-Path $toolDir 'uninstall.bat') -Value $uninstallScript -Encoding Ascii

# ---------------------------------------------------------------
# Summary
# ---------------------------------------------------------------
Write-Host ""
$ytExe = Join-Path $toolDir 'yt-dlp.exe'
if (Test-Path $ytExe) {
    Write-Host "Installed yt-dlp version:" -ForegroundColor Cyan
    & $ytExe --version
}
if ($failures.Count -gt 0) {
    Write-Host ""
    Write-Host "Finished WITH ERRORS. Failed: $($failures -join ', '). Re-run to retry." -ForegroundColor Red
} else {
    Write-Host "All tools are installed, verified and ready." -ForegroundColor Green
}
