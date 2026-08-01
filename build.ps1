<#
================================================================================
 build.ps1 - Stage 2: pack EasyVoice into an unzip-and-double-click bundle (Windows)
================================================================================
 Strategy: use conda-pack on the already-validated `easyvoice` conda env (Python
       3.12 + CUDA torch + qwen-tts + gradio; torch falls back to CPU with no
       NVIDIA GPU). Far more reliable than pip-installing torch / qwen-tts into
       a python-embed tree (see the design doc, section 6 risk table, fallback
       "portable Miniconda").

 Output (<Ver> is -Version; the CPU lite bundle appends a -cpu suffix):
   dist\EasyVoice-<Ver>\          <- bundle directory (hand this to users as-is)
     |- runtime\                  <- embedded Python 3.12 + deps (conda-pack)
     |- app\  app_main.py         <- the program
     |- models\Qwen\...0___6B...  <- preinstalled 0.6B model weights
     |- assets\ README*.md ...    <- in-bundle docs and images (the README's
     |                               relative links break without them)
     |- voices\ presets\ outputs\ <- empty user-data directories
     \- Start EasyVoice.bat       <- the only thing a user double-clicks
   dist\EasyVoice-<Ver>.zip       <- archive (for hosting / distribution)

 Usage (from the project root, in PowerShell 7 on the base env):
     pwsh -File build.ps1 -Version v1.1.1
   -Version names the output directory and zip, and MUST be passed explicitly
   when cutting a release: the default below is hardcoded, so omitting it
   produces a directory / zip named after the previous version and overwrites
   that build in dist\.
   Other optional parameters:
     pwsh -File build.ps1 -Version v1.1.1 -EnvName easyvoice -CondaRoot D:\miniconda3

 Notes:
   - Run `python app_main.py` successfully once first (confirms the env works).
   - Close any running app (port 7860) before packing, to avoid file locks.
   - Output is roughly 6-8GB; make sure there is disk space.

 This script is intentionally ASCII-only: it is read and run by Windows
 PowerShell 5.1 and by consoles on non-UTF-8 code pages, where non-ASCII
 comments and output turn into mojibake.
================================================================================
#>
[CmdletBinding()]
param(
  [string]$EnvName   = "easyvoice",
  [string]$Version   = "v1.1.1",
  [string]$CondaRoot = "$env:USERPROFILE\miniconda3",
  [string]$ModelId   = "Qwen/Qwen3-TTS-12Hz-0.6B-Base",
  [ValidateSet("gpu","cpu")][string]$Variant = "gpu"
)

$ErrorActionPreference = "Stop"
# Non-zero exit codes from native commands (conda / robocopy / 7z) are checked
# by hand below, so do not let them throw automatically.
$PSNativeCommandUseErrorActionPreference = $false

$ProjectRoot = $PSScriptRoot
if ($Variant -eq "cpu") {
  if ($EnvName -eq "easyvoice") { $EnvName = "easyvoice-cpu" }   # use the CPU env unless told otherwise
  $DistName    = "EasyVoice-$Version-cpu"
} else {
  $DistName    = "EasyVoice-$Version"
}
$Dist        = Join-Path $ProjectRoot "dist"
$Stage       = Join-Path $Dist $DistName
$RuntimeDir  = Join-Path $Stage "runtime"
$EnvPath     = Join-Path $CondaRoot "envs\$EnvName"
$Conda       = Join-Path $CondaRoot "condabin\conda.bat"

function Step($n, $m) { Write-Host "`n==== [$n] $m ====" -ForegroundColor Cyan }
function Ok($m)        { Write-Host "  [OK] $m" -ForegroundColor Green }

# 7-Zip is much faster than PowerShell's Compress/Expand-Archive and handles
# >4GB (zip64) safely.
$SevenZip = $null
foreach ($c in @("$env:ProgramFiles\7-Zip\7z.exe", "${env:ProgramFiles(x86)}\7-Zip\7z.exe", "7z.exe")) {
  if (Test-Path $c) { $SevenZip = $c; break }
  $g = Get-Command $c -ErrorAction SilentlyContinue
  if ($g) { $SevenZip = $g.Source; break }
}
# bsdtar (tar.exe, shipped with Windows 10+) also handles >4GB zips safely and
# is the preferred fallback when 7-Zip is absent.
$UseTar = [bool](Get-Command tar.exe -ErrorAction SilentlyContinue)

