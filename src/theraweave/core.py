"""Diagnostics and deterministic local serialization shared by import/reporting."""
from __future__ import annotations

import hashlib
import json
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

_ON_WINDOWS = sys.platform == "win32"


def publish_directory(temporary: Path, target: Path) -> None:
    """Bounded retries for transient Windows rename/access conflicts only."""
    delays = (0.05, 0.1, 0.2, 0.4)
    for attempt in range(len(delays) + 1):
        if target.exists() or target.is_symlink():
            raise FileExistsError(f"Output appeared during publication: {target}")
        try:
            temporary.rename(target)
            return
        except PermissionError as error:
            if (not _ON_WINDOWS or getattr(error, "winerror", None) not in {5, 32, 33}
                    or attempt == len(delays)):
                raise
            time.sleep(delays[attempt])


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def content_id(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def software_fingerprint() -> str:
    """Identify actual package code/schema bytes even for uncommitted dev builds."""
    root = Path(__file__).parent
    entries = [(path.relative_to(root).as_posix(), sha256_file(path))
               for path in sorted(root.rglob("*"))
               if path.is_file() and (path.suffix in {".py", ".json"} or path.name == "LICENSE")]
    return content_id(entries)


def parse_json(text: str) -> Any:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError(f"Non-finite JSON number: {value}")

    return json.loads(text, object_pairs_hook=pairs,
                      parse_constant=invalid_constant)


def read_json(path: Path) -> Any:
    return parse_json(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n",
                    encoding="utf-8")


@dataclass(frozen=True)
class Diagnostic:
    rule_id: str
    severity: str
    file: str
    message: str
    field: str | None = None
    row_or_record_id: str | int | None = None
    suggested_action: str = "Inspect the source record and regenerate the bundle."


@dataclass
class ValidationReport:
    diagnostics: list[Diagnostic] = field(default_factory=list)
    files_checked: int = 0
    rows_checked: int = 0
    duplicate_rows: int = 0

    @property
    def valid(self) -> bool:
        return not any(d.severity == "error" for d in self.diagnostics)

    def add(self, rule_id: str, severity: str, file: str, message: str, **kwargs) -> None:
        self.diagnostics.append(Diagnostic(rule_id, severity, file, message, **kwargs))

    def to_dict(self) -> dict:
        return {"valid": self.valid, **asdict(self)}


class BundleValidationError(ValueError):
    def __init__(self, report: ValidationReport):
        self.report = report
        super().__init__("Bundle validation failed; inspect the structured diagnostics.")
