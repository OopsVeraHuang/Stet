"""Standard-library packaging for the curated P0 handoff; never includes .git."""
import argparse
import datetime as dt
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = "PACKAGE_MANIFEST.json"


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args])


def safe_name(name):
    if not isinstance(name, str) or not name or "\\" in name or ":" in name:
        raise ValueError("Invalid relative path in package")
    path = PurePosixPath(name)
    if path.is_absolute() or any(p in ("", ".", "..") for p in name.split("/")):
        raise ValueError("Unsafe package path: " + name)
    if path.parts[0] == ".git":
        raise ValueError("Git internals cannot be packaged")
    return name


def manifest_entries(raw):
    entries = json.loads(raw).get("files")
    if not isinstance(entries, list) or not entries:
        raise ValueError("Manifest must contain a nonempty files list")
    result = {}
    for entry in entries:
        name = safe_name(entry["path"])
        if name == MANIFEST or name in result:
            raise ValueError("Duplicate or self-referential manifest entry: " + name)
        if type(entry["bytes"]) is not int or entry["bytes"] < 0:
            raise ValueError("Invalid byte count: " + name)
        if not re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]):
            raise ValueError("Invalid SHA-256: " + name)
        result[name] = entry
    return result


def check_bytes(name, data, entry):
    if len(data) != entry["bytes"] or hashlib.sha256(data).hexdigest() != entry["sha256"]:
        raise ValueError("Missing or modified package bytes: " + name)


def refresh():
    """Use staged Git blob bytes, not Windows checkout line endings."""
    entries, names = [], set()
    for row in git("ls-files", "--stage", "-z").split(b"\0"):
        if not row:
            continue
        header, raw_name = row.split(b"\t", 1)
        mode, oid, stage = header.decode("ascii").split()
        name = safe_name(raw_name.decode("utf-8"))
        if stage != "0" or mode not in ("100644", "100755"):
            raise ValueError("Unmerged or nonregular staged entry: " + name)
        if name in names:
            raise ValueError("Duplicate staged path: " + name)
        names.add(name)
        if name == MANIFEST:
            continue
        data = git("cat-file", "blob", oid)
        entries.append({"path": name, "bytes": len(data),
                        "sha256": hashlib.sha256(data).hexdigest()})
    if not entries:
        raise ValueError("Stage the curated files before refreshing the manifest")
    document = {
        "date": dt.date.today().isoformat(),
        "scope": "P0 curated source and synthetic fixtures; no full application",
        "hash_scope": "exact staged Git blob bytes; manifest itself excluded",
        "files": sorted(entries, key=lambda e: e["path"]),
    }
    (ROOT / MANIFEST).write_bytes((json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(f"Refreshed {MANIFEST}: {len(entries)} files. Stage this manifest, then commit.")


def verify_folder(root):
    root = root.resolve()
    manifest_path = root / MANIFEST
    if manifest_path.is_symlink():
        raise ValueError("Manifest must not be a symlink")
    entries = manifest_entries(manifest_path.read_bytes())
    for name, entry in entries.items():
        candidate = root.joinpath(*PurePosixPath(name).parts)
        if any(p.is_symlink() for p in [candidate, *candidate.parents] if p != root and root in p.parents):
            raise ValueError("Symlink in extracted package: " + name)
        if not candidate.is_file() or not candidate.resolve().is_relative_to(root):
            raise ValueError("Missing or unsafe package file: " + name)
        check_bytes(name, candidate.read_bytes(), entry)
    return len(entries)


def verify_zip(data):
    """Check exact file membership before writing a new archive."""
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        seen, files = set(), set()
        for info in archive.infolist():
            name = safe_name(info.filename.rstrip("/") if info.is_dir() else info.filename)
            if name in seen:
                raise ValueError("Duplicate ZIP path: " + name)
            seen.add(name)
            kind = stat.S_IFMT(info.external_attr >> 16)
            if kind not in (0, stat.S_IFREG, stat.S_IFDIR):
                raise ValueError("Nonregular ZIP member: " + name)
            if not info.is_dir():
                files.add(name)
        if MANIFEST not in files:
            raise ValueError("ZIP has no manifest")
        entries = manifest_entries(archive.read(MANIFEST))
        if files != set(entries) | {MANIFEST}:
            raise ValueError("ZIP members do not match the manifest exactly")
        for name, entry in entries.items():
            check_bytes(name, archive.read(name), entry)
        return len(files)


def build(output):
    if git("status", "--porcelain").strip():
        raise ValueError("Commit curated changes first; build exports committed HEAD only")
    commit = git("rev-parse", "HEAD").decode("ascii").strip()
    output = output.resolve()
    if output.exists():
        raise ValueError("Output already exists; choose a fresh --output path")
    data = git("-c", "core.autocrlf=false", "archive", "--format=zip", "HEAD")
    count = verify_zip(data)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as stream:
        stream.write(data)
    print(json.dumps({"commit": commit, "files_in_zip": count, "bytes": len(data),
                      "sha256": hashlib.sha256(data).hexdigest(), "output": str(output)},
                     ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("refresh", help="Hash staged Git blobs and rewrite the manifest")
    verify = commands.add_parser("verify", help="Check extracted files; Git is not required")
    verify.add_argument("--root", type=Path, default=ROOT)
    package = commands.add_parser("build", help="Export clean committed HEAD and verify its ZIP")
    package.add_argument("--output", type=Path,
                         default=ROOT / "dist" / "Continuity-Prototype01-2026-10-24.zip")
    args = parser.parse_args()
    try:
        if args.command == "refresh":
            refresh()
        elif args.command == "verify":
            print(f"Verified {verify_folder(args.root)} manifest files (manifest itself excluded).")
        else:
            build(args.output)
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError,
            zipfile.BadZipFile) as error:
        print("Package check failed: " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