# ---- 0. Preflight ------------------------------------------------------------
Step 0 "Preflight"
if (-not (Test-Path $Conda))                              { throw "conda not found: $Conda (use -CondaRoot to point at the miniconda root)" }
if (-not (Test-Path (Join-Path $EnvPath "python.exe")))   { throw "conda env '$EnvName' not found: $EnvPath" }
if (-not (Test-Path (Join-Path $ProjectRoot "app\ui.py"))){ throw "run this from the project root (app\ui.py is missing)" }
if (-not (Test-Path (Join-Path $ProjectRoot "Start EasyVoice.bat"))) { throw "Start EasyVoice.bat is missing" }
if (Get-NetTCPConnection -LocalPort 7860 -State Listen -ErrorAction SilentlyContinue) {
  Write-Warning "An app appears to be running on port 7860; close it before packing (it locks runtime files)."
}
if (-not $PSBoundParameters.ContainsKey('Version')) {
  Write-Warning "-Version was not passed; falling back to the script default $Version. Pass -Version when cutting a release, or this overwrites the same-named previous build in dist\."
}
$zipTool = if ($SevenZip) { "7-Zip" } elseif ($UseTar) { "tar/bsdtar" } else { "PowerShell built-in (slow)" }
Ok "conda / env / project layout ready; archiver: $zipTool"

# ---- 1. Make sure base has conda-pack ----------------------------------------
Step 1 "Ensure conda-pack is available"
& $Conda run -n base python -c "import conda_pack" 2>$null
if ($LASTEXITCODE -ne 0) {
  Write-Host "  Installing conda-pack into base (conda-forge only, to avoid the defaults channel ToS)..."
  & $Conda install -n base -y --override-channels -c conda-forge conda-pack
  if ($LASTEXITCODE -ne 0) {
    Write-Host "  conda install failed; falling back to pip ..."
    & $Conda run -n base python -m pip install -q conda-pack
    if ($LASTEXITCODE -ne 0) { throw "conda-pack install failed (both conda-forge and pip)" }
  }
}
Ok "conda-pack ready"

# ---- 2. Prepare the stage directory ------------------------------------------
Step 2 "Prepare the stage directory"
if (Test-Path $Stage) { Remove-Item $Stage -Recurse -Force }
New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
Ok "cleaned and created $Stage"

# ---- 3. conda-pack the env -> runtime\ ---------------------------------------
Step 3 "Pack the conda env (about 5GB, takes a few minutes)"
$packZip = Join-Path $Dist "runtime.zip"
if (Test-Path $packZip) { Remove-Item $packZip -Force }
& $Conda run -n base conda-pack -n $EnvName -o "$packZip" --format zip --n-threads -1 --ignore-missing-files --force
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $packZip)) { throw "conda-pack failed" }

Write-Host "  Extracting runtime ..."
if     ($SevenZip) { & $SevenZip x "$packZip" "-o$RuntimeDir" -y | Out-Null; if ($LASTEXITCODE -ne 0) { throw "7z extract failed" } }
elseif ($UseTar)   { & tar.exe -xf "$packZip" -C "$RuntimeDir";              if ($LASTEXITCODE -ne 0) { throw "tar extract failed" } }
else               { Expand-Archive -Path $packZip -DestinationPath $RuntimeDir -Force }
Remove-Item $packZip -Force
if (-not (Test-Path (Join-Path $RuntimeDir "python.exe")))                 { throw "bad runtime extract: python.exe missing" }
if (-not (Test-Path (Join-Path $RuntimeDir "Scripts\conda-unpack.exe")))   { throw "bad runtime extract: conda-unpack.exe missing" }
Ok "runtime\ ready (Python 3.12 + torch + qwen-tts + gradio)"

