"""Explicit maintainer operation: capture an inspected local upstream draft.

This script imports the upstream source only during capture; the distributed
TheraWeave runtime does not import or install OmicsWeave. Run from the repo root.
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import shutil
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve()
    sys.dont_write_bytecode = True  # Never modify the upstream checkout.
    sys.path.insert(0, str(source / "src"))
    from omicsweave import __version__
    from omicsweave.contract import BUNDLE_SCHEMA_VERSION, DIFFERENTIAL_COLUMNS, export_json_schema
    from omicsweave.contract.tables import DIFFERENTIAL_REQUIRED_BY_OMICS, EVIDENCE_LEVELS

    if BUNDLE_SCHEMA_VERSION != "0.1":
        raise SystemExit("Only the inspected draft 0.1 may be captured by this adapter.")
    args.output.mkdir(parents=True, exist_ok=True)
    payloads = {f"{name}.schema.json": value for name, value in export_json_schema().items()}
    payloads["differential.columns.json"] = [dataclasses.asdict(column) for column in DIFFERENTIAL_COLUMNS]
    payloads["differential.rules.json"] = {"required_by_omics": DIFFERENTIAL_REQUIRED_BY_OMICS,
                                          "evidence_levels": list(EVIDENCE_LEVELS)}
    for name, value in payloads.items():
        (args.output / name).write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    shutil.copyfile(source / "LICENSE", args.output / "LICENSE")
    paths = ["src/omicsweave/__init__.py", "src/omicsweave/contract/__init__.py",
             "src/omicsweave/contract/dataset.py", "src/omicsweave/contract/tables.py",
             "src/omicsweave/contract/manifest.py", "src/omicsweave/core/model.py",
             "src/omicsweave/core/provenance.py", "LICENSE"]
    digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    snapshot = {
        "contract_version": BUNDLE_SCHEMA_VERSION,
        "upstream_version": __version__,
        "status": "local_draft_snapshot_not_upstream_release",
        "capture_date": "2026-10-30",
        "source_hashes": {p: digest(source / p) for p in paths},
        "artifact_hashes": {p.name: digest(p) for p in sorted(args.output.iterdir()) if p.name != "snapshot.json"},
    }
    (args.output / "snapshot.json").write_text(json.dumps(snapshot, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"contract_version": BUNDLE_SCHEMA_VERSION, "captured_artifacts": sorted(snapshot["artifact_hashes"])}))


if __name__ == "__main__":
    main()
