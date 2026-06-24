<#
================================================================================
 build.ps1 — 阶段二：把「易声」打包成"解压双击即用"的整合包（Windows）
================================================================================
 策略：用 conda-pack 打包已验证可用的 `easyvoice` conda 环境（内含 Python 3.12 +
       CUDA 版 torch + qwen-tts + gradio；无 N 卡时 torch 自动退回 CPU）。
       这比把 torch / qwen-tts 重新 pip 装进 python-embed 可靠得多
       （见设计文档 §6 风险表的"退回 Miniconda 便携版"备选）。

 产物：
   dist\易声-v1.0\                ← 整合包目录（可直接拷给用户）
     ├─ runtime\                  ← 内嵌 Python 3.12 + 全部依赖（conda-pack 解包）
     ├─ app\  app_main.py         ← 程序
     ├─ models\Qwen\...0___6B...  ← 预装 0.6B 模型权重
     ├─ voices\ presets\ outputs\ ← 空的用户数据目录
     └─ Start EasyVoice.bat              ← 用户唯一双击的入口
   dist\易声-v1.0.zip             ← 压缩包（托管/分发用）

 用法（在 base 环境的 PowerShell 7 里，于项目根目录执行）：
     pwsh -File build.ps1
   可选参数：
     pwsh -File build.ps1 -EnvName easyvoice -Version v1.0 -CondaRoot D:\miniconda3

 注意：
   - 需要先 `python app_main.py` 跑通过一次（确认 easyvoice 环境可用）。
   - 打包前建议关闭正在运行的 app（占用 7860 端口），避免文件锁定。
   - 产物约 6-8GB，请确保磁盘空间充足。
================================================================================
#>
[CmdletBinding()]
param(
  [string]$EnvName   = "easyvoice",
  [string]$Version   = "v1.0",
  [string]$CondaRoot = "$env:USERPROFILE\miniconda3",
  [string]$ModelId   = "Qwen/Qwen3-TTS-12Hz-0.6B-Base",
  [ValidateSet("gpu","cpu")][string]$Variant = "gpu"
)

$ErrorActionPreference = "Stop"
# native 命令（conda / robocopy / 7z）的非零退出码由我们自己判断，不要自动抛异常
$PSNativeCommandUseErrorActionPreference = $false

$ProjectRoot = $PSScriptRoot
if ($Variant -eq "cpu") {
  if ($EnvName -eq "easyvoice") { $EnvName = "easyvoice-cpu" }   # 未显式指定则用 CPU 环境
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

# 7-Zip 比 PowerShell 的 Compress/Expand-Archive 快很多，且稳妥处理 >4GB（zip64）
$SevenZip = $null
foreach ($c in @("$env:ProgramFiles\7-Zip\7z.exe", "${env:ProgramFiles(x86)}\7-Zip\7z.exe", "7z.exe")) {
  if (Test-Path $c) { $SevenZip = $c; break }
  $g = Get-Command $c -ErrorAction SilentlyContinue
  if ($g) { $SevenZip = $g.Source; break }
}
# bsdtar(Windows 10+ 自带 tar.exe) 也能稳妥处理 >4GB 的 zip，作为无 7-Zip 时的首选回退
$UseTar = [bool](Get-Command tar.exe -ErrorAction SilentlyContinue)

# ---- 0. 预检 -----------------------------------------------------------------
Step 0 "预检环境"
if (-not (Test-Path $Conda))                              { throw "找不到 conda：$Conda（用 -CondaRoot 指定 miniconda 根目录）" }
if (-not (Test-Path (Join-Path $EnvPath "python.exe")))   { throw "找不到 conda 环境 '$EnvName'：$EnvPath" }
if (-not (Test-Path (Join-Path $ProjectRoot "app\ui.py"))){ throw "请在项目根目录运行（缺 app\ui.py）" }
if (-not (Test-Path (Join-Path $ProjectRoot "Start EasyVoice.bat"))) { throw "缺少 Start EasyVoice.bat" }
if (Get-NetTCPConnection -LocalPort 7860 -State Listen -ErrorAction SilentlyContinue) {
  Write-Warning "检测到 7860 端口有 app 在运行，建议先关闭再打包（避免锁定 runtime 文件）。"
}
$zipTool = if ($SevenZip) { "7-Zip" } elseif ($UseTar) { "tar/bsdtar" } else { "PowerShell 内置（较慢）" }
Ok "conda / 环境 / 项目结构就绪；压缩工具：$zipTool"

# ---- 1. 确保 base 有 conda-pack ----------------------------------------------
Step 1 "确保 conda-pack 可用"
& $Conda run -n base python -c "import conda_pack" 2>$null
if ($LASTEXITCODE -ne 0) {
  Write-Host "  安装 conda-pack 到 base（仅用 conda-forge，规避 defaults 渠道的 ToS 限制）..."
  & $Conda install -n base -y --override-channels -c conda-forge conda-pack
  if ($LASTEXITCODE -ne 0) {
    Write-Host "  conda 安装失败，改用 pip 安装 conda-pack ..."
    & $Conda run -n base python -m pip install -q conda-pack
    if ($LASTEXITCODE -ne 0) { throw "conda-pack 安装失败（conda-forge 与 pip 均失败）" }
  }
}
Ok "conda-pack 就绪"

# ---- 2. 准备打包目录 ---------------------------------------------------------
Step 2 "准备打包目录"
if (Test-Path $Stage) { Remove-Item $Stage -Recurse -Force }
New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
Ok "已清理并创建 $Stage"

# ---- 3. conda-pack 打包环境 -> runtime\ --------------------------------------
Step 3 "打包 conda 环境（约 5GB，请耐心，数分钟）"
$packZip = Join-Path $Dist "runtime.zip"
if (Test-Path $packZip) { Remove-Item $packZip -Force }
& $Conda run -n base conda-pack -n $EnvName -o "$packZip" --format zip --n-threads -1 --ignore-missing-files --force
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $packZip)) { throw "conda-pack 打包失败" }