# ---- 4. Copy the program + launcher ------------------------------------------
Step 4 "Copy app/ and the launcher"
Copy-Item (Join-Path $ProjectRoot "app")         (Join-Path $Stage "app") -Recurse -Force
Copy-Item (Join-Path $ProjectRoot "app_main.py") $Stage -Force
# The bundled README links to these documents and images. Leave one out and the
# corresponding relative link points at a file that does not exist once the
# bundle is extracted. Adding a relative link to the README means adding the
# target here too.
foreach ($f in @(
    "README.md", "README.en.md",
    "DEVELOPMENT.md", "DEVELOPMENT.en.md",
    "CHANGELOG.md", "CHANGELOG.en.md",
    "LICENSE", "requirements.txt",
    "docs\ARCHITECTURE.md", "docs\SPIKE-qwen-tts.md",
    "assets\brand\social-card.png", "assets\brand\social-card.en.png",
    "assets\packaging\THIRD-PARTY-NOTICES.txt")) {
  $p = Join-Path $ProjectRoot $f
  if (-not (Test-Path $p)) { Write-Warning "missing $f -- the bundled README's link to it will break"; continue }
  $dest    = Join-Path $Stage $f
  $destDir = Split-Path $dest -Parent
  if (-not (Test-Path $destDir)) { New-Item -ItemType Directory -Force -Path $destDir | Out-Null }
  Copy-Item $p $dest -Force
}
# Drop any __pycache__ that came along
Get-ChildItem (Join-Path $Stage "app") -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
  Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
# Launcher: copy with forced CRLF + UTF-8 (no BOM) so cmd runs the .bat correctly
$batText = (Get-Content (Join-Path $ProjectRoot "Start EasyVoice.bat") -Raw) -replace "`r?`n", "`r`n"
[IO.File]::WriteAllText((Join-Path $Stage "Start EasyVoice.bat"), $batText, (New-Object Text.UTF8Encoding($false)))
Ok "app/, app_main.py, Start EasyVoice.bat, README / DEVELOPMENT / CHANGELOG / LICENSE and assets/ are in place"

# ---- 5. Model weights (0.6B) + license notices -------------------------------
if ($Variant -eq "cpu") {
  Step 5 "CPU lite bundle: skipping the bundled model (downloaded in-app on first launch)"
  Copy-Item (Join-Path $ProjectRoot "assets\packaging\THIRD-PARTY-NOTICES.txt") `
            (Join-Path $Stage "THIRD-PARTY-NOTICES.txt") -Force
  Ok "model skipped; third-party notices placed"
} else {
  Step 5 "Prepare model weights (0.6B)"
  $srcModelOrg = Join-Path $ProjectRoot "models\Qwen"
  $dstModelOrg = Join-Path $Stage "models\Qwen"
  $modelLeaf   = "Qwen3-TTS-12Hz-0___6B-Base"   # ModelScope writes '.' as '___'; tts_engine parses it back
  if (Test-Path (Join-Path $srcModelOrg $modelLeaf)) {
    Write-Host "  Copying the already-downloaded model ..."
    New-Item -ItemType Directory -Force -Path $dstModelOrg | Out-Null
    robocopy "$srcModelOrg" "$dstModelOrg" /E /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "model copy failed (robocopy=$LASTEXITCODE)" }
  } else {
    Write-Host "  No local model; downloading via modelscope into the stage directory ..."
    $env:MODELSCOPE_CACHE = (Join-Path $Stage "models")
    & (Join-Path $EnvPath "python.exe") -c "from modelscope import snapshot_download; snapshot_download('$ModelId')"
    if ($LASTEXITCODE -ne 0) { throw "model download failed" }
  }
  # Apache-2.0: place the full license text inside the model directory
  # (redistribution obligation)
  $apacheCache = Join-Path $Dist "_cache\LICENSE-Apache-2.0.txt"
  if (-not (Test-Path $apacheCache)) {
    New-Item -ItemType Directory -Force -Path (Split-Path $apacheCache) | Out-Null
    Invoke-WebRequest -Uri "https://www.apache.org/licenses/LICENSE-2.0.txt" -OutFile $apacheCache -UseBasicParsing
  }
  $modelDir = Join-Path $dstModelOrg $modelLeaf
  if (Test-Path $modelDir) { Copy-Item $apacheCache (Join-Path $modelDir "LICENSE") -Force }
  # Top-level third-party notices (model / FFmpeg / runtime) - template is
  # version-controlled with the repo
  Copy-Item (Join-Path $ProjectRoot "assets\packaging\THIRD-PARTY-NOTICES.txt") `
            (Join-Path $Stage "THIRD-PARTY-NOTICES.txt") -Force
  Ok "model LICENSE and THIRD-PARTY-NOTICES packaged"
}

