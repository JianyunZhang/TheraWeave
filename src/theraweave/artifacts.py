"""Checksummed local run archives shared by assessment, plans and feedback."""
from __future__ import annotations

import shutil
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .contract import safe_output_path
from .core import content_id, read_json, sha256_file, write_json, publish_directory, software_fingerprint


def read_archive(directory: str | Path, expected_format: str) -> tuple[Path, dict]:
    root = Path(directory).resolve()
    manifest_path = root / "manifest.json"
    if not manifest_path.resolve().is_relative_to(root):
        raise ValueError("Archive manifest escapes its directory.")
    manifest = read_json(manifest_path)
    if (not isinstance(manifest, dict) or manifest.get("format") != expected_format or manifest.get("format_version") != "0.1"
            or manifest.get("status") != "complete"):
        raise ValueError(f"Expected a complete {expected_format} 0.1 archive.")
    if not isinstance(manifest.get("run_id"), str) or not isinstance(manifest.get("files"), list):
        raise ValueError("Archive must declare its run ID and checksummed file list.")
    seen = set()
    for entry in manifest["files"]:
        if (not isinstance(entry, dict) or not isinstance(entry.get("path"), str)
                or not isinstance(entry.get("sha256"), str) or type(entry.get("size")) is not int or entry["size"] < 0):
            raise ValueError("Invalid archive file record.")
        name = entry["path"]
        if name.casefold() in seen or name == "manifest.json":
            raise ValueError("Duplicate or self-referencing archive entry.")
        seen.add(name.casefold())
        path = safe_output_path(root, name)
        if path.stat().st_size != entry["size"] or sha256_file(path) != entry["sha256"]:
            raise ValueError(f"Archive integrity check failed: {name}")
    for required in ("context.json",):
        if required not in seen:
            raise ValueError(f"Archive does not checksum required file: {required}")
    return root, manifest


def read_member(root: Path, manifest: dict, name: str):
    if name not in {entry["path"] for entry in manifest["files"]}:
        raise ValueError(f"Required file is not in the archive manifest: {name}")
    return read_json(safe_output_path(root, name))


@contextmanager
def new_archive(destination: str | Path, *, format_name: str, identity: dict, forbidden_roots=()):
    from . import __version__

    target = Path(destination).absolute()
    if target.exists() or target.is_symlink():
        raise FileExistsError(f"Output already exists: {target}")
    parent = target.parent.resolve()
    target = parent / target.name
    if any(target.is_relative_to(Path(p).resolve()) or Path(p).resolve().is_relative_to(target) for p in forbidden_roots):
        raise ValueError("Output must be separate from its source archives.")
    parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{target.name}-", dir=parent)).resolve()
    try:
        yield temporary
        outputs = [{"path": p.relative_to(temporary).as_posix(), "size": p.stat().st_size, "sha256": sha256_file(p)}
                   for p in sorted(temporary.rglob("*")) if p.is_file()]
        fingerprint = software_fingerprint()
        write_json(temporary / "manifest.json", {
            "format": format_name, "format_version": "0.1", "status": "complete",
            "run_id": format_name.split(".")[-1] + "-" + content_id([identity, __version__, fingerprint])[:24],
            "created_at": datetime.now(timezone.utc).isoformat(), "software_version": __version__,
            "software_fingerprint": fingerprint,
            "network_used": False, "identity": identity, "files": outputs,
        })
        if target.exists():
            raise FileExistsError(f"Output appeared while publishing: {target}")
        publish_directory(temporary, target)
    finally:
        if temporary.exists():
            if temporary.parent != parent or not temporary.name.startswith(f".{target.name}-"):
                raise RuntimeError("Unexpected temporary directory; refusing cleanup.")
            shutil.rmtree(temporary)