Write-Host "  解压 runtime ..."
if     ($SevenZip) { & $SevenZip x "$packZip" "-o$RuntimeDir" -y | Out-Null; if ($LASTEXITCODE -ne 0) { throw "7z 解压失败" } }
elseif ($UseTar)   { & tar.exe -xf "$packZip" -C "$RuntimeDir";              if ($LASTEXITCODE -ne 0) { throw "tar 解压失败" } }
else               { Expand-Archive -Path $packZip -DestinationPath $RuntimeDir -Force }
Remove-Item $packZip -Force
if (-not (Test-Path (Join-Path $RuntimeDir "python.exe")))                 { throw "runtime 解压异常：缺 python.exe" }
if (-not (Test-Path (Join-Path $RuntimeDir "Scripts\conda-unpack.exe")))   { throw "runtime 解压异常：缺 conda-unpack.exe" }
Ok "runtime\ 就绪（Python 3.12 + torch + qwen-tts + gradio）"

# ---- 4. 复制程序 + 启动器 ----------------------------------------------------
Step 4 "复制 app/ 与启动器"
Copy-Item (Join-Path $ProjectRoot "app")         (Join-Path $Stage "app") -Recurse -Force
Copy-Item (Join-Path $ProjectRoot "app_main.py") $Stage -Force
foreach ($f in @("README.md", "requirements.txt")) {
  $p = Join-Path $ProjectRoot $f
  if (Test-Path $p) { Copy-Item $p $Stage -Force }
}
# 清掉打包进来的 __pycache__
Get-ChildItem (Join-Path $Stage "app") -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
  Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
# 启动器：复制并强制 CRLF + UTF-8(无 BOM)，确保 cmd 正确执行中文 .bat
$batText = (Get-Content (Join-Path $ProjectRoot "Start EasyVoice.bat") -Raw) -replace "`r?`n", "`r`n"
[IO.File]::WriteAllText((Join-Path $Stage "Start EasyVoice.bat"), $batText, (New-Object Text.UTF8Encoding($false)))
Ok "app/、app_main.py、Start EasyVoice.bat 已就位"

# ---- 5. 模型权重（0.6B）+ 许可声明 -------------------------------------------
if ($Variant -eq "cpu") {
  Step 5 "CPU 精简包：跳过内置模型（首次启动时在工具内下载）"
  Copy-Item (Join-Path $ProjectRoot "assets\packaging\THIRD-PARTY-NOTICES.txt") `
            (Join-Path $Stage "THIRD-PARTY-NOTICES.txt") -Force
  Ok "已跳过模型；第三方声明已放置"
} else {
  Step 5 "准备模型权重（0.6B）"
  $srcModelOrg = Join-Path $ProjectRoot "models\Qwen"
  $dstModelOrg = Join-Path $Stage "models\Qwen"
  $modelLeaf   = "Qwen3-TTS-12Hz-0___6B-Base"   # ModelScope 把 '.' 写成 '___'，tts_engine 据此解析
  if (Test-Path (Join-Path $srcModelOrg $modelLeaf)) {
    Write-Host "  复制已下载模型 ..."
    New-Item -ItemType Directory -Force -Path $dstModelOrg | Out-Null
    robocopy "$srcModelOrg" "$dstModelOrg" /E /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "模型复制失败（robocopy=$LASTEXITCODE）" }
  } else {
    Write-Host "  本地无模型，改用 modelscope 下载到打包目录 ..."
    $env:MODELSCOPE_CACHE = (Join-Path $Stage "models")
    & (Join-Path $EnvPath "python.exe") -c "from modelscope import snapshot_download; snapshot_download('$ModelId')"
    if ($LASTEXITCODE -ne 0) { throw "模型下载失败" }
  }
  # Apache-2.0：模型目录内放置完整许可文本（再分发义务）
  $apacheCache = Join-Path $Dist "_cache\LICENSE-Apache-2.0.txt"
  if (-not (Test-Path $apacheCache)) {
    New-Item -ItemType Directory -Force -Path (Split-Path $apacheCache) | Out-Null
    Invoke-WebRequest -Uri "https://www.apache.org/licenses/LICENSE-2.0.txt" -OutFile $apacheCache -UseBasicParsing
  }
  $modelDir = Join-Path $dstModelOrg $modelLeaf
  if (Test-Path $modelDir) { Copy-Item $apacheCache (Join-Path $modelDir "LICENSE") -Force }
  # 顶层第三方许可声明（模型 / FFmpeg / 运行时）——模板随仓库版本控制
  Copy-Item (Join-Path $ProjectRoot "assets\packaging\THIRD-PARTY-NOTICES.txt") `
            (Join-Path $Stage "THIRD-PARTY-NOTICES.txt") -Force
  Ok "模型许可(LICENSE) 与第三方声明(THIRD-PARTY-NOTICES) 已打包"
}

