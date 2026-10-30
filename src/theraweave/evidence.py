"""Conservative observation inventory; no therapeutic direction inference."""
from __future__ import annotations

import pyarrow as pa

from .contract import ValidatedBundle
from .core import canonical_json, content_id

EVIDENCE_SCHEMA = pa.schema([
    ("evidence_id", pa.string()), ("entity_key", pa.string()),
    ("context_id", pa.string()), ("dependency_group_id", pa.string()),
    ("source_run_id", pa.string()), ("contrast_id", pa.string()),
    ("contrast_role", pa.string()), ("sample_tissue", pa.string()),
    ("omics", pa.string()), ("feature_id", pa.string()),
    ("measurement_basis", pa.string()), ("log2fc", pa.float64()),
    ("effect_size", pa.float64()), ("effect_size_type", pa.string()),
    ("pvalue", pa.float64()), ("padj", pa.float64()),
    ("padj_method", pa.string()), ("method", pa.string()),
    ("n_numerator", pa.int64()), ("n_denominator", pa.int64()),
    ("observed_direction", pa.string()), ("intervention_direction", pa.string()),
    ("result_interpretation", pa.string()), ("stance", pa.string()),
    ("source_statistical_level", pa.string()), ("source_inference_unit", pa.string()), ("source_units", pa.string()),
    ("source_rows_json", pa.string()), ("source_values_json", pa.string()),
])
ENTITY_SCHEMA = pa.schema([
    ("entity_key", pa.string()), ("entity_id", pa.string()),
    ("namespace", pa.string()), ("entity_type", pa.string()),
    ("taxon_id", pa.int64()), ("identity_status", pa.string()),
    ("evidence_ids", pa.list_(pa.string())),
    ("dependency_group_ids", pa.list_(pa.string())),
    ("independent_replications", pa.int64()),
])


def build_inventory(bundle: ValidatedBundle, context: dict) -> tuple[pa.Table, pa.Table]:
    manifest = bundle.manifest
    # Without sample overlap information, do not claim independent replications
    # even between omics. All observations in this experiment share a group.
    group = "experiment-" + content_id([manifest["project_id"], manifest["experiment_id"]])[:20]
    entities, observations = {}, []
    for entry in bundle.rows:
        row = entry["values"]
        mapping = context["feature_namespaces"][row["omics"]]
        entity_key = "entity-" + content_id([context["source_taxon_id"], mapping, row["feature_id"]])[:24]
        evidence_id = "evidence-" + content_id([group, context["context_id"], entity_key, row])[:24]
        entity = entities.setdefault(entity_key, {
            "entity_key": entity_key, "entity_id": row["feature_id"],
            "namespace": mapping["namespace"], "entity_type": mapping["entity_type"],
            "taxon_id": context["source_taxon_id"], "identity_status": "user_asserted_not_resolved",
            "evidence_ids": [], "dependency_group_ids": [group],
            "independent_replications": None,
        })
        entity["evidence_ids"].append(evidence_id)
        effect = row.get("log2fc")
        observed_direction = "unknown" if effect is None else "up" if effect > 0 else "down" if effect < 0 else "none"
        observation = {key: row.get(key) for key in (
            "contrast_id", "contrast_role", "omics", "feature_id", "log2fc", "effect_size",
            "effect_size_type", "pvalue", "padj", "padj_method", "method", "n_numerator", "n_denominator",
        )}
        observation.update({
            "evidence_id": evidence_id, "entity_key": entity_key, "context_id": context["context_id"],
            "dependency_group_id": group, "source_run_id": manifest["run_id"],
            "sample_tissue": row["tissue"], "measurement_basis": "estimated",
            "observed_direction": observed_direction, "intervention_direction": "unknown",
            "result_interpretation": "not_assessed", "stance": "unclear",
            "source_statistical_level": row.get("evidence_level"), "source_inference_unit": row.get("inference_unit"), "source_units": row.get("units"),
            "source_rows_json": canonical_json(sorted(entry["source_rows"], key=lambda v: (v["file"], v["row"]))),
            "source_values_json": canonical_json(row),
        })
        observations.append(observation)
    return (pa.Table.from_pylist(sorted(observations, key=lambda v: v["evidence_id"]), schema=EVIDENCE_SCHEMA),
            pa.Table.from_pylist(sorted(entities.values(), key=lambda v: v["entity_key"]), schema=ENTITY_SCHEMA))
