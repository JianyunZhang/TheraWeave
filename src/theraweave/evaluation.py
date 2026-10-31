"""Descriptive comparisons. No labels means no accuracy and no winning method."""
from __future__ import annotations


def _summary(rows: list[dict]) -> dict:
    return {row["entity_id"]: {"bucket": row["bucket"], "intervention_direction": row["intervention_direction"]} for row in rows}


def _changes(full: dict, alternate: dict) -> list[dict]:
    changed = []
    for entity_id in sorted(full):
        if full[entity_id] != alternate[entity_id]:
            changed.append({"entity_id": entity_id, "full": full[entity_id], "alternate": alternate[entity_id]})
    return changed


def _order(evidence: list[dict], key):
    rows = [row for row in evidence if row["contrast_role"] == "disease_effect"]
    return [{"evidence_id": row["evidence_id"], "feature_id": row["feature_id"], "padj": row["padj"], "log2fc": row["log2fc"]}
            for row in sorted(rows, key=key)]


def build_comparisons(entities, evidence, knowledge_records, genetic_records, context, policy, views, assess) -> dict:
    def run(observations, knowledge, genetic):
        return _summary([assess(entity, observations, knowledge, context, policy, views[entity["entity_key"]], genetic) for entity in entities])

    full = run(evidence, knowledge_records, genetic_records)
    without_knowledge = run(evidence, [], [])
    sources = sorted({ref["source"] for record in knowledge_records for ref in record["source_refs"]})
    single_source = []
    for source in sources:
        kept = [record for record in knowledge_records if any(ref["source"] == source for ref in record["source_refs"])]
        single_source.append({"source": source, "bucket_or_direction_changes": _changes(full, run(evidence, kept, genetic_records))})
    mfa = [row for row in evidence if row["omics"] == "mfa"]
    if mfa:
        without_mfa = {"status": "compared", "observations_removed": len(mfa),
                       "bucket_or_direction_changes": _changes(full, run([row for row in evidence if row["omics"] != "mfa"], knowledge_records, genetic_records)),
                       "note": "A change after removing MFA is not evidence that MFA improved target selection."}
    else:
        without_mfa = {"status": "not_applicable", "observations_removed": 0, "bucket_or_direction_changes": [],
                       "note": "This archive has no MFA observations to remove."}
    return {
        "accuracy": None, "labels": None, "ranked_winner": None,
        "interpretation": "Descriptive contrasts only. No labels are present, so no accuracy is calculated.",
        "adjusted_p_order": _order(evidence, lambda row: (row["padj"] is None, row["padj"] if row["padj"] is not None else 1, row["evidence_id"])),
        "absolute_effect_order": _order(evidence, lambda row: (row["log2fc"] is None, -(abs(row["log2fc"]) if row["log2fc"] is not None else 0), row["evidence_id"])),
        "full_rules": [{"entity_id": entity_id, **full[entity_id]} for entity_id in sorted(full)],
        "without_external_knowledge": {"bucket_or_direction_changes": _changes(full, without_knowledge)},
        "single_source": single_source,
        "without_mfa": without_mfa,
    }
