"""Prepare EasyVoice bundles and publish a verified pair of Windows assets."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
VARIANTS = ("cpu", "gpu")
PART_SIZE = 1_900_000_000
ASSET_LIMIT = 2_000_000_000
VERSION = r"v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)"


def release_notes(root, tag):
    if not re.fullmatch(VERSION, tag):
        raise ValueError("Release tag must be a stable version such as v1.2.0")
    sections = []
    for filename in ("CHANGELOG.md", "CHANGELOG.en.md"):
        changelog = (root / filename).read_text(encoding="utf-8")
        match = re.search(rf"^## ({VERSION})[^\S\n]*\n(.*?)(?=^## |\Z)", changelog, re.M | re.S)
        if match is None or match[1] != tag or not match[2].strip():
            raise ValueError(f"The newest release section in {filename} must be a nonempty '## {tag}'")
        sections.append(match[2].strip())
    return f"## 简体中文\n\n{sections[0]}\n\n## English\n\n{sections[1]}"


def bundle_name(version, variant):
    return f"EasyVoice-{version}" + ("-cpu" if variant == "cpu" else "")


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def merge_script(stem, parts):
    sources = "+".join(f'"{part.name}"' for part in parts)
    temporary = f"{stem}.zip.partial"
    return (
        '@echo off\nsetlocal\ncd /d "%~dp0"\n'
        f'copy /b /y {sources} "{temporary}" >nul\n'
        'if errorlevel 1 goto failed\n'
        f'tar.exe -xf "{temporary}"\n'
        'if errorlevel 1 goto failed\n'
        f'del "{temporary}"\necho Extraction complete.\npause\nexit /b 0\n'
        f':failed\nif exist "{temporary}" del "{temporary}"\n'
        'echo Merge or extraction failed. Check that all volumes are in this folder.\n'
        'pause\nexit /b 1\n'
    )


def variant_assets(directory, version, variant):
    stem = bundle_name(version, variant)
    archive = directory / f"{stem}.zip"
    parts = sorted(directory.glob(f"{archive.name}.*"))
    merge = directory / "merge-and-extract.bat"
    if archive.is_file():
        if parts or (variant == "gpu" and merge.exists()):
            raise ValueError(f"Mixed ZIP and split volumes: {stem}")
        files = [archive]
    else:
        expected = [f"{archive.name}.{i:02d}" for i in range(1, len(parts) + 1)]
        if variant != "gpu" or len(parts) < 2 or [p.name for p in parts] != expected:
            raise ValueError(f"Missing ZIP or non-contiguous volumes: {stem}")
        if not merge.is_file() or merge.read_text(encoding="ascii") != merge_script(stem, parts):
            raise ValueError(f"Merge script does not match the volumes: {stem}")
        files = [*parts, merge]
    for path in files:
        if not path.is_file() or not 0 < path.stat().st_size < ASSET_LIMIT:
            raise ValueError(f"Empty or oversized asset: {path.name}")
    return files


def manifest(directory, version, variant, *, write=False):
    files = variant_assets(directory, version, variant)
    sums = {path.name: digest(path) for path in files}
    path = directory / f"SHA256SUMS-{variant}.txt"
    content = "".join(f"{sha}  {name}\n" for name, sha in sums.items())
    if write:
        path.write_text(content, encoding="ascii", newline="\n")
    elif path.read_text(encoding="ascii") != content:
        raise ValueError(f"Checksum mismatch: {path.name}")
    sums[path.name] = digest(path)
    return sums


def check_assets(directory, version):
    sums = {}
    for variant in VARIANTS:
        sums.update(manifest(directory, version, variant))
    if {path.name for path in directory.iterdir()} != sums.keys():
        raise ValueError("Unexpected release assets")
    return sums


def stage_archive(archive, destination, version, variant):
    stem = bundle_name(version, variant)
    if archive.name != f"{stem}.zip":
        raise ValueError(f"Expected {stem}.zip")
    size = archive.stat().st_size
    if variant == "cpu" and size >= ASSET_LIMIT:
        raise ValueError("CPU bundle exceeds the single-file limit")
    destination.mkdir()
    if size < ASSET_LIMIT:
        archive.replace(destination / archive.name)
    else:
        parts = []
        with archive.open("rb") as source:
            for i, offset in enumerate(range(0, size, PART_SIZE), 1):
                path = destination / f"{archive.name}.{i:02d}"
                with path.open("xb") as target:
                    remaining = min(PART_SIZE, size - offset)
                    while remaining:
                        chunk = source.read(min(4 * 1024 * 1024, remaining))
                        if not chunk:
                            raise ValueError(f"Unexpected end of {archive.name}")
                        target.write(chunk)
                        remaining -= len(chunk)
                parts.append(path)
        (destination / "merge-and-extract.bat").write_text(
            merge_script(stem, parts), encoding="ascii", newline="\r\n"
        )
    manifest(destination, version, variant, write=True)


def smoke_test(archive, version, variant):
    stem = bundle_name(version, variant)
    if archive.name != f"{stem}.zip":
        raise ValueError(f"Expected {stem}.zip")
    required = (
        "Start EasyVoice.bat", "app_main.py", "runtime/python.exe", "runtime/Scripts/conda-unpack.exe",
        "ffmpeg/ffmpeg.exe", "ffmpeg/ffprobe.exe", "ffmpeg/COPYING.GPLv3.txt",
        "THIRD-PARTY-NOTICES.txt",
    )
    with tempfile.TemporaryDirectory(prefix="portable test ", dir=archive.parent) as temporary:
        with ZipFile(archive) as bundle:
            if not {f"{stem}/{name}" for name in required} <= set(bundle.namelist()):
                raise ValueError(f"Incomplete portable archive: {archive.name}")
            # Extract every file to validate ZIP CRCs and exercise relocation.
            bundle.extractall(temporary)
        package = Path(temporary) / stem
        runtime = package / "runtime"
        system = Path(os.environ["SystemRoot"])
        env = {
            **{key: value for key, value in os.environ.items() if not key.startswith(("CONDA_", "_CONDA_"))},
            "PATH": os.pathsep.join(map(str, (runtime / "Library/bin", system / "System32", system))),
            "MODELSCOPE_CACHE": str(package / "models"),
            "HF_HUB_OFFLINE": "1",
            "CUDA_VISIBLE_DEVICES": "-1",
        }
        subprocess.run([runtime / "Scripts/conda-unpack.exe"], cwd=package, env=env, check=True)
        subprocess.run(
            [runtime / "python.exe", "-E", "-s", "-B", "-X", "utf8", ROOT / "packaging/verify_bundle.py", variant],
            cwd=package, env=env, check=True,
        )


def gh(*args):
    result = subprocess.run(["gh", *args], check=False, capture_output=True, text=True, encoding="utf-8")
    if result.returncode:
        raise RuntimeError(f"gh {' '.join(args[:2])} failed: {result.stderr}")
    return result.stdout


def check_uploaded(directory, sums, assets):
    if {asset["name"] for asset in assets} != sums.keys() or len(assets) != len(sums):
        raise ValueError("Remote release has missing or unexpected assets")
    for asset in assets:
        name = asset["name"]
        if (asset["state"] != "uploaded" or asset["size"] != (directory / name).stat().st_size
                or asset.get("digest") != f"sha256:{sums[name]}"):
            raise ValueError(f"Uploaded asset verification failed: {name}")


def publish(root, directory, tag, sha):
    notes = release_notes(root, tag)
    sums = check_assets(directory, tag)
    repo = os.environ["GH_REPO"]
    marker = f"<!-- easyvoice-ci:{sha} -->"

    def check_tag():
        remote = json.loads(gh("api", f"repos/{repo}/commits/{tag}"))
        if remote["sha"] != sha:
            raise ValueError("Release tag moved away from the tested commit")

    def find_release():
        raw = gh("api", f"repos/{repo}/releases", "--paginate", "--jq", f'.[] | select(.tag_name == "{tag}")')
        return json.loads(raw) if raw else None

    check_tag()
    release = find_release()
    if release and not release["draft"]:
        check_uploaded(directory, sums, release["assets"])
        print(f"{tag} is already published with these exact assets")
        return
    if release:
        if marker not in (release.get("body") or ""):
            raise ValueError("Refusing to overwrite a draft created outside this CI build")
        if {asset["name"] for asset in release["assets"]} - sums.keys():
            raise ValueError("Existing draft contains unexpected assets")
    else:
        gh("release", "create", tag, "--verify-tag", "--target", sha, "--draft",
           "--title", tag, "--notes", f"{marker}\n\n{notes}")
    gh("release", "upload", tag, *(str(directory / name) for name in sums), "--clobber")
    release = find_release()
    if not release or not release["draft"] or marker not in (release.get("body") or ""):
        raise ValueError("CI draft changed during upload")
    check_uploaded(directory, sums, release["assets"])
    check_tag()
    gh("release", "edit", tag, "--draft=false", "--verify-tag")
    print(f"Published {tag} with {len(sums)} verified assets")


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    version = commands.add_parser("version")
    version.add_argument("tag")
    package = commands.add_parser("package")
    package.add_argument("--archive", type=Path, required=True)
    package.add_argument("--directory", type=Path, required=True)
    package.add_argument("--version", required=True)
    package.add_argument("--variant", choices=VARIANTS, required=True)
    release = commands.add_parser("publish")
    release.add_argument("--tag", required=True)
    release.add_argument("--sha", required=True)
    release.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "version":
        release_notes(ROOT, args.tag)
    elif args.command == "package":
        if not re.fullmatch(rf"(?:{VERSION}|build-[0-9a-f]{{12}})", args.version):
            parser.error("Invalid bundle version")
        smoke_test(args.archive.resolve(), args.version, args.variant)
        stage_archive(args.archive, args.directory, args.version, args.variant)
    else:
        if not re.fullmatch(r"[0-9a-f]{40}", args.sha):
            parser.error("publish requires a full commit SHA")
        publish(ROOT, args.directory, args.tag, args.sha)


if __name__ == "__main__":
    main()