# ---- 6. 用户数据空目录 -------------------------------------------------------
Step 6 "创建用户数据目录"
foreach ($d in @("voices", "presets", "outputs")) {
  New-Item -ItemType Directory -Force -Path (Join-Path $Stage $d) | Out-Null
}
Ok "voices/ presets/ outputs/ 已创建"

# ---- 6.5 ffmpeg（语速功能所需；缺失时 app 会优雅降级）------------------------
Step "6.5" "准备 ffmpeg（语速功能所需）"
$ffDir   = Join-Path $Stage "ffmpeg"
$ffExe   = Join-Path $ffDir "ffmpeg.exe"
$cache   = Join-Path $Dist "_cache"
$cachedFf= Join-Path $cache "ffmpeg.exe"
try {
  New-Item -ItemType Directory -Force -Path $ffDir, $cache | Out-Null
  if (-not (Test-Path $cachedFf)) {
    $url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
    $zip = Join-Path $cache "ffmpeg.zip"
    Write-Host "  下载 ffmpeg 静态构建（约 80MB，仅首次）..."
    Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing
    $tmp = Join-Path $cache "ff_extract"
    if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
    if     ($SevenZip) { & $SevenZip x "$zip" "-o$tmp" -y | Out-Null }
    elseif ($UseTar)   { New-Item -ItemType Directory -Force -Path $tmp | Out-Null; & tar.exe -xf "$zip" -C "$tmp" }
    else               { Expand-Archive -Path $zip -DestinationPath $tmp -Force }
    $found = Get-ChildItem $tmp -Recurse -Filter "ffmpeg.exe" | Select-Object -First 1
    if (-not $found) { throw "解压后未找到 ffmpeg.exe" }
    Copy-Item $found.FullName $cachedFf -Force
    Remove-Item $tmp -Recurse -Force; Remove-Item $zip -Force
  }
  Copy-Item $cachedFf $ffExe -Force
  # FFmpeg 为 GPLv3 构建：随附完整许可文本 + 源代码声明（再分发义务）
  $gplCache = Join-Path $cache "COPYING.GPLv3.txt"
  if (-not (Test-Path $gplCache)) {
    Invoke-WebRequest -Uri "https://www.gnu.org/licenses/gpl-3.0.txt" -OutFile $gplCache -UseBasicParsing
  }
  Copy-Item $gplCache (Join-Path $ffDir "COPYING.GPLv3.txt") -Force
  Copy-Item (Join-Path $ProjectRoot "assets\packaging\ffmpeg-README-LICENSE.txt") `
            (Join-Path $ffDir "README-LICENSE.txt") -Force
  Ok ("ffmpeg.exe + 许可(GPLv3) 已随包（{0} MB）" -f [math]::Round((Get-Item $ffExe).Length/1MB))
} catch {
  Write-Warning "ffmpeg 准备失败：$($_.Exception.Message)；整合包仍可用，但语速≠1.0 将不生效。"
  if (Test-Path $ffDir) { Remove-Item $ffDir -Recurse -Force }
}

# ---- 7. 压缩为整合包 ---------------------------------------------------------
Step 7 "压缩为整合包（耗时较长）"
$zipPath = Join-Path $Dist "$DistName.zip"
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
if ($SevenZip) {
  & $SevenZip a -tzip "$zipPath" "$Stage" -mx=5 | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "7z 压缩失败" }
} elseif ($UseTar) {
  & tar.exe -c -a -f "$zipPath" -C "$Dist" "$DistName"
  if ($LASTEXITCODE -ne 0) { throw "tar 压缩失败" }
} else {
  Write-Warning "用 PowerShell 内置压缩，>4GB 较慢，请耐心 ..."
  Compress-Archive -Path $Stage -DestinationPath $zipPath -CompressionLevel Optimal
}
$zipGB = "{0:N2}" -f ((Get-Item $zipPath).Length / 1GB)
Ok "已生成 $zipPath（$zipGB GB）"

# ---- 完成 --------------------------------------------------------------------
Write-Host "`n全部完成 ✅" -ForegroundColor Green
Write-Host "  整合包目录：$Stage"
Write-Host "  压缩包：    $zipPath  ($zipGB GB)"
Write-Host "`n验收：把 zip 拷到一台【干净的 / 最好无 N 卡的】Windows，解压后双击「Start EasyVoice.bat」，"
Write-Host "      首次会自动初始化(约 1 分钟) + 加载模型(约 30 秒)，随后自动打开浏览器即可用。"
