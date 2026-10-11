#!/usr/bin/env python3
"""Materialize a pinned MIT dependency and apply the project's scoped patch."""
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parent
REVISION = "41c388baef0dd55c0ce4924789abbfde889d9b87"
PATCH = ROOT / "patches/idevice-rsd-xctest.patch"
OUTPUT = ROOT / ".deps/idevice"
stamp = {"revision": REVISION, "patch_sha256": hashlib.sha256(PATCH.read_bytes()).hexdigest(), "isolated_workspace": True}
marker = OUTPUT / ".ipu-source.json"
if marker.exists() and json.loads(marker.read_text()) == stamp:
    print("Pinned RSD dependency ready")
    raise SystemExit(0)
source = os.environ.get("IPU_IDEVICE_SOURCE")
if source:
    source = Path(source).resolve()
    revision = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    clean = subprocess.run(["git", "-C", str(source), "diff", "--quiet", "HEAD", "--", "idevice"]).returncode == 0
    if revision != REVISION or not clean:
        raise SystemExit("Local dependency source must be the clean pinned revision")
if OUTPUT.exists() and not marker.exists():
    raise SystemExit("Refusing to replace an unowned dependency directory")
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="idevice-build-", dir=OUTPUT.parent) as temporary:
    staging = Path(temporary) / "source"
    staging.mkdir()
    if source:
        shutil.copytree(source / "idevice", staging / "idevice", ignore=shutil.ignore_patterns("target"))
        shutil.copy2(source / "LICENSE.txt", staging / "LICENSE.txt")
    else:
        url = f"https://codeload.github.com/leeguooooo/idevice/tar.gz/{REVISION}"
        data = urllib.request.urlopen(url, timeout=60).read()
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
            for member in archive.getmembers():
                parts = Path(member.name).parts[1:]
                if not parts or parts[0] not in ("idevice", "LICENSE.txt"):
                    continue
                if member.isdir():
                    continue
                if member.issym() and tuple(parts) == ("idevice", "README.md") and member.linkname == "../README.md":
                    original = archive.getmember(Path(member.name).parts[0] + "/README.md")
                    if not original.isfile() or original.size > 1_048_576:
                        raise SystemExit("Invalid upstream README")
                    destination = staging.joinpath(*parts)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(archive.extractfile(original).read())
                    continue
                if not member.isfile() or any(p in ("..", "") for p in parts):
                    raise SystemExit("Invalid archive entry")
                destination = staging.joinpath(*parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(archive.extractfile(member).read())
    subprocess.run(["git", "apply", "--directory", str(staging.relative_to(ROOT)), str(PATCH)], cwd=ROOT, check=True)
    manifest = staging / "idevice/Cargo.toml"
    manifest.write_text(manifest.read_text() + "\n[workspace]\n")
    (staging / ".ipu-source.json").write_text(json.dumps(stamp, indent=2) + "\n")
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    staging.rename(OUTPUT)
print("Pinned RSD dependency prepared")
