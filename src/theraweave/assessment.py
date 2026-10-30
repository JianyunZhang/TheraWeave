"""Transparent experimental prioritisation, without an additive success score."""
from __future__ import annotations

from html import escape
from pathlib import Path
import math

import pyarrow as pa
import pyarrow.parquet as pq

from .artifacts import new_archive, read_archive, read_member
from .core import content_id, sha256_file, write_json
from .knowledge import load_snapshots

DEFAULT_POLICY = {"version": "preview-rules-1", "alpha": 0.05, "minimum_abs_log2fc": 0.5, "minimum_biological_n": 3}
BUCKETS = ["functional_validation_ready", "conflict_resolution_first", "evidence_gap_first", "hold_for_review"]


def validate_policy(policy: dict) -> dict:
    if set(policy) != set(DEFAULT_POLICY) or policy["version"] != DEFAULT_POLICY["version"]:
        raise ValueError("Unsupported policy keys or rule version.")
    if any(isinstance(policy[k], bool) or not isinstance(policy[k], (int, float)) or not math.isfinite(policy[k])
           for k in ("alpha", "minimum_abs_log2fc", "minimum_biological_n")):
        raise ValueError("Policy thresholds must be finite numeric values.")
    if not (0 < policy["alpha"] < 1 and 0 <= policy["minimum_abs_log2fc"] < float("inf")):
        raise ValueError("Invalid alpha or effect threshold.")
    if not isinstance(policy["minimum_biological_n"], int) or policy["minimum_biological_n"] < 1:
        raise ValueError("Minimum biological n must be a positive integer.")
    return policy


def _assess(entity: dict, observations: list[dict], knowledge: list[dict], context: dict, policy: dict) -> dict:
    matches = [r for r in knowledge if (r["entity_id"], r["namespace"], r["taxon_id"]) ==
               (entity["entity_id"], entity["namespace"], entity["taxon_id"])]
    applicable = [r for r in matches if r["context_id"] == context["context_id"] or
                  (r["context_id"] is None and r["evidence_type"] in {"identity", "tool"})]
    reviewed = [r for r in applicable if r["reviewed"]]
    positive = lambda kind: [r for r in reviewed if r["evidence_type"] == kind and r["stance"] == "supports"]
    contrary = [r for r in reviewed if r["evidence_type"] in {"functional", "direction"} and r["stance"] == "contradicts"]
    directions = {r["direction"] for r in positive("direction") + positive("functional") if r["direction"] != "unknown"}
    direction_conflict = len(directions) > 1 or bool(contrary)
    local = [r for r in observations if r["entity_key"] == entity["entity_key"]]
    qualified = [r for r in local if r["contrast_role"] == "disease_effect" and
                 r.get("source_statistical_level") not in {"effect_size_only", "insufficient"} and
                 r["padj"] is not None and r["padj"] <= policy["alpha"] and
                 r["log2fc"] is not None and abs(r["log2fc"]) >= policy["minimum_abs_log2fc"] and
                 min(r["n_numerator"], r["n_denominator"]) >= policy["minimum_biological_n"]]
    blocking = [r for r in reviewed if r["evidence_type"] == "risk" and r.get("blocking") and r["stance"] == "supports"]
    dimensions = {
        "local_statistical_evidence": "supported" if qualified else "limited" if local else "unknown",
        "independent_replication": "unknown",
        "mechanistic_evidence": "conflicting" if contrary else "supported" if positive("functional") else "unknown",
        "direction_evidence": "conflicting" if direction_conflict else "supported" if directions else "unknown",
        "context_specificity": "limited",  # bulk/organ labels alone do not establish cell specificity
        "human_translation": "unknown",
        "identity_and_tools": "supported" if positive("identity") and positive("tool") else "limited" if positive("identity") or positive("tool") else "unknown",
        "risk_review": "conflicting" if blocking else "limited" if positive("risk") else "unknown",
    }
    reasons, gaps = [], []
    if not positive("identity"):
        gaps.append("identity_resolution")
    if not positive("tool"):
        gaps.append("validated_perturbation_tool")
    direct_entity = entity["entity_type"] in {"gene", "transcript", "protein"}
    if not direct_entity:
        gaps.append("unambiguous_target_mapping")
    if not qualified:
        gaps.append("local_statistical_precision_or_effect")
    if not directions:
        gaps.append("intervention_direction")
    if not positive("functional"):
        gaps.append("functional_causality")
    gaps.extend(["independent_replication", "human_translation", "cell_type_context"])
    if dimensions["risk_review"] == "unknown":
        gaps.append("safety_information")
    if blocking:
        bucket = "hold_for_review"
        reasons.append("Reviewed risk evidence blocks the specified context; other evidence cannot compensate.")
    elif direction_conflict:
        bucket = "conflict_resolution_first"
        reasons.append("Comparable reviewed evidence conflicts on direction or function.")
    elif qualified and positive("identity") and positive("tool") and direct_entity:
        bucket = "functional_validation_ready"
        reasons.append("Local effect, reviewed identity and an experimental tool support designing a functional test.")
    else:
        bucket = "evidence_gap_first"
        reasons.append("Resolve missing identity, measurement or tool evidence before a functional test.")
    if len(matches) != len(applicable):
        reasons.append("Evidence from a different/unspecified disease context was retained but not used for directional or causal claims.")
    direction = next(iter(directions)) if len(directions) == 1 and not direction_conflict else "unknown"
    return {
        "hypothesis_id": "hypothesis-" + content_id([entity["entity_key"], context["context_id"], direction])[:24],
        "entity_key": entity["entity_key"], "entity_id": entity["entity_id"], "namespace": entity["namespace"],
        "entity_type": entity["entity_type"], "context_id": context["context_id"], "bucket": bucket,
        "intervention_direction": direction, "dimensions": dimensions, "gaps": sorted(set(gaps)), "reasons": reasons,
        "evidence_ids": [r["evidence_id"] for r in local],
        "knowledge_evidence_ids": sorted(r["evidence_id"] for r in applicable),
        "qualifying_local_evidence_ids": sorted(r["evidence_id"] for r in qualified),
        "tool_ids": sorted({r["tool_id"] for r in positive("tool")}),
        "study_family_ids": sorted({r["primary_study_id"] for r in reviewed if r["primary_study_id"]}),
        "coverage": {"known_or_limited_dimensions": sum(v != "unknown" for v in dimensions.values()), "total_dimensions": len(dimensions)},
        "rule_version": policy["version"], "manual_review_required": True,
        "limitations": ["uncalibrated_policy", "no_success_probability", "no_sample_overlap_resolution", "not_a_treatment_recommendation"],
    }


