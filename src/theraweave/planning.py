"""Versioned draft plans, explicit review, and conservative outcome feedback."""
from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path

from .artifacts import new_archive, read_archive, read_member
from .core import content_id, read_json, sha256_file, write_json


def _screen(row: dict, options: list[dict]) -> dict:
    matched = [item for item in options if item["hypothesis_id"] == row["hypothesis_id"]]
    return {
        "rule_version": "modality-rules-1", "not_a_recommendation": True, "screen_does_not_override_bucket": True,
        "assessment_bucket": row["bucket"],
        "open_research_probes": [item["modality"] for item in matched if item["disposition"] == "open_research_probe"],
        "attribute_mismatches": [item["modality"] for item in matched if item["disposition"] == "attribute_mismatch"],
        "pending_conditions": [item["modality"] for item in matched if item["disposition"] == "pending_conditions"],
    }


def create_plans(assessment_directory, destination) -> Path:
    root, manifest = read_archive(assessment_directory, "theraweave.assessment-preview")
    context = read_member(root, manifest, "context.json")
    assessments = read_member(root, manifest, "assessments.json")
    options = read_member(root, manifest, "intervention_options.json")
    plans = []
    for row in assessments:
        plans.append({
            "plan_id": "plan-" + content_id([manifest["run_id"], row["hypothesis_id"]])[:24], "version": 1,
            "status": "draft", "hypothesis_id": row["hypothesis_id"], "entity_id": row["entity_id"],
            "context_id": context["context_id"], "assessment_bucket": row["bucket"],
            "question": f"Does modulating {row['entity_id']} change {context['primary_endpoint']} in the specified model?",
            "intervention_direction": row["intervention_direction"], "tool_ids": row["tool_ids"],
            "gap_ids": row["gaps"], "evidence_refs": row["evidence_ids"] + row["knowledge_evidence_ids"],
            "controls_to_review": ["vehicle_or_non_targeting", "orthogonal_perturbation", "rescue_if_feasible", "viability_or_general_stress"],
            "readout_chain": ["target_engagement", "functional_activity", "mechanistic_flux_if_applicable", "disease_phenotype"],
            "primary_endpoint": {"name": context["primary_endpoint"], "unit": None, "desired_direction": None,
                                 "minimum_meaningful_effect": None, "confidence_level": None},
            "design": {"experimental_unit": context.get("experimental_unit"), "biological_n": None,
                       "randomization": None, "blinding": None, "comparison": None,
                       "alpha": None, "power_or_precision": None, "variance_source": None,
                       "multiplicity_plan": None, "exclusions": None},
            "decision_rule": None, "review": None,
            "effort": {"decision_to_change": None, "cost_level": None, "duration_level": None, "laboratory_capability": None, "basis": None},
            "execution_ready": False, "computed_sample_size": None, "information_gain": None, "claims_reduced_experiment_count": False,
            "modality_screen": _screen(row, options),
            "alternatives": ["marker_or_compensation", "tool_off_target", "model_mismatch", "non_specific_toxicity"],
            "unresolved": ["experimental_design", "primary_endpoint_readout", "effect_and_precision_thresholds",
                           "tool_specificity", "modality_selectivity_exposure_or_delivery", "decision_cost_duration_and_laboratory_capability"],
        })
    with new_archive(destination, format_name="theraweave.validation-plans", identity={"parent_run_id": manifest["run_id"],
                     "parent_sha256": sha256_file(root / "manifest.json")}, forbidden_roots=[root]) as temp:
        write_json(temp / "context.json", context)
        write_json(temp / "plans.json", plans)
        write_json(temp / "assessment_reference.json", {"run_id": manifest["run_id"], "assessments": assessments})
        (temp / "README.md").write_text(
            "# 验证计划草稿\n\n每条计划须补充主要终点、效应界限、实验单位/样本量依据、对照和盲法等设计后审查。\n"
            "未知方差不自动生成样本量。hold_for_review 候选必须先解决风险，不能直接推进实验。\n"
            "审查使用独立 review JSON；反馈写入新归档，历史计划保持不变。\n", encoding="utf-8")
    return Path(destination).resolve()


