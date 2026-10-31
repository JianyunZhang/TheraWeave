"""Generate a small synthetic draft bundle without installing OmicsWeave."""
from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from .core import sha256_file, write_json


def create_demo(destination: str | Path, *, include_reaction: bool = False) -> Path:
    root = Path(destination).absolute()
    root.mkdir(parents=True, exist_ok=False)
    bundle = root / "bundle"
    data_dir = bundle / "omics" / "transcriptomics" / "tables"
    data_dir.mkdir(parents=True)
    table = pa.table({
        "contrast_id": ["disease_vs_reference", "treated_vs_disease", "disease_vs_reference"],
        "contrast_role": ["disease_effect", "treatment_effect", "disease_effect"],
        "tissue": ["liver"] * 3, "omics": ["transcriptomics"] * 3,
        "feature_id": ["DEMO_GENE_A", "DEMO_GENE_A", "DEMO_GENE_B"],
        "log2fc": pa.array([1.2, -0.8, None], type=pa.float64()),
        "pvalue": pa.array([0.01, 0.03, None], type=pa.float64()),
        "padj": pa.array([0.04, 0.12, None], type=pa.float64()),
        "padj_method": ["fdr_bh"] * 3,
        "n_numerator": pa.array([4, 4, 4], type=pa.int64()),
        "n_denominator": pa.array([4, 4, 4], type=pa.int64()),
        "method": ["synthetic_fixture_not_a_computed_test"] * 3,
    })
    output = data_dir / "differential.parquet"
    pq.write_table(table, output)
    files = [{"path": output.relative_to(bundle).as_posix(), "role": "output", "size": output.stat().st_size,
              "sha256": sha256_file(output), "kind": "differential"}]
    omics = ["transcriptomics"]
    if include_reaction:
        mfa_dir = bundle / "omics" / "mfa" / "tables"
        mfa_dir.mkdir(parents=True)
        flux = pa.table({
            "contrast_id": ["disease_vs_reference"], "contrast_role": ["disease_effect"], "tissue": ["liver"],
            "omics": ["mfa"], "feature_id": ["DEMO_RXN_1"],
            "log2fc": pa.array([1.1], type=pa.float64()), "pvalue": pa.array([0.01], type=pa.float64()),
            "padj": pa.array([0.02], type=pa.float64()), "padj_method": ["fdr_bh"],
            "n_numerator": pa.array([4], type=pa.int64()), "n_denominator": pa.array([4], type=pa.int64()),
            "method": ["synthetic_fixture_not_a_computed_test"], "effect_size": pa.array([1.5], type=pa.float64()),
            "effect_size_type": ["flux_difference"], "mean_numerator": pa.array([3.0], type=pa.float64()),
            "mean_denominator": pa.array([1.5], type=pa.float64()), "units": ["nmol/min/g"],
            "inference_unit": ["animal"], "evidence_level": ["statistical_test"],
        })
        flux_path = mfa_dir / "differential.parquet"
        pq.write_table(flux, flux_path)
        files.append({"path": flux_path.relative_to(bundle).as_posix(), "role": "output", "size": flux_path.stat().st_size,
                      "sha256": sha256_file(flux_path), "kind": "differential"})
        omics.append("mfa")
    write_json(bundle / "manifest.json", {
        "bundle_schema_version": "0.1", "run_id": "synthetic_run_001", "project_id": "synthetic_metabolic_study",
        "experiment_id": "synthetic_experiment", "created_at": "2026-10-30T00:00:00Z",
        "omicsweave_version": "0.1.0.dev0", "python_version": "synthetic_fixture",
        "command": [], "config_sha256": None, "omics": omics,
        "parameters": {"synthetic": True, "generated_by": "theraweave demo"},
        "files": files,
    })
    namespaces = {"transcriptomics": {"namespace": "demo", "entity_type": "gene"}}
    if include_reaction:
        namespaces["mfa"] = {"namespace": "demo_network", "entity_type": "reaction"}
    write_json(root / "context.json", {
        "context_id": "synthetic_context", "source_taxon_id": 10090,
        "disease_or_phenotype": "合成代谢病场景（无真实实验结果）", "primary_endpoint": "合成代谢表型",
        "experimental_unit": "animal", "feature_namespaces": namespaces,
        "notes": "All identifiers and values are synthetic; opposite signs do not establish therapeutic reversal.",
    })
    (root / "README.txt").write_text("Synthetic format fixture, not biological validation.\nSee context.json and bundle/manifest.json.\n", encoding="utf-8")
    create_knowledge_fixtures(root / "knowledge")
    return root


def create_knowledge_fixtures(directory: Path) -> None:
    """Normalized synthetic assertions; never downloaded database content."""
    directory.mkdir(parents=True)
    base = {
        "record_id": "synthetic_record", "primary_record_id": "synthetic:record", "primary_study_id": "synthetic:study",
        "entity_id": "DEMO_GENE_A", "namespace": "demo", "taxon_id": 10090,
        "context_id": None, "evidence_type": "identity", "stance": "supports", "direction": "unknown",
        "reviewed": True, "reviewer": "Synthetic fixture reviewer", "citations": ["urn:synthetic:fixture"],
        "statement": "Synthetic assertion for software testing only.",
    }
    definitions = {
        "UniProt": {**base, "record_id": "identity_A", "primary_record_id": "synthetic:identity_A",
                    "protein_class": "enzyme", "subcellular_location": "intracellular",
                    "statement": "Synthetic intracellular enzyme identity for software testing only."},
        "ChEMBL": {**base, "record_id": "tool_A", "primary_record_id": "synthetic:tool_A", "evidence_type": "tool",
                   "tool_id": "SYNTHETIC_PROBE_A", "modality": "small_molecule", "intervention_mechanism": "inhibition",
                   "statement": "Synthetic small-molecule inhibition tool for software testing only."},
        "OpenTargets": {**base, "record_id": "direction_A", "primary_record_id": "synthetic:direction_A", "evidence_type": "direction",
                        "context_id": "synthetic_context", "direction": "inhibit"},
    }
    for source, record in definitions.items():
        write_json(directory / f"{source}.synthetic.json", {
            "format": "theraweave.knowledge-snapshot", "version": "0.1",
            "source": {"name": source, "release": "synthetic-1", "retrieved_at": "2026-10-30",
                       "origin_url": f"urn:theraweave:synthetic:{source}", "license": "Synthetic fixture, BSD-3-Clause",
                       "synthetic": True, "coverage_notes": "No actual database records included."},
            "records": [record],
        })
