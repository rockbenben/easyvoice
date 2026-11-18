<#
================================================================================
 build.ps1 - Stage 2: pack EasyVoice into an unzip-and-double-click bundle (Windows)
================================================================================
 Strategy: use conda-pack on the already-validated `easyvoice` conda env (Python
       3.12 + CUDA torch + qwen-tts + gradio; torch falls back to CPU with no
       NVIDIA GPU). Far more reliable than pip-installing torch / qwen-tts into
       a python-embed tree.

 Output (<Ver> is -Version; the CPU lite bundle appends a -cpu suffix):
   dist\EasyVoice-<Ver>\          <- bundle directory (hand this to users as-is)
     |- runtime\                  <- embedded Python 3.12 + deps (conda-pack)
     |- app\  app_main.py         <- the program
     |- models\Qwen\...0___6B...  <- preinstalled 0.6B model weights (full bundle only)
     |- docs\ assets\ README*.md  <- in-bundle docs and images (the README's
     |  DEVELOPMENT*.md ...         relative links break without them)
     |- ffmpeg\                   <- ffmpeg.exe, ffprobe.exe + GPLv3 license texts
     |- THIRD-PARTY-NOTICES.txt   <- third-party component license notices
     |- voices\ presets\ outputs\ <- empty user-data directories
     \- Start EasyVoice.bat       <- the only thing a user double-clicks
   dist\EasyVoice-<Ver>.zip       <- archive (for hosting / distribution)

 Usage (from the project root, in PowerShell 7 on the base env):
     pwsh -File build.ps1 -Version v1.1.2
   -Version names the output directory and zip, and MUST be passed explicitly
   when cutting a release: the default below is hardcoded, so omitting it
   produces a directory / zip named after the previous version and overwrites
   that build in dist\.
   Other optional parameters (defaults in the param block below):
     pwsh -File build.ps1 -Version v1.1.2 -EnvName easyvoice -CondaRoot D:\miniconda3
     pwsh -File build.ps1 -Version v1.1.2 -Variant cpu   # easyvoice-cpu env, no CUDA, no bundled model
     -ModelId selects the model id packed into the full bundle (default Qwen/Qwen3-TTS-12Hz-0.6B-Base).

 Notes:
   - Run `python app_main.py` successfully once first (confirms the env works).
   - Close any running app (port 7860) before packing, to avoid file locks.
   - The full bundle directory is roughly 6-8GB (runtime ~5GB + 0.6B weights
     ~2.3GB); the zip is about 4.6GB. Reserve about 12-13GB in dist\ for both.

 This script is intentionally ASCII-only: it is read and run by Windows
 PowerShell 5.1 and by consoles on non-UTF-8 code pages, where non-ASCII
 comments and output turn into mojibake.
