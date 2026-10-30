"""Run the actual upstream writer in a subprocess, then the independent reader.

This is a local developer integration check on synthetic data. It never writes
into the upstream checkout, installs its package, or claims real-study validation.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from theraweave import DiscoveryProject
from theraweave.contract import snapshot
from theraweave.core import read_json, sha256_file, write_json

WRITER = r'''
import sys
sys.dont_write_bytecode = True
from pathlib import Path
import pandas as pd
from omicsweave.contract import RunManifest, file_record, write_differential, write_manifest, export_json_schema
root = Path(sys.argv[1])
root.mkdir(parents=True)
path = root / "omics" / "transcriptomics" / "tables" / "differential.parquet"
frame = pd.DataFrame({
    "contrast_id": ["disease_vs_reference", "disease_vs_reference"],
    "contrast_role": ["disease_effect", "disease_effect"],
    "tissue": ["liver", "liver"], "omics": ["transcriptomics", "transcriptomics"],
    "feature_id": ["SYNTHETIC_A", "SYNTHETIC_B"], "log2fc": [1.2, -0.4],
    "pvalue": [0.001, 0.3], "padj": [0.002, 0.4], "padj_method": ["fdr_bh", "fdr_bh"],
    "n_numerator": [4, 4], "n_denominator": [4, 4], "method": ["synthetic", "synthetic"]})
write_differential(frame, path)
record = file_record(path, root, "output", kind="differential")
manifest = RunManifest(run_id="synthetic_upstream_writer_001", project_id="synthetic_study",
    experiment_id="synthetic_experiment", omics=["transcriptomics"], files=[record])
write_manifest(manifest, root)
print("actual upstream write_differential / RunManifest / file_record / write_manifest completed")
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    upstream = args.upstream.resolve()
    for relative, expected in snapshot()["source_hashes"].items():
        if sha256_file(upstream / relative) != expected:
            raise SystemExit(f"Upstream drift: {relative}. Review and recapture before claiming compatibility.")
    root = args.output.resolve()
    if root.is_relative_to(upstream) or upstream.is_relative_to(root):
        raise SystemExit("Integration output must be separate from the upstream checkout.")
    root.mkdir(parents=True, exist_ok=False)
    env = {**os.environ, "PYTHONPATH": str(upstream / "src"), "PYTHONDONTWRITEBYTECODE": "1"}
    result = subprocess.run([sys.executable, "-c", WRITER, str(root / "upstream_bundle")],
                            env=env, capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise SystemExit(result.stderr)
    context = {"context_id": "synthetic_upstream_writer_check", "source_taxon_id": 10090,
               "disease_or_phenotype": "synthetic metabolic model", "primary_endpoint": "synthetic endpoint",
               "experimental_unit": "animal",
               "feature_namespaces": {"transcriptomics": {"namespace": "demo", "entity_type": "gene"}}}
    write_json(root / "context.json", context)
    project = DiscoveryProject.from_bundle(root / "upstream_bundle", context=root / "context.json", allow_draft=True)
    archive = project.write_evidence_report(root / "theraweave_archive")
    summary = {"actual_upstream_writer": True, "source_hashes_match": True, "synthetic_data": True,
               "upstream_contract_version": "0.1", "validation": project.bundle.report.to_dict(),
               "output_counts": read_json(archive / "manifest.json")["counts"],
               "real_study_compatibility": "not_tested"}
    write_json(root / "compatibility_result.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
