import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path
from zipfile import ZipFile

import pytest


ROOT = Path(__file__).resolve().parents[1]
SHA = "a" * 40
TAG = "v1.2.0"


@pytest.fixture
def release():
    spec = importlib.util.spec_from_file_location("easyvoice_release", ROOT / "packaging/release.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def changelogs(tmp_path):
    (tmp_path / "CHANGELOG.md").write_text(f"## 未发布\n\n## {TAG}\n\n- 修复\n", encoding="utf-8")
    (tmp_path / "CHANGELOG.en.md").write_text(f"## Unreleased\n\n## {TAG}\n\n- Fix\n", encoding="utf-8")
    return tmp_path


@pytest.fixture
def assets(release, tmp_path, monkeypatch):
    monkeypatch.setattr(release, "ASSET_LIMIT", 3000)
    monkeypatch.setattr(release, "PART_SIZE", 2000)
    combined = tmp_path / "combined"
    combined.mkdir()
    for variant in release.VARIANTS:
        stem = release.bundle_name(TAG, variant)
        archive = tmp_path / f"{stem}.zip"
        with ZipFile(archive, "w") as bundle:
            data = b"playable fixture" if variant == "cpu" else b"playable fixture" * 350
            bundle.writestr(f"{stem}/sample.wav", data)
        staged = tmp_path / variant
        release.stage_archive(archive, staged, TAG, variant)
        for path in staged.iterdir():
            shutil.copyfile(path, combined / path.name)
    return combined


def test_release_requires_matching_bilingual_notes(release, changelogs):
    notes = release.release_notes(changelogs, TAG)
    assert "- 修复" in notes and "- Fix" in notes
    with pytest.raises(ValueError, match="stable version"):
        release.release_notes(changelogs, "v01.2.0")
    (changelogs / "CHANGELOG.en.md").write_text(f"## {TAG}\n\n## v1.1.2\n- Older", encoding="utf-8")
    with pytest.raises(ValueError, match="CHANGELOG.en.md"):
        release.release_notes(changelogs, TAG)
    (changelogs / "CHANGELOG.en.md").write_text(f"## v1.2.1\n- Newer\n## {TAG}\n- Fix", encoding="utf-8")
    with pytest.raises(ValueError, match="CHANGELOG.en.md"):
        release.release_notes(changelogs, TAG)


def test_split_assets_reproduce_original_archive(release, assets):
    parts = sorted(assets.glob(f"EasyVoice-{TAG}.zip.*"))
    assert len(parts) == 3
    original = assets.parent / f"EasyVoice-{TAG}.zip"
    assert b"".join(p.read_bytes() for p in parts) == original.read_bytes()
    assert release.check_assets(assets, TAG).keys() == {p.name for p in assets.iterdir()}


@pytest.mark.skipif(os.name != "nt", reason="Windows merge script")
def test_generated_merge_script_extracts_and_keeps_parts(assets):
    parts = sorted(assets.glob(f"EasyVoice-{TAG}.zip.*"))
    result = subprocess.run(["cmd.exe", "/d", "/c", "merge-and-extract.bat"],
                            cwd=assets, stdin=subprocess.DEVNULL, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (assets / f"EasyVoice-{TAG}" / "sample.wav").read_bytes() == b"playable fixture" * 350
    assert all(path.is_file() for path in parts)
    assert not list(assets.glob("*.partial"))


@pytest.mark.parametrize("damage", ["missing-part", "bad-digest", "bad-merge", "extra-asset"])
def test_release_rejects_incomplete_or_modified_assets(release, assets, damage):
    part = assets / f"EasyVoice-{TAG}.zip.01"
    if damage == "missing-part":
        part.unlink()
    elif damage == "bad-digest":
        part.write_bytes(b"modified")
    elif damage == "bad-merge":
        (assets / "merge-and-extract.bat").write_bytes(b"invalid")
    else:
        (assets / "unexpected.zip").touch()
    with pytest.raises(ValueError):
        release.check_assets(assets, TAG)


@pytest.mark.parametrize("scenario", ["new", "retry", "published", "bad-upload", "moved-tag", "manual-draft"])
def test_publish_only_opens_verified_ci_draft(release, changelogs, assets, monkeypatch, scenario):
    monkeypatch.setenv("GH_REPO", "owner/repo")
    calls = []
    marker = f"<!-- easyvoice-ci:{SHA} -->"
    remote = {"draft": scenario != "published", "body": marker, "assets": []}
    if scenario == "manual-draft":
        remote["body"] = "Human-written draft"
    sums = release.check_assets(assets, TAG)
    uploaded = [
        {"name": name, "size": (assets / name).stat().st_size, "state": "uploaded", "digest": f"sha256:{sha}"}
        for name, sha in sums.items()
    ]
    if scenario == "bad-upload":
        uploaded[0]["digest"] = "sha256:wrong"
    if scenario == "published":
        remote["assets"] = uploaded

    def fake_gh(*args):
        calls.append(args)
        if args[0] == "api" and "/commits/" in args[1]:
            moved = scenario == "moved-tag" and bool(remote["assets"])
            return json.dumps({"sha": "b" * 40 if moved else SHA})
        if args[0] == "api":
            if scenario == "new" and not any(call[:2] == ("release", "create") for call in calls):
                return ""
            return json.dumps(remote)
        if args[:2] == ("release", "upload"):
            remote["assets"] = uploaded
        return ""

    monkeypatch.setattr(release, "gh", fake_gh)
    if scenario in {"bad-upload", "moved-tag", "manual-draft"}:
        with pytest.raises(ValueError):
            release.publish(changelogs, assets, TAG, SHA)
        assert not any(call[:2] == ("release", "edit") for call in calls)
    else:
        release.publish(changelogs, assets, TAG, SHA)
        if scenario == "published":
            assert all(call[0] == "api" for call in calls)
        else:
            assert calls[-1] == ("release", "edit", TAG, "--draft=false", "--verify-tag")
    assert any(call[:2] == ("release", "create") for call in calls) == (scenario == "new")