================================================================================
#>
[CmdletBinding()]
param(
  [string]$EnvName   = "easyvoice",
  [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._+-]*$')][string]$Version = "v1.1.2",
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
$CacheDir    = Join-Path $Dist "_cache"
$RuntimeDir  = Join-Path $Stage "runtime"
$EnvPath     = [IO.Path]::GetFullPath((Join-Path $CondaRoot "envs\$EnvName"))
$Conda       = Join-Path $CondaRoot "condabin\conda.bat"

function Step($n, $m) { Write-Host "`n==== [$n] $m ====" -ForegroundColor Cyan }
function Ok($m)        { Write-Host "  [OK] $m" -ForegroundColor Green }

function Assert-DistPath([string]$Path) {
  $root = [IO.Path]::GetFullPath($Dist).TrimEnd('\', '/')
  $target = [IO.Path]::GetFullPath($Path).TrimEnd('\', '/')
  $prefix = $root + [IO.Path]::DirectorySeparatorChar
  if (-not $target.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Path must be inside dist: $target"
  }

  # A lexical descendant can resolve elsewhere through a junction or symlink.
  $ancestors = [Collections.Generic.Stack[string]]::new()
  for ($current = $target; ; $current = [IO.Path]::GetDirectoryName($current)) {
    $ancestors.Push($current)
    if ($current -eq $root) { break }
  }
  foreach ($current in $ancestors) {
    try {
      $item = Get-Item -LiteralPath $current -Force -ErrorAction Stop
      if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw "Refusing reparse point in dist path: $current"
      }
    } catch [System.Management.Automation.ItemNotFoundException] {
      # New paths are allowed. Any existing ancestors still need checking.
    }
  }
  return $target
}

function Remove-DistTree([string]$Path) {
  $target = Assert-DistPath $Path
  if (-not (Test-Path -LiteralPath $target)) { return }

  # Check descendants without walking through any link, including on PowerShell 5.1.
  $pending = [Collections.Generic.Stack[string]]::new()
  $pending.Push($target)
  while ($pending.Count -gt 0) {
    foreach ($item in (Get-ChildItem -LiteralPath ($pending.Pop()) -Force)) {
      if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw "Refusing reparse point in cleanup tree: $($item.FullName)"
      }
      if ($item.PSIsContainer) { $pending.Push($item.FullName) }
    }
  }
  Remove-Item -LiteralPath $target -Recurse -Force
}

function Install-BundledFfmpeg([string]$Destination, [string]$Cache, [string]$FfmpegVersion, [string]$Sha256) {
  $bundle = Assert-DistPath $Destination
  $name = "ffmpeg-$FfmpegVersion-essentials_build"
  $cachedZip = Assert-DistPath (Join-Path $Cache "$name.zip")
  $work = Assert-DistPath (Join-Path $Cache ("ffmpeg-work-" + [guid]::NewGuid().ToString('N')))

  try {
    New-Item -ItemType Directory -Force -Path $work | Out-Null
    # Hash the private copy that will be extracted. The old raw .exe cache is unused.
    $zip = Join-Path $work "$name.zip"
    if (Test-Path -LiteralPath $cachedZip -PathType Leaf) {
      Copy-Item -LiteralPath $cachedZip -Destination $zip
    }
    if (-not (Test-Path -LiteralPath $zip) -or (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash -ne $Sha256) {
      if (Test-Path -LiteralPath $zip) { Write-Warning "FFmpeg cache SHA-256 mismatch. Downloading the pinned archive again." }
      $url = "https://github.com/GyanD/codexffmpeg/releases/download/$FfmpegVersion/$name.zip"
      Write-Host "  Downloading FFmpeg $FfmpegVersion Essentials ..."
      Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing -TimeoutSec 300
      if ((Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash -ne $Sha256) {
        throw "FFmpeg download SHA-256 mismatch: $name.zip"
      }
      Copy-Item -LiteralPath $zip -Destination $cachedZip -Force
    }

    Expand-Archive -LiteralPath $zip -DestinationPath $work
    $extracted = Join-Path $work $name
    New-Item -ItemType Directory -Force -Path $bundle | Out-Null
    foreach ($exe in @("ffmpeg.exe", "ffprobe.exe")) {
      Copy-Item -LiteralPath (Join-Path $extracted "bin\$exe") -Destination $bundle
    }
    Copy-Item -LiteralPath (Join-Path $extracted "LICENSE") -Destination (Join-Path $bundle "COPYING.GPLv3.txt")
    Copy-Item -LiteralPath (Join-Path $ProjectRoot "assets\packaging\ffmpeg-README-LICENSE.txt") `
              -Destination (Join-Path $bundle "README-LICENSE.txt")
  } finally {
    Remove-DistTree $work
  }
}

function Test-RuntimeImports($Python, $AppDir) {
  $oldPath = $env:PATH
  $nativeBin = Join-Path (Split-Path -Parent $Python) "Library\bin"
  try {
    $env:PATH = "$nativeBin;$oldPath"
    & $Python -E -s -B -c 'import sys; sys.path.insert(0, sys.argv[1]); import app_main, torch; from modelscope import snapshot_download; from qwen_tts import Qwen3TTSModel' $AppDir
    if ($LASTEXITCODE -ne 0) {
      throw "Runtime imports failed for $Python. Install the required packages into that environment (not the user site) before packing."
    }
  } finally {
    $env:PATH = $oldPath
  }
}

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
$Stage = Assert-DistPath $Stage
$CacheDir = Assert-DistPath $CacheDir
if (-not (Test-Path $Conda))                              { throw "conda not found: $Conda (use -CondaRoot to point at the miniconda root)" }
if (-not (Test-Path (Join-Path $EnvPath "python.exe")))   { throw "conda env '$EnvName' not found: $EnvPath" }
if (-not (Test-Path (Join-Path $ProjectRoot "app\ui.py"))){ throw "run this from the project root (app\ui.py is missing)" }
if (-not (Test-Path (Join-Path $ProjectRoot "Start EasyVoice.bat"))) { throw "Start EasyVoice.bat is missing" }
Test-RuntimeImports (Join-Path $EnvPath "python.exe") $ProjectRoot
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
Remove-DistTree $Stage
New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
Ok "cleaned and created $Stage"

# ---- 3. conda-pack the env -> runtime\ ---------------------------------------
Step 3 "Pack the conda env (about 5GB, takes a few minutes)"
$packZip = Assert-DistPath (Join-Path $Dist "runtime.zip")
if (Test-Path -LiteralPath $packZip) { Remove-Item -LiteralPath $packZip -Force }
& $Conda run -n base conda-pack -p $EnvPath -o "$packZip" --format zip --n-threads -1 --ignore-missing-files --force
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $packZip)) { throw "conda-pack failed" }

Write-Host "  Extracting runtime ..."
if     ($SevenZip) { & $SevenZip x "$packZip" "-o$RuntimeDir" -y | Out-Null; if ($LASTEXITCODE -ne 0) { throw "7z extract failed" } }
elseif ($UseTar)   { & tar.exe -xf "$packZip" -C "$RuntimeDir";              if ($LASTEXITCODE -ne 0) { throw "tar extract failed" } }
else               { Expand-Archive -Path $packZip -DestinationPath $RuntimeDir -Force }
Remove-Item -LiteralPath (Assert-DistPath $packZip) -Force
if (-not (Test-Path (Join-Path $RuntimeDir "python.exe")))                 { throw "bad runtime extract: python.exe missing" }
if (-not (Test-Path (Join-Path $RuntimeDir "Scripts\conda-unpack.exe")))   { throw "bad runtime extract: conda-unpack.exe missing" }
Ok "runtime\ ready (Python 3.12 + torch + qwen-tts + gradio)"

# ---- 4. Copy the program + launcher ------------------------------------------
Step 4 "Copy app/ and the launcher"
Copy-Item (Join-Path $ProjectRoot "app")         (Join-Path $Stage "app") -Recurse -Force
Copy-Item (Join-Path $ProjectRoot "app_main.py") $Stage -Force
# The bundled docs (README / DEVELOPMENT / CHANGELOG) link to these files and
# images. Leave one out and the corresponding relative link points at a file
# that does not exist once the bundle is extracted. Adding a relative link to
# the README (or to a doc it links) means adding the target here too.
foreach ($f in @(
    "README.md", "README.en.md",
    "DEVELOPMENT.md", "DEVELOPMENT.en.md",
    "CHANGELOG.md", "CHANGELOG.en.md",
    "LICENSE", "requirements.txt",
    "docs\ARCHITECTURE.md", "docs\SPIKE-qwen-tts.md",
    "assets\brand\screenshot.png", "assets\brand\screenshot.en.png",
    "assets\packaging\THIRD-PARTY-NOTICES.txt")) {
  $p = Join-Path $ProjectRoot $f
  if (-not (Test-Path $p)) { Write-Warning "missing $f -- the bundled README's link to it will break"; continue }
  $dest    = Join-Path $Stage $f
  $destDir = Split-Path $dest -Parent
  if (-not (Test-Path $destDir)) { New-Item -ItemType Directory -Force -Path $destDir | Out-Null }
  Copy-Item $p $dest -Force
}
# Drop any __pycache__ that came along
Get-ChildItem -LiteralPath (Join-Path $Stage "app") -Recurse -Directory -Filter "__pycache__" |
  ForEach-Object { Remove-DistTree $_.FullName }
# Launcher: copy with forced CRLF + UTF-8 (no BOM) so cmd runs the .bat correctly
$batText = (Get-Content (Join-Path $ProjectRoot "Start EasyVoice.bat") -Raw -Encoding UTF8) -replace "`r?`n", "`r`n"
[IO.File]::WriteAllText((Join-Path $Stage "Start EasyVoice.bat"), $batText, (New-Object Text.UTF8Encoding($false)))
Ok "app/, app_main.py, Start EasyVoice.bat, README / DEVELOPMENT / CHANGELOG / LICENSE, docs/ and assets/ are in place"
Test-RuntimeImports (Join-Path $RuntimeDir "python.exe") $Stage

# ---- 5. Model weights (0.6B) + license notices -------------------------------
if ($Variant -eq "cpu") {
  Step 5 "CPU lite bundle: skipping the bundled model (downloaded in-app on first launch)"
  Copy-Item (Join-Path $ProjectRoot "assets\packaging\THIRD-PARTY-NOTICES.txt") `
            (Join-Path $Stage "THIRD-PARTY-NOTICES.txt") -Force
  Ok "model skipped; third-party notices placed"
} else {
  Step 5 "Prepare model weights (0.6B)"
  $modelDir = Join-Path $Stage "models\Qwen\Qwen3-TTS-12Hz-0___6B-Base"
  $envPython = Join-Path $EnvPath "python.exe"
  $srcModel = & $envPython -E -s -B -c 'import sys; sys.path.insert(0, sys.argv[1]); from app.tts_engine import resolve_model_dir; print(resolve_model_dir(sys.argv[2]))' $ProjectRoot $ModelId
  if ($LASTEXITCODE -ne 0) { throw "model lookup failed" }
  if ($srcModel -ne $ModelId) {
    Write-Host "  Copying the already-downloaded model ..."
    robocopy "$srcModel" "$modelDir" /E /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "model copy failed (robocopy=$LASTEXITCODE)" }
  } else {
    Write-Host "  No local model; downloading via modelscope into the stage directory ..."
    & $envPython -E -s -B -c 'import sys; from modelscope import snapshot_download; snapshot_download(sys.argv[1], local_dir=sys.argv[2], max_workers=1)' $ModelId $modelDir
    if ($LASTEXITCODE -ne 0) { throw "model download failed" }
  }
  # Apache-2.0: place the full license text inside the model directory
  # (redistribution obligation)
  $apacheCache = Assert-DistPath (Join-Path $CacheDir "LICENSE-Apache-2.0.txt")
  if (-not (Test-Path $apacheCache)) {
    New-Item -ItemType Directory -Force -Path (Split-Path $apacheCache) | Out-Null
    Invoke-WebRequest -Uri "https://www.apache.org/licenses/LICENSE-2.0.txt" -OutFile $apacheCache -UseBasicParsing
  }
  Copy-Item $apacheCache (Join-Path $modelDir "LICENSE") -Force
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

# ---- 6.5 FFmpeg tools (needed for speed control and video export) -------------
Step "6.5" "Prepare ffmpeg and ffprobe"
$ffDir = Join-Path $Stage "ffmpeg"
# https://github.com/GyanD/codexffmpeg/releases/tag/9.0.2 (Essentials ZIP digest)
$ffmpegVersion = "9.0.2"
$ffmpegSha256 = "60f467265b1e312373dbcd92200c2618a74850f98d3d078e94296bb3fa2047ba"
Install-BundledFfmpeg $ffDir $CacheDir $ffmpegVersion $ffmpegSha256
Ok "ffmpeg and ffprobe $ffmpegVersion and their GPLv3 license bundled"

# ---- 7. Compress into the bundle archive -------------------------------------
Step 7 "Compress into the bundle archive (slow)"
$zipPath = Assert-DistPath (Join-Path $Dist "$DistName.zip")
if (Test-Path -LiteralPath $zipPath) { Remove-Item -LiteralPath $zipPath -Force }
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
