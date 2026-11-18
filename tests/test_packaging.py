import hashlib
import os
from pathlib import Path
import shutil
import subprocess
from zipfile import ZipFile

import pytest


ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows bundle scripts")


def test_build_rejects_broken_runtime_before_clearing_stage(tmp_path):
    powershell = shutil.which("pwsh") or shutil.which("powershell")
    if not powershell:
        pytest.skip("requires PowerShell")
    shutil.copyfile(ROOT / "build.ps1", tmp_path / "build.ps1")
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "ui.py").touch()
    (tmp_path / "Start EasyVoice.bat").touch()
    conda = tmp_path / "conda"
    (conda / "condabin").mkdir(parents=True)
    (conda / "condabin" / "conda.bat").write_text("@exit /b 99\n")
    env = conda / "envs" / "easyvoice"
    env.mkdir(parents=True)
    shutil.copyfile(shutil.which("where.exe"), env / "python.exe")
    stage = tmp_path / "dist" / "EasyVoice-test"
    stage.mkdir(parents=True)
    sentinel = stage / "previous-build"
    sentinel.touch()

    result = subprocess.run([
        powershell, "-NoProfile", "-File", str(tmp_path / "build.ps1"),
        "-CondaRoot", str(conda), "-Version", "test",
    ], capture_output=True, timeout=30)

    assert result.returncode != 0
    assert b"Runtime imports failed" in result.stdout + result.stderr
    assert sentinel.exists()