def assess_archive(import_directory, destination, *, snapshot_paths=(), policy=None) -> Path:
    root, manifest = read_archive(import_directory, "theraweave.import-preview")
    context = read_member(root, manifest, "context.json")
    for name in ("entity_inventory.parquet", "evidence_inventory.parquet"):
        if name not in {v["path"] for v in manifest["files"]}:
            raise ValueError(f"Missing checksummed inventory: {name}")
    entities = pq.read_table(root / "entity_inventory.parquet").to_pylist()
    evidence = pq.read_table(root / "evidence_inventory.parquet").to_pylist()
    knowledge = load_snapshots(list(snapshot_paths))
    if any(source["synthetic"] for source in knowledge["sources"].values()) and not manifest.get("synthetic_input"):
        raise ValueError("Synthetic knowledge is accepted only with an explicitly synthetic input bundle.")
    policy = validate_policy(dict(DEFAULT_POLICY) if policy is None else dict(policy))
    assessments = [_assess(entity, evidence, knowledge["records"], context, policy) for entity in entities]
    assessments.sort(key=lambda row: (BUCKETS.index(row["bucket"]), row["entity_key"]))
    sensitivity = []
    removal_sets = [("source", key) for key in sorted(knowledge["sources"])]
    removal_sets += [("study", key) for key in sorted({r["primary_study_id"] for r in knowledge["records"] if r["primary_study_id"]})]
    for mode, key in removal_sets:
        reduced = [r for r in knowledge["records"] if
                   (r["primary_study_id"] != key if mode == "study" else any(ref["source"] != key for ref in r["source_refs"]))]
        for entity, original in zip(entities, [_assess(e, evidence, knowledge["records"], context, policy) for e in entities]):
            changed = _assess(entity, evidence, reduced, context, policy)
            sensitivity.append({"remove_type": mode, "removed": key, "hypothesis_id": original["hypothesis_id"],
                                "original_bucket": original["bucket"], "new_bucket": changed["bucket"],
                                "direction_changed": changed["intervention_direction"] != original["intervention_direction"],
                                "bucket_changed": changed["bucket"] != original["bucket"]})
    # A descriptive baseline, not a retrospective accuracy claim.
    baseline = sorted([{"evidence_id": r["evidence_id"], "feature_id": r["feature_id"], "padj": r["padj"]}
                       for r in evidence if r["contrast_role"] == "disease_effect"],
                      key=lambda r: (r["padj"] is None, r["padj"] if r["padj"] is not None else 1, r["evidence_id"]))
    identity = {"parent_run_id": manifest["run_id"], "input_manifest_sha256": sha256_file(root / "manifest.json"),
                "policy": policy, "knowledge_hash": content_id(knowledge)}
    with new_archive(destination, format_name="theraweave.assessment-preview", identity=identity, forbidden_roots=[root]) as temp:
        write_json(temp / "context.json", context)
        write_json(temp / "assessments.json", assessments)
        write_json(temp / "knowledge.json", knowledge)
        write_json(temp / "policy.json", policy)
        write_json(temp / "sensitivity.json", sensitivity)
        write_json(temp / "baseline.json", {"method": "adjusted_p_descriptive_order", "records": baseline, "accuracy": None})
        write_json(temp / "input_reference.json", {"path": str(root), "manifest_sha256": identity["input_manifest_sha256"],
                                                   "archived_observations": evidence, "archived_entities": entities})
        table_rows = [{k: row[k] for k in ("hypothesis_id", "entity_key", "entity_id", "bucket", "intervention_direction")} for row in assessments]
        pq.write_table(pa.Table.from_pylist(table_rows, schema=pa.schema([(k, pa.string()) for k in ("hypothesis_id", "entity_key", "entity_id", "bucket", "intervention_direction")])), temp / "target_assessments.parquet")
        rendered = "".join("<tr>" + "".join(f"<td>{escape(str(row[k]))}</td>" for k in ("entity_id", "bucket", "intervention_direction", "gaps")) + "</tr>" for row in assessments)
        (temp / "decision_report.html").write_text(
            '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'">'
            '<title>TheraWeave 候选评估预览</title><style>body{font:16px/1.6 system-ui;margin:40px;color:#18332f}td,th{padding:12px;border-bottom:1px solid #ddd}table{border-collapse:collapse}</style>'
            '<h1>候选验证优先级 · 规则预览</h1><p>规则尚未用独立研究校准；分桶表示下一步研究工作。所有候选均需人工审查。安全资料缺失保留为未知。</p>'
            f'<table><tr><th>实体</th><th>下一步</th><th>功能方向</th><th>缺口</th></tr>{rendered}</table>'
            '<p><a href="assessments.json">完整证据画像</a> · <a href="sensitivity.json">来源/研究移除敏感性</a> · <a href="knowledge.json">知识与来源</a></p></html>', encoding="utf-8")
    return Path(destination).resolve()