# ---- 6. Empty user-data directories ------------------------------------------
Step 6 "Create user-data directories"
foreach ($d in @("voices", "presets", "outputs")) {
  New-Item -ItemType Directory -Force -Path (Join-Path $Stage $d) | Out-Null
}
Ok "voices/ presets/ outputs/ created"

# ---- 6.5 ffmpeg (needed for speed control; the app degrades gracefully) ------
Step "6.5" "Prepare ffmpeg (needed for speed control)"
$ffDir   = Join-Path $Stage "ffmpeg"
$ffExe   = Join-Path $ffDir "ffmpeg.exe"
$cache   = Join-Path $Dist "_cache"
$cachedFf= Join-Path $cache "ffmpeg.exe"
try {
  New-Item -ItemType Directory -Force -Path $ffDir, $cache | Out-Null
  if (-not (Test-Path $cachedFf)) {
    $url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
    $zip = Join-Path $cache "ffmpeg.zip"
    Write-Host "  Downloading a static ffmpeg build (about 80MB, first run only)..."
    Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing
    $tmp = Join-Path $cache "ff_extract"
    if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
    if     ($SevenZip) { & $SevenZip x "$zip" "-o$tmp" -y | Out-Null }
    elseif ($UseTar)   { New-Item -ItemType Directory -Force -Path $tmp | Out-Null; & tar.exe -xf "$zip" -C "$tmp" }
    else               { Expand-Archive -Path $zip -DestinationPath $tmp -Force }
    $found = Get-ChildItem $tmp -Recurse -Filter "ffmpeg.exe" | Select-Object -First 1
    if (-not $found) { throw "ffmpeg.exe not found after extraction" }
    Copy-Item $found.FullName $cachedFf -Force
    Remove-Item $tmp -Recurse -Force; Remove-Item $zip -Force
  }
  Copy-Item $cachedFf $ffExe -Force
  # This FFmpeg is a GPLv3 build: ship the full license text + source offer
  # (redistribution obligation)
  $gplCache = Join-Path $cache "COPYING.GPLv3.txt"
  if (-not (Test-Path $gplCache)) {
    Invoke-WebRequest -Uri "https://www.gnu.org/licenses/gpl-3.0.txt" -OutFile $gplCache -UseBasicParsing
  }
  Copy-Item $gplCache (Join-Path $ffDir "COPYING.GPLv3.txt") -Force
  Copy-Item (Join-Path $ProjectRoot "assets\packaging\ffmpeg-README-LICENSE.txt") `
            (Join-Path $ffDir "README-LICENSE.txt") -Force
  Ok ("ffmpeg.exe + GPLv3 license bundled ({0} MB)" -f [math]::Round((Get-Item $ffExe).Length/1MB))
} catch {
  Write-Warning "ffmpeg setup failed: $($_.Exception.Message); the bundle still works, but speed != 1.0 will not take effect."
  if (Test-Path $ffDir) { Remove-Item $ffDir -Recurse -Force }
}

# ---- 7. Compress into the bundle archive -------------------------------------
Step 7 "Compress into the bundle archive (slow)"
$zipPath = Join-Path $Dist "$DistName.zip"
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
if ($SevenZip) {
  & $SevenZip a -tzip "$zipPath" "$Stage" -mx=5 | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "7z compression failed" }
} elseif ($UseTar) {
  & tar.exe -c -a -f "$zipPath" -C "$Dist" "$DistName"
  if ($LASTEXITCODE -ne 0) { throw "tar compression failed" }
} else {
  Write-Warning "Using PowerShell's built-in compression; >4GB is slow, please wait ..."
  Compress-Archive -Path $Stage -DestinationPath $zipPath -CompressionLevel Optimal
}
$zipGB = "{0:N2}" -f ((Get-Item $zipPath).Length / 1GB)
Ok "wrote $zipPath ($zipGB GB)"

# ---- Done --------------------------------------------------------------------
Write-Host "`nAll done." -ForegroundColor Green
Write-Host "  Bundle directory: $Stage"
Write-Host "  Archive:          $zipPath  ($zipGB GB)"
Write-Host "`nAcceptance: copy the zip to a clean Windows machine (ideally without an NVIDIA GPU), extract it"
Write-Host "            and double-click 'Start EasyVoice.bat'. First run: ~1 min init + ~30 s model load, then a browser opens."
