"""Versioned draft plans, explicit review, and conservative outcome feedback."""
from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path

from .artifacts import new_archive, read_archive, read_member
from .core import content_id, read_json, sha256_file, write_json


def create_plans(assessment_directory, destination) -> Path:
    root, manifest = read_archive(assessment_directory, "theraweave.assessment-preview")
    context = read_member(root, manifest, "context.json")
    assessments = read_member(root, manifest, "assessments.json")
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
            "alternatives": ["marker_or_compensation", "tool_off_target", "model_mismatch", "non_specific_toxicity"],
            "unresolved": ["experimental_design", "primary_endpoint_readout", "effect_and_precision_thresholds", "tool_specificity"],
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
    required = {"reviewer", "reviewed_at", "rationale", "primary_endpoint", "design", "decision_rule"}
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
    assessment = read_member(root, manifest, "assessment_reference.json")
    row = next(r for r in assessment["assessments"] if r["hypothesis_id"] == plan["hypothesis_id"])
    if row["bucket"] == "hold_for_review":
        raise ValueError("Blocking risk must first be resolved in a new assessment.")
    reviewed = {**plan, "version": plan["version"] + 1, "status": "reviewed", "primary_endpoint": endpoint,
                "design": design, "decision_rule": review["decision_rule"], "review": review,
                "unresolved": [], "previous_plan_sha256": content_id(plan)}
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
