"""Transparent experimental prioritisation, without an additive success score."""
from __future__ import annotations

from html import escape
from pathlib import Path
import math

import pyarrow as pa
import pyarrow.parquet as pq

from .artifacts import new_archive, read_archive, read_member
from .core import content_id, sha256_file, write_json
from .evaluation import build_comparisons
from .genetics import load_genetic_evidence
from .knowledge import load_snapshots
from .mappings import load_ortholog_map, load_reaction_map, ortholog_view, reaction_links
from .modalities import screen_modalities

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


def _applicable(entity: dict, knowledge: list[dict], context: dict) -> list[dict]:
    matches = [row for row in knowledge if (row["entity_id"], row["namespace"], row["taxon_id"]) ==
               (entity["entity_id"], entity["namespace"], entity["taxon_id"])]
    return [row for row in matches if row["context_id"] == context["context_id"] or
            (row["context_id"] is None and row["evidence_type"] in {"identity", "tool"})]


def _translation_gaps(status: str) -> list[str]:
    if status == "reviewed_map":
        return ["human_functional_conservation"]
    if status == "no_human_ortholog":
        return ["no_human_ortholog"]
    if status == "source_taxon_is_human":
        return ["human_disease_relevance"]
    return ["human_ortholog_map", "human_functional_conservation"]


def _sign_pattern(local: list[dict]) -> dict:
    def signs(role: str) -> set[str]:
        return {row["observed_direction"] for row in local if row["contrast_role"] == role and row["observed_direction"] in {"up", "down"}}

    disease, treatment = signs("disease_effect"), signs("treatment_effect")
    if len(disease) == 1 and len(treatment) == 1 and disease != treatment:
        status = "opposite_direction"
    elif len(disease) == 1 and disease == treatment:
        status = "same_direction"
    elif not disease or not treatment:
        status = "not_assessed"
    else:
        status = "discordant"
    return {"status": status, "sets_intervention_direction": False, "establishes_causal_reversal": False,
            "limitations": ["phenotype_response_and_residual_contrast_not_assessed", "shared_controls_not_recorded", "sign_pattern_is_not_restoration"]}


def _assess(entity: dict, observations: list[dict], knowledge: list[dict], context: dict, policy: dict, ortholog: dict, genetic: list[dict]) -> dict:
    applicable = _applicable(entity, knowledge, context)
    matches = [r for r in knowledge if (r["entity_id"], r["namespace"], r["taxon_id"]) ==
               (entity["entity_id"], entity["namespace"], entity["taxon_id"])]
    reviewed = [r for r in applicable if r["reviewed"]]
    positive = lambda kind: [r for r in reviewed if r["evidence_type"] == kind and r["stance"] == "supports"]
    contrary = [r for r in reviewed if r["evidence_type"] in {"functional", "direction"} and r["stance"] == "contradicts"]
    directions = {r["direction"] for r in positive("direction") + positive("functional") if r["direction"] != "unknown"}
    matched_genetic = [row for row in genetic if (row["entity_id"], row["namespace"], row["taxon_id"]) ==
                       (entity["entity_id"], entity["namespace"], entity["taxon_id"]) and row["context_id"] == context["context_id"]]
    directions.update(row["allele_direction"] for row in matched_genetic if row["direction_used"] and row["stance"] == "supports")
    genetic_contrary = [row for row in matched_genetic if row["direction_used"] and row["stance"] == "contradicts"]
    direction_conflict = len(directions) > 1 or bool(contrary) or bool(genetic_contrary)
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
        "human_translation": ortholog["dimension"],
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
    if any(row["mapping_basis"] == "nearest_gene" for row in matched_genetic):
        gaps.append("nearest_gene_not_causal")
    if any(row["direction_used"] or row["mechanism_used"] for row in matched_genetic):
        gaps.append("genetic_evidence_is_not_this_model_perturbation")
    gaps.extend(["independent_replication", "cell_type_context", *_translation_gaps(ortholog["status"])])
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
    if any(row["direction_used"] for row in matched_genetic):
        reasons.append("Reviewed genetic direction was included. It does not replace a perturbation in this model.")
    direction = next(iter(directions)) if len(directions) == 1 and not direction_conflict else "unknown"
    return {
        "hypothesis_id": "hypothesis-" + content_id([entity["entity_key"], context["context_id"], direction])[:24],
        "entity_key": entity["entity_key"], "entity_id": entity["entity_id"], "namespace": entity["namespace"],
        "entity_type": entity["entity_type"], "taxon_id": entity["taxon_id"], "context_id": context["context_id"], "bucket": bucket,
        "algorithm_bucket": bucket, "intervention_direction": direction, "dimensions": dimensions,
        "ortholog_status": ortholog["status"], "orthology_type": ortholog["orthology_type"],
        "human_orthologs": ortholog["orthologs"], "sign_pattern": _sign_pattern(local),
        "genetic_record_ids": [row["record_id"] for row in matched_genetic],
        "genetic_uses": sorted({row["use"] for row in matched_genetic}),
        "gaps": sorted(set(gaps)), "reasons": reasons,
        "evidence_ids": [r["evidence_id"] for r in local],
        "knowledge_evidence_ids": sorted(r["evidence_id"] for r in applicable),
        "qualifying_local_evidence_ids": sorted(r["evidence_id"] for r in qualified),
        "tool_ids": sorted({r["tool_id"] for r in positive("tool")}),
        "study_family_ids": sorted({r["primary_study_id"] for r in reviewed if r["primary_study_id"]}),
        "coverage": {"known_or_limited_dimensions": sum(v != "unknown" for v in dimensions.values()), "total_dimensions": len(dimensions)},
        "rule_version": policy["version"], "manual_review_required": True,
        "limitations": ["uncalibrated_policy", "no_success_probability", "no_sample_overlap_resolution", "not_a_treatment_recommendation"],
    }