def test_bundle_retries_failed_runtime_initialization(tmp_path):
    launcher = tmp_path / "Start EasyVoice.bat"
    launcher.write_bytes((ROOT / launcher.name).read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
    scripts = tmp_path / "runtime" / "Scripts"
    scripts.mkdir(parents=True)
    shutil.copyfile(shutil.which("where.exe"), scripts / "conda-unpack.exe")

    for _ in range(2):
        result = subprocess.run(["cmd.exe", "/d", "/c", "call", launcher.name], cwd=tmp_path,
                                stdin=subprocess.DEVNULL, capture_output=True, timeout=30)
        assert result.returncode == 1
        assert b"Runtime initialization failed" in result.stdout
        assert not (scripts.parent / ".unpacked").exists()


@pytest.fixture
def run_build_phase(tmp_path):
    powershell = shutil.which("pwsh") or shutil.which("powershell")
    if not powershell:
        pytest.skip("requires PowerShell")
    script = tmp_path / "phase.ps1"
    header = r"""
$ErrorActionPreference = 'Stop'
$ProjectRoot = $PSScriptRoot
$Dist = Join-Path $ProjectRoot 'dist'
$ast = [Management.Automation.Language.Parser]::ParseFile($env:EASYVOICE_BUILD_SCRIPT, [ref]$null, [ref]$null)
foreach ($fn in $ast.FindAll({ param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] }, $false)) {
  . ([scriptblock]::Create($fn.Extent.Text))
}
"""

    def run(body, **env):
        script.write_text(header + body, encoding="ascii")
        return subprocess.run([powershell, "-NoProfile", "-File", str(script)], capture_output=True,
                              timeout=30, env={**os.environ, "EASYVOICE_BUILD_SCRIPT": str(ROOT / "build.ps1"), **env})

    return run


@pytest.mark.parametrize(("case", "expected"), [
    ("root", b"Path must be inside dist"),
    ("sibling", b"Path must be inside dist"),
    ("parent traversal", b"Path must be inside dist"),
    ("dist junction", b"Refusing reparse point in dist path"),
    ("parent junction", b"Refusing reparse point in dist path"),
    ("nested junction", b"Refusing reparse point in cleanup tree"),
])
def test_build_rejects_cleanup_outside_dist(tmp_path, run_build_phase, case, expected):
    sibling = tmp_path / "dist-neighbor"
    (sibling / "target").mkdir(parents=True)
    sentinel = sibling / "target" / "keep"
    sentinel.touch()
    result = run_build_phase(r"""
$sibling = Join-Path $ProjectRoot 'dist-neighbor'
if ($env:EASYVOICE_CASE -eq 'dist junction') {
  New-Item -ItemType Junction -Path $Dist -Target $sibling | Out-Null
} else {
  New-Item -ItemType Directory -Path $Dist | Out-Null
}
$target = switch ($env:EASYVOICE_CASE) {
  'root' { $Dist }
  'sibling' { Join-Path $sibling 'target' }
  'parent traversal' { Join-Path $Dist '../dist-neighbor/target' }
  'dist junction' { Join-Path $Dist 'target' }
  'parent junction' {
    New-Item -ItemType Junction -Path (Join-Path $Dist 'linked') -Target $sibling | Out-Null
    Join-Path $Dist 'linked/target'
  }
  'nested junction' {
    $inside = Join-Path $Dist 'target'
    New-Item -ItemType Directory -Path $inside | Out-Null
    New-Item -ItemType Junction -Path (Join-Path $inside 'linked') -Target $sibling | Out-Null
    $inside
  }
}
function Remove-Item { throw 'Deletion intercepted' }
Remove-DistTree $target
""", EASYVOICE_CASE=case)

    assert result.returncode != 0
    assert expected in result.stdout + result.stderr
    assert b"Deletion intercepted" not in result.stdout + result.stderr
    assert sentinel.exists()


def test_build_allows_cleanup_strictly_inside_dist(tmp_path, run_build_phase):
    target = tmp_path / "dist" / "stage"
    (target / "runtime").mkdir(parents=True)
    (target / "runtime" / "old-file").touch()
    keep = tmp_path / "dist" / "keep"
    keep.touch()

    result = run_build_phase("Remove-DistTree (Join-Path $Dist 'stage')")

    assert result.returncode == 0, result.stderr
    assert not target.exists()
    assert keep.exists()


@pytest.mark.parametrize("case", ["verified cache", "corrupt cache", "corrupt download"])
def test_ffmpeg_stage_only_uses_verified_versioned_archive(tmp_path, run_build_phase, case):
    version = "9.0.2"
    name = f"ffmpeg-{version}-essentials_build"
    valid_zip = tmp_path / "valid.zip"
    with ZipFile(valid_zip, "w") as archive:
        archive.writestr(f"{name}/bin/ffmpeg.exe", b"verified fixture")
        archive.writestr(f"{name}/bin/ffprobe.exe", b"verified probe")
        archive.writestr(f"{name}/LICENSE", b"license from pinned archive")
    bad_zip = tmp_path / "corrupt.zip"
    with ZipFile(bad_zip, "w") as archive:
        archive.writestr(f"{name}/bin/ffmpeg.exe", b"unverified fixture")
    digest = hashlib.sha256(valid_zip.read_bytes()).hexdigest()
    cache = tmp_path / "dist" / "_cache"
    cache.mkdir(parents=True)
    (cache / "ffmpeg.exe").write_bytes(b"legacy executable cache")
    (cache / "ffprobe.exe").write_bytes(b"legacy probe cache")
    cached_zip = cache / f"{name}.zip"
    if case != "corrupt download":
        shutil.copyfile(valid_zip if case == "verified cache" else bad_zip, cached_zip)
    notice = tmp_path / "assets" / "packaging" / "ffmpeg-README-LICENSE.txt"
    notice.parent.mkdir(parents=True)
    notice.write_text("build notice", encoding="ascii")

    result = run_build_phase(r"""
function Invoke-WebRequest {
  param($Uri, $OutFile, [switch]$UseBasicParsing, $TimeoutSec)
  if ($env:EASYVOICE_CASE -eq 'verified cache') { throw 'Unexpected network access' }
  $expected = 'https://github.com/GyanD/codexffmpeg/releases/download/9.0.2/ffmpeg-9.0.2-essentials_build.zip'
  if ($Uri -ne $expected) { throw "Unexpected FFmpeg URL: $Uri" }
  Copy-Item -LiteralPath $env:EASYVOICE_DOWNLOAD -Destination $OutFile -Force
}
if ($env:EASYVOICE_CASE -eq 'corrupt download') {
  function Expand-Archive { throw 'Unverified archive reached extraction' }
}
Install-BundledFfmpeg (Join-Path $Dist 'stage/ffmpeg') (Join-Path $Dist '_cache') '9.0.2' $env:EASYVOICE_HASH
""", EASYVOICE_CASE=case, EASYVOICE_HASH=digest,
       EASYVOICE_DOWNLOAD=str(bad_zip if case == "corrupt download" else valid_zip))

    bundled = tmp_path / "dist" / "stage" / "ffmpeg"
    assert not list(cache.glob("ffmpeg-work-*"))
    if case == "corrupt download":
        assert result.returncode != 0
        assert b"FFmpeg download SHA-256 mismatch" in result.stdout + result.stderr
        assert not bundled.exists() and not cached_zip.exists()
    else:
        assert result.returncode == 0, (result.stdout, result.stderr)
        assert (bundled / "ffmpeg.exe").read_bytes() == b"verified fixture"
        assert (bundled / "ffprobe.exe").read_bytes() == b"verified probe"
        assert (bundled / "COPYING.GPLv3.txt").read_bytes() == b"license from pinned archive"
        assert cached_zip.read_bytes() == valid_zip.read_bytes()