def _nonempty_string(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a nonempty string.")


def _finite_number(value, name, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or (positive and value <= 0):
        raise ValueError(f"{name} must be a finite{' positive' if positive else ''} number.")


_DECISIONS = {"marker_versus_functional_link", "target_versus_off_target", "flux_mechanism_versus_concentration",
              "specific_effect_versus_toxicity", "species_translation", "other_preregistered"}
_COST = {"not_recorded", "low", "moderate", "high"}
_DURATION = {"not_recorded", "days", "weeks", "months"}
_CAPABILITY = {"available", "not_available", "not_recorded"}


def _effort(value) -> dict:
    required = {"decision_to_change", "cost_level", "duration_level", "laboratory_capability", "basis"}
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError(f"Effort must contain exactly {sorted(required)}.")
    if value["decision_to_change"] not in _DECISIONS:
        raise ValueError("Unsupported decision_to_change.")
    if value["cost_level"] not in _COST or value["duration_level"] not in _DURATION or value["laboratory_capability"] not in _CAPABILITY:
        raise ValueError("Cost, duration, and laboratory capability must use the recorded level labels.")
    _nonempty_string(value["basis"], "effort.basis")
    return value


def review_plan(plan_directory, plan_id: str, review_path, destination) -> Path:
    root, manifest = read_archive(plan_directory, "theraweave.validation-plans")
    context = read_member(root, manifest, "context.json")
    plans = read_member(root, manifest, "plans.json")
    matches = [p for p in plans if p["plan_id"] == plan_id]
    if len(matches) != 1:
        raise ValueError("Plan ID is missing or ambiguous.")
    plan = matches[0]
    if plan["status"] != "draft":
        raise ValueError("Review accepts a draft plan only; create a new revision for changes.")
    review = read_json(Path(review_path))
    required = {"reviewer", "reviewed_at", "rationale", "primary_endpoint", "design", "decision_rule", "effort"}
    if not isinstance(review, dict) or set(review) != required:
        raise ValueError(f"Review must contain exactly {sorted(required)}.")
    for key in ("reviewer", "reviewed_at", "rationale"):
        _nonempty_string(review[key], key)
    datetime.fromisoformat(review["reviewed_at"].replace("Z", "+00:00"))
    endpoint = review["primary_endpoint"]
    if not isinstance(endpoint, dict) or set(endpoint) != {"name", "unit", "desired_direction", "minimum_meaningful_effect", "confidence_level"}:
        raise ValueError("Incomplete primary endpoint.")
    for key in ("name", "unit"):
        _nonempty_string(endpoint[key], key)
    if endpoint["desired_direction"] not in {"increase", "decrease"}:
        raise ValueError("Endpoint desired_direction must be increase or decrease.")
    _finite_number(endpoint["minimum_meaningful_effect"], "minimum_meaningful_effect", positive=True)
    _finite_number(endpoint["confidence_level"], "confidence_level")
    if not 0 < endpoint["confidence_level"] < 1:
        raise ValueError("Invalid pre-specified confidence level.")
    design = review["design"]
    required_design = {"experimental_unit", "sample_size_basis", "randomization", "blinding", "comparison", "multiplicity_plan", "exclusions", "controls"}
    if not isinstance(design, dict) or set(design) != required_design:
        raise ValueError(f"Design must contain exactly {sorted(required_design)}.")
    for key in required_design:
        _nonempty_string(design[key], key)
    # A narrow interpretable feedback rule. Other rules require a new version.
    if review["decision_rule"] != "benefit_ci_excludes_zero_and_point_meets_minimum":
        raise ValueError("Unsupported pre-specified outcome decision rule.")
    effort = _effort(review["effort"])
    assessment = read_member(root, manifest, "assessment_reference.json")
    row = next(r for r in assessment["assessments"] if r["hypothesis_id"] == plan["hypothesis_id"])
    if row["bucket"] == "hold_for_review":
        raise ValueError("Blocking risk must first be resolved in a new assessment.")
    reviewed = {**plan, "version": plan["version"] + 1, "status": "reviewed", "primary_endpoint": endpoint,
                "design": design, "decision_rule": review["decision_rule"], "review": review, "effort": effort,
                "execution_ready": False, "computed_sample_size": None, "information_gain": None,
                "claims_reduced_experiment_count": False, "unresolved": [], "previous_plan_sha256": content_id(plan)}
    with new_archive(destination, format_name="theraweave.reviewed-plan", identity={"parent_run_id": manifest["run_id"],
                     "plan_id": plan_id, "review_hash": content_id(review)}, forbidden_roots=[root]) as temp:
        write_json(temp / "context.json", context)
        write_json(temp / "plan.json", reviewed)
        write_json(temp / "original_draft.json", plan)
        # JSON is valid YAML. Keep templates draft with empty sample tables.
        species = "mus_musculus" if context["source_taxon_id"] == 10090 else "homo_sapiens"
        template = temp / "omicsweave_draft"
        experiment = template / "experiments" / "validation"
        experiment.mkdir(parents=True)
        write_json(template / "project.yaml", {"schema_version": 1, "project": {"id": "validation_draft", "species": species,
                   "title": "Validation planning draft; sample records not provided"}})
        write_json(experiment / "experiment.yaml", {"schema_version": 1, "experiment": {"id": "validation",
                   "metadata": {"status": "draft", "plan_id": plan_id, "hypothesis_id": plan["hypothesis_id"]}},
                   "design": {"subjects": "subjects.tsv", "samples": "samples.tsv"}, "omics": {}, "integration": {"enabled": False}})
        (experiment / "subjects.tsv").write_text("subject_id\n", encoding="utf-8")
        (experiment / "samples.tsv").write_text("sample_id\tsubject_id\tomics\ttissue\n", encoding="utf-8")
        (template / "DRAFT.txt").write_text("No samples or input data. Not a validated execution configuration.\n", encoding="utf-8")
    return Path(destination).resolve()


def record_outcome(reviewed_directory, outcome_path, destination) -> Path:
    root, manifest = read_archive(reviewed_directory, "theraweave.reviewed-plan")
    context = read_member(root, manifest, "context.json")
    plan = read_member(root, manifest, "plan.json")
    outcome = read_json(Path(outcome_path))
    required = {"plan_id", "plan_version", "endpoint_name", "unit", "effect", "ci_lower", "ci_upper", "confidence_level",
                "target_engagement_confirmed", "qc_passed", "observed_by", "source_analysis", "execution_deviations"}
    if not isinstance(outcome, dict) or set(outcome) != required:
        raise ValueError(f"Outcome must contain exactly {sorted(required)}.")
    if outcome["plan_id"] != plan["plan_id"] or outcome["plan_version"] != plan["version"]:
        raise ValueError("Outcome must reference the exact reviewed plan version.")
    if outcome["endpoint_name"] != plan["primary_endpoint"]["name"] or outcome["unit"] != plan["primary_endpoint"]["unit"]:
        raise ValueError("Outcome endpoint and unit must match the reviewed plan; no silent conversion.")
    if outcome["confidence_level"] != plan["primary_endpoint"]["confidence_level"]:
        raise ValueError("Outcome confidence level must match the pre-specified reviewed plan.")
    for key in ("effect", "ci_lower", "ci_upper", "confidence_level"):
        _finite_number(outcome[key], key)
    if not (outcome["ci_lower"] <= outcome["effect"] <= outcome["ci_upper"] and 0 < outcome["confidence_level"] < 1):
        raise ValueError("Invalid effect interval or confidence level.")
    if (outcome["target_engagement_confirmed"] is not None and type(outcome["target_engagement_confirmed"]) is not bool) or type(outcome["qc_passed"]) is not bool:
        raise ValueError("Invalid engagement or QC status.")
    for key in ("observed_by", "source_analysis", "execution_deviations"):
        _nonempty_string(outcome[key], key)
    if not outcome["qc_passed"] or outcome["target_engagement_confirmed"] is not True:
        interpretation, reason = "inconclusive", "Perturbation or quality requirements not established."
    else:
        sign = 1 if plan["primary_endpoint"]["desired_direction"] == "increase" else -1
        lower, upper = sorted([sign * outcome["ci_lower"], sign * outcome["ci_upper"]])
        benefit = sign * outcome["effect"]
        if lower > 0 and benefit >= plan["primary_endpoint"]["minimum_meaningful_effect"]:
            interpretation, reason = "supported", "Predefined endpoint rule met in this model and experiment."
        elif upper <= 0:
            interpretation, reason = "not_supported", "Interval does not support benefit in the prespecified direction."
        else:
            interpretation, reason = "inconclusive", "Precision or minimum meaningful effect rule not met."
    feedback = {"hypothesis_id": plan["hypothesis_id"], "plan_id": plan["plan_id"], "plan_version": plan["version"],
                "interpretation": interpretation, "reason": reason, "outcome": outcome, "scope": "this_plan_and_context_only",
                "global_target_refuted": False, "requires_scientific_review": True}
    with new_archive(destination, format_name="theraweave.validation-outcome", identity={"parent_run_id": manifest["run_id"],
                     "outcome_hash": content_id(outcome)}, forbidden_roots=[root]) as temp:
        write_json(temp / "context.json", context)
        write_json(temp / "feedback.json", feedback)
        write_json(temp / "reviewed_plan.json", plan)
    return Path(destination).resolve()


_READOUTS = ("target_engagement", "functional_activity", "flux_or_mechanism", "disease_phenotype", "nonspecific_harm")
_READOUT_STATUS = {"supported", "not_supported", "inconclusive", "not_measured"}


def record_readouts(reviewed_directory, readouts_path, destination) -> Path:
    """Interpret a readout chain without letting harm or a failed perturbation refute the target."""
    root, manifest = read_archive(reviewed_directory, "theraweave.reviewed-plan")
    context = read_member(root, manifest, "context.json")
    plan = read_member(root, manifest, "plan.json")
    report = read_json(Path(readouts_path))
    required = {"plan_id", "plan_version", "qc_passed", "flux_applicable", "species_translation_claimed",
                "observed_by", "source_analysis", "execution_deviations", "layers"}
    if not isinstance(report, dict) or set(report) != required:
        raise ValueError(f"Readouts must contain exactly {sorted(required)}.")
    if report["plan_id"] != plan["plan_id"] or report["plan_version"] != plan["version"]:
        raise ValueError("Readouts must reference the exact reviewed plan version.")
    if type(report["qc_passed"]) is not bool or type(report["flux_applicable"]) is not bool or report["species_translation_claimed"] is not False:
        raise ValueError("QC and flux applicability must be boolean, and species translation cannot be claimed.")
    for key in ("observed_by", "source_analysis", "execution_deviations"):
        _nonempty_string(report[key], key)
    layers = report["layers"]
    if not isinstance(layers, list) or len(layers) != len(_READOUTS):
        raise ValueError("The readout chain needs each layer exactly once.")
    by_layer = {}
    for layer in layers:
        if not isinstance(layer, dict) or set(layer) != {"layer", "status", "note"}:
            raise ValueError("Each readout needs layer, status, and note.")
        if layer["layer"] in by_layer or layer["layer"] not in _READOUTS or layer["status"] not in _READOUT_STATUS:
            raise ValueError("Readout layers must be the known chain and cannot repeat.")
        _nonempty_string(layer["note"], layer["layer"])
        by_layer[layer["layer"]] = layer["status"]
    if not report["flux_applicable"] and by_layer["flux_or_mechanism"] != "not_measured":
        raise ValueError("A flux readout cannot be supplied when flux is not applicable.")
    interpretation, reason = _readout_interpretation(by_layer, report["flux_applicable"], report["qc_passed"])
    feedback = {"hypothesis_id": plan["hypothesis_id"], "plan_id": plan["plan_id"], "plan_version": plan["version"],
                "interpretation": interpretation, "reason": reason, "readouts": report, "scope": "this_plan_and_context_only",
                "global_target_refuted": False, "species_translation": False, "replaces_primary_endpoint": False,
                "requires_scientific_review": True}
    with new_archive(destination, format_name="theraweave.readout-chain", identity={"parent_run_id": manifest["run_id"],
                     "readout_hash": content_id(report)}, forbidden_roots=[root]) as temp:
        write_json(temp / "context.json", context)
        write_json(temp / "feedback.json", feedback)
        write_json(temp / "reviewed_plan.json", plan)
    return Path(destination).resolve()


def _readout_interpretation(layers: dict, flux_applicable: bool, qc_passed: bool) -> tuple[str, str]:
    if not qc_passed:
        return "inconclusive", "Quality requirements were not met."
    if layers["nonspecific_harm"] == "supported":
        return "inconclusive", "Nonspecific harm was observed, so the phenotype is not counted as therapeutic support."
    if layers["target_engagement"] != "supported":
        return "inconclusive", "Without established target engagement, the phenotype cannot support or refute the hypothesis."
    if layers["functional_activity"] != "supported":
        return "inconclusive", "Functional activity was not established."
    if flux_applicable and layers["flux_or_mechanism"] != "supported":
        return "inconclusive", "The applicable flux or mechanism readout was not established."
    if layers["nonspecific_harm"] != "not_supported":
        return "inconclusive", "Nonspecific harm was not shown to be absent."
    if layers["disease_phenotype"] == "supported":
        return "supported", "Engagement, function, and the disease readout support this plan, and nonspecific harm was not observed."
    if layers["disease_phenotype"] == "not_supported":
        return "not_supported", "The disease readout does not support the prespecified benefit in this plan."
    return "inconclusive", "The disease readout is incomplete."


_BUCKET_LEVEL = {"functional_validation_ready": 0, "evidence_gap_first": 1, "conflict_resolution_first": 1, "hold_for_review": 2}


def record_override(assessment_directory, override_path, destination) -> Path:
    """Record a human decision that cannot relax the algorithm bucket or clear a blocking risk."""
    root, manifest = read_archive(assessment_directory, "theraweave.assessment-preview")
    context = read_member(root, manifest, "context.json")
    assessments = read_member(root, manifest, "assessments.json")
    options = read_member(root, manifest, "intervention_options.json")
    links = read_member(root, manifest, "reaction_links.json")
    override = read_json(Path(override_path))
    required = {"hypothesis_id", "operator", "overridden_at", "rationale", "requested_bucket", "evidence_ids"}
    if not isinstance(override, dict) or set(override) != required:
        raise ValueError(f"Override must contain exactly {sorted(required)}.")
    for key in ("hypothesis_id", "operator", "overridden_at", "rationale"):
        _nonempty_string(override[key], key)
    datetime.fromisoformat(override["overridden_at"].replace("Z", "+00:00"))
    if override["requested_bucket"] not in _BUCKET_LEVEL:
        raise ValueError("Unsupported decision bucket.")
    evidence_ids = override["evidence_ids"]
    if (not isinstance(evidence_ids, list) or not evidence_ids or len(evidence_ids) != len(set(evidence_ids))
            or any(not isinstance(item, str) or not item.strip() for item in evidence_ids)):
        raise ValueError("Override must cite unique evidence identifiers from this hypothesis.")
    matches = [row for row in assessments if row["hypothesis_id"] == override["hypothesis_id"]]
    if len(matches) != 1:
        raise ValueError("Hypothesis ID is missing or ambiguous.")
    row = matches[0]
    if any(item not in set(row["evidence_ids"]) | set(row["knowledge_evidence_ids"]) for item in evidence_ids):
        raise ValueError("Override evidence identifiers must belong to this hypothesis.")
    algorithm_bucket = row.get("algorithm_bucket", row["bucket"])
    requested = override["requested_bucket"]
    if _BUCKET_LEVEL[requested] < _BUCKET_LEVEL[algorithm_bucket] or _BUCKET_LEVEL[requested] < _BUCKET_LEVEL[row["bucket"]]:
        raise ValueError("An override cannot relax the algorithm bucket or clear a blocking risk.")
    updated = [{**item, "algorithm_bucket": algorithm_bucket, "bucket": requested} if item["hypothesis_id"] == row["hypothesis_id"] else item
               for item in assessments]
    prior = read_member(root, manifest, "decision_log.json") if any(entry["path"] == "decision_log.json" for entry in manifest["files"]) else []
    if not isinstance(prior, list):
        raise ValueError("Existing decision log is unreadable.")
    entry = {"hypothesis_id": row["hypothesis_id"], "algorithm_bucket": algorithm_bucket, "previous_bucket": row["bucket"],
             "requested_bucket": requested, "accepted_bucket": requested, "operator": override["operator"],
             "overridden_at": override["overridden_at"], "rationale": override["rationale"], "evidence_ids": evidence_ids,
             "relaxes_algorithm_decision": False, "clears_blocking_risk": False}
    with new_archive(destination, format_name="theraweave.assessment-preview", identity={"parent_run_id": manifest["run_id"],
                     "override_hash": content_id(override)}, forbidden_roots=[root]) as temp:
        write_json(temp / "context.json", context)
        write_json(temp / "assessments.json", updated)
        write_json(temp / "intervention_options.json", options)
        write_json(temp / "reaction_links.json", links)
        write_json(temp / "decision_log.json", prior + [entry])
    return Path(destination).resolve()