def assess_archive(import_directory, destination, *, snapshot_paths=(), policy=None, ortholog_map=None, reaction_map=None, genetic_evidence=None) -> Path:
    root, manifest = read_archive(import_directory, "theraweave.import-preview")
    context = read_member(root, manifest, "context.json")
    for name in ("entity_inventory.parquet", "evidence_inventory.parquet"):
        if name not in {v["path"] for v in manifest["files"]}:
            raise ValueError(f"Missing checksummed inventory: {name}")
    entities = pq.read_table(root / "entity_inventory.parquet").to_pylist()
    evidence = pq.read_table(root / "evidence_inventory.parquet").to_pylist()
    knowledge = load_snapshots(list(snapshot_paths))
    ortholog_doc = load_ortholog_map(ortholog_map, entities) if ortholog_map else None
    reaction_doc = load_reaction_map(reaction_map, entities) if reaction_map else None
    genetic_doc = load_genetic_evidence(genetic_evidence, entities) if genetic_evidence else None
    genetic_records = [] if genetic_doc is None else genetic_doc["records"]
    synthetic = [source["synthetic"] for source in knowledge["sources"].values()]
    synthetic += [doc["synthetic"] for doc in (ortholog_doc, reaction_doc, genetic_doc) if doc]
    if any(synthetic) and not manifest.get("synthetic_input"):
        raise ValueError("Synthetic knowledge, ortholog maps, reaction maps, or genetic evidence are accepted only with an explicitly synthetic input bundle.")
    policy = validate_policy(dict(DEFAULT_POLICY) if policy is None else dict(policy))
    views = {entity["entity_key"]: ortholog_view(entity, ortholog_doc) for entity in entities}
    assessments = [_assess(entity, evidence, knowledge["records"], context, policy, views[entity["entity_key"]], genetic_records) for entity in entities]
    assessments.sort(key=lambda row: (BUCKETS.index(row["bucket"]), row["entity_key"]))
    sensitivity = []
    removal_sets = [("source", key) for key in sorted(knowledge["sources"])]
    removal_sets += [("study", key) for key in sorted({r["primary_study_id"] for r in knowledge["records"] if r["primary_study_id"]})]
    for mode, key in removal_sets:
        reduced = [r for r in knowledge["records"] if
                   (r["primary_study_id"] != key if mode == "study" else any(ref["source"] != key for ref in r["source_refs"]))]
        for entity in entities:
            original = _assess(entity, evidence, knowledge["records"], context, policy, views[entity["entity_key"]], genetic_records)
            changed = _assess(entity, evidence, reduced, context, policy, views[entity["entity_key"]], genetic_records)
            sensitivity.append({"remove_type": mode, "removed": key, "hypothesis_id": original["hypothesis_id"],
                                "original_bucket": original["bucket"], "new_bucket": changed["bucket"],
                                "direction_changed": changed["intervention_direction"] != original["intervention_direction"],
                                "bucket_changed": changed["bucket"] != original["bucket"]})
    links = reaction_links(reaction_doc, entities, evidence)
    linked = {link["reaction_entity_key"] for link in links["links"]}
    for row in assessments:
        if row["entity_key"] in linked:
            row["reasons"].append("A reviewed reaction map lists candidate enzymes. The flux remains one shared source and does not set an inhibition direction.")
    options = []
    for row in assessments:
        reviewed = [record for record in _applicable(row, knowledge["records"], context) if record["reviewed"]]
        options.extend(screen_modalities(row, reviewed))
    comparisons = build_comparisons(entities, evidence, knowledge["records"], genetic_records, context, policy, views, _assess)
    identity = {"parent_run_id": manifest["run_id"], "input_manifest_sha256": sha256_file(root / "manifest.json"),
                "policy": policy, "knowledge_hash": content_id(knowledge),
                "ortholog_map_sha256": None if ortholog_doc is None else ortholog_doc["sha256"],
                "reaction_map_sha256": None if reaction_doc is None else reaction_doc["sha256"],
                "genetic_evidence_sha256": None if genetic_doc is None else genetic_doc["sha256"],
                "synthetic_input": manifest.get("synthetic_input") is True}
    with new_archive(destination, format_name="theraweave.assessment-preview", identity=identity, forbidden_roots=[root]) as temp:
        write_json(temp / "context.json", context)
        write_json(temp / "assessments.json", assessments)
        write_json(temp / "knowledge.json", knowledge)
        write_json(temp / "policy.json", policy)
        write_json(temp / "sensitivity.json", sensitivity)
        write_json(temp / "baseline.json", {"method": "adjusted_p_descriptive_order", "records": comparisons["adjusted_p_order"],
                                            "accuracy": None, "ablation": "see_comparisons.json", "modality_rank": None})
        write_json(temp / "comparisons.json", comparisons)
        write_json(temp / "genetic_evidence.json", {"records": genetic_records, "sha256": identity["genetic_evidence_sha256"]})
        write_json(temp / "intervention_options.json", options)
        write_json(temp / "reaction_links.json", links)
        write_json(temp / "identity_maps.json", {
            "ortholog_map": None if ortholog_doc is None else {k: ortholog_doc[k] for k in
                            ("reviewer", "source_name", "source_release", "retrieved_at", "method", "synthetic", "sha256")},
            "reaction_map": None if reaction_doc is None else {k: reaction_doc[k] for k in
                            ("reviewer", "model_id", "model_version", "synthetic", "sha256")},
        })
        write_json(temp / "input_reference.json", {"path": str(root), "manifest_sha256": identity["input_manifest_sha256"],
                                                   "archived_observations": evidence, "archived_entities": entities})
        table_rows = [{k: row[k] for k in ("hypothesis_id", "entity_key", "entity_id", "bucket", "intervention_direction")} for row in assessments]
        pq.write_table(pa.Table.from_pylist(table_rows, schema=pa.schema([(k, pa.string()) for k in ("hypothesis_id", "entity_key", "entity_id", "bucket", "intervention_direction")])), temp / "target_assessments.parquet")
        rendered = "".join("<tr>" + "".join(f"<td>{escape(str(row[k] if k != 'sign_pattern' else row['sign_pattern']['status']))}</td>" for k in ("entity_id", "bucket", "intervention_direction", "sign_pattern", "ortholog_status", "gaps")) + "</tr>" for row in assessments)
        screened = [row for row in options if row["disposition"] != "insufficient_records"]
        modality_rows = "".join("<tr>" + "".join(f"<td>{escape(str(row[k]))}</td>" for k in ("entity_id", "modality", "disposition", "open_questions")) + "</tr>" for row in screened)
        (temp / "decision_report.html").write_text(
            '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'">'
            '<title>TheraWeave 候选评估预览</title><style>body{font:16px/1.6 system-ui;margin:40px;color:#18332f}td,th{padding:12px;border-bottom:1px solid #ddd}table{border-collapse:collapse}</style>'
            '<h1>候选验证优先级 · 规则预览</h1><p>规则尚未用独立研究校准；分桶表示下一步研究工作。所有候选均需人工审查。安全资料缺失保留为未知。模态表记录条件，不产生排序或治疗推荐。</p>'
            f'<table><tr><th>实体</th><th>下一步</th><th>功能方向</th><th>符号线索</th><th>人类同源</th><th>缺口</th></tr>{rendered}</table>'
            '<h2>模态条件</h2><p>开放的研究工具仍保留选择性、暴露或递送等未决条件。抗体与多肽、siRNA 与 ASO、mRNA 与基因补充分开记录。反向符号不是因果逆转，遗传记录也不代替本研究中的扰动。</p>'
            f'<table><tr><th>实体</th><th>模态</th><th>条件状态</th><th>未决问题</th></tr>{modality_rows or "<tr><td colspan=4>没有已记录的模态条件。</td></tr>"}</table>'
            '<p><a href="assessments.json">完整证据画像</a> · <a href="comparisons.json">描述性对照</a> · <a href="genetic_evidence.json">遗传记录</a> · '
            '<a href="intervention_options.json">模态条件</a> · <a href="reaction_links.json">反应映射</a> · '
            '<a href="sensitivity.json">来源/研究移除敏感性</a> · <a href="knowledge.json">知识与来源</a></p></html>', encoding="utf-8")
    return Path(destination).resolve()
