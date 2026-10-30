"""Validated evidence import with atomic, non-overwriting publication."""
from __future__ import annotations

import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pyarrow.parquet as pq

from .contract import snapshot, validate_bundle, validate_context
from .core import BundleValidationError, content_id, sha256_file, write_json, publish_directory, software_fingerprint
from .evidence import build_inventory
from .reporting import render_report


class DiscoveryProject:
    def __init__(self, bundle, context):
        self.bundle = bundle
        self.context = context

    @classmethod
    def from_bundle(cls, directory: str | Path, *, context: str | Path, allow_draft: bool = False):
        bundle = validate_bundle(directory, allow_draft=allow_draft)
        parsed_context = validate_context(context, bundle) if bundle.report.valid else {}
        if not bundle.report.valid:
            raise BundleValidationError(bundle.report)
        return cls(bundle, parsed_context)

    def write_evidence_report(self, destination: str | Path) -> Path:
        from . import __version__

        target = Path(destination).absolute()
        if target.exists() or target.is_symlink():
            raise FileExistsError(f"Output already exists; choose a new run directory: {target}")
        parent = target.parent.resolve()
        target = parent / target.name
        if target.is_relative_to(self.bundle.root) or self.bundle.root.is_relative_to(target):
            raise ValueError("Output must not contain or be inside the input bundle.")
        parent.mkdir(parents=True, exist_ok=True)
        temporary = Path(tempfile.mkdtemp(prefix=f".{target.name}-", dir=parent)).resolve()
        try:
            evidence, entities = build_inventory(self.bundle, self.context)
            pq.write_table(evidence, temporary / "evidence_inventory.parquet")
            pq.write_table(entities, temporary / "entity_inventory.parquet")
            write_json(temporary / "context.json", self.context)
            write_json(temporary / "validation_report.json", self.bundle.report.to_dict())
            source_dir = temporary / "source_bundle"
            source_dir.mkdir()
            shutil.copyfile(self.bundle.root / "manifest.json", source_dir / "manifest.json")
            if sha256_file(source_dir / "manifest.json") != self.bundle.manifest_sha256:
                raise ValueError("Input manifest changed after validation; rerun import.")
            expected = {r["path"]: r["sha256"] for r in self.bundle.manifest["files"] if r["role"] == "output"}
            for name, source in self.bundle.output_files.items():
                copied = source_dir / name
                copied.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, copied)
                if sha256_file(copied) != expected[name]:
                    raise ValueError(f"Input changed after validation: {name}; rerun import.")
            html = render_report(self.context, self.bundle.manifest, evidence.to_pylist(), entities.to_pylist(), self.bundle.report.to_dict())
            (temporary / "import_report.html").write_text(html, encoding="utf-8")
            source_snapshot = snapshot()
            write_json(temporary / "contract_snapshot.json", source_snapshot)
            outputs = [{"path": p.relative_to(temporary).as_posix(), "size": p.stat().st_size, "sha256": sha256_file(p)}
                       for p in sorted(temporary.rglob("*")) if p.is_file()]
            identity = {"input_manifest_sha256": self.bundle.manifest_sha256,
                        "context_sha256": content_id(self.context), "adapter": "omicsweave-0.1-preview-1",
                        "snapshot_sha256": content_id(source_snapshot), "software_version": __version__,
                        "software_fingerprint": software_fingerprint()}
            write_json(temporary / "manifest.json", {
                "format": "theraweave.import-preview", "format_version": "0.1", "status": "complete",
                "run_id": "import-" + content_id(identity)[:24],
                "created_at": datetime.now(timezone.utc).isoformat(),
                **identity, "source_bundle_version": "0.1", "network_used": False,
                "synthetic_input": self.bundle.manifest.get("parameters", {}).get("synthetic") is True,
                "counts": {"entities": len(entities), "evidence": len(evidence), "duplicate_rows": self.bundle.report.duplicate_rows},
                "files": outputs,
                "limitations": ["draft_contract", "no_target_ranking", "no_identity_resolution", "no_causal_or_safety_assessment", "independent_replications_unknown"],
            })
            # Directory rename publishes only a complete run. Never replace an
            # existing destination, including a concurrently created directory.
            if target.exists():
                raise FileExistsError(f"Output appeared during import: {target}")
            publish_directory(temporary, target)
            return target
        finally:
            if temporary.exists():
                if temporary.parent != parent or not temporary.name.startswith(f".{target.name}-"):
                    raise RuntimeError("Refusing to remove an unexpected temporary path.")
                shutil.rmtree(temporary)
