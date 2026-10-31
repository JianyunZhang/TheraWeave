from pathlib import Path

import pytest

from theraweave import DiscoveryProject
from theraweave.assessment import assess_archive
from theraweave.core import BundleValidationError, read_json, write_json
from theraweave.demo import create_demo
from theraweave.knowledge import load_snapshots
from theraweave.planning import create_plans, record_outcome, review_plan


@pytest.fixture
def pipeline(tmp_path):
    demo = create_demo(tmp_path / "demo")
    archive = DiscoveryProject.from_bundle(demo / "bundle", context=demo / "context.json", allow_draft=True).write_evidence_report(tmp_path / "import")
    snapshots = sorted((demo / "knowledge").glob("*.json"))
    assessed = assess_archive(archive, tmp_path / "assessed", snapshot_paths=snapshots)
    return {"demo": demo, "import": archive, "snapshots": snapshots, "assessment": assessed, "root": tmp_path}


def rows(pipeline):
    return {r["entity_id"]: r for r in read_json(pipeline["assessment"] / "assessments.json")}


def test_rule_profiles_preserve_unknowns_and_report_sensitivity(pipeline):
    values = rows(pipeline)
    a, b = values["DEMO_GENE_A"], values["DEMO_GENE_B"]
    assert a["bucket"] == "functional_validation_ready"
    assert a["intervention_direction"] == "inhibit"
    assert a["dimensions"]["risk_review"] == "unknown"
    assert a["dimensions"]["mechanistic_evidence"] == "unknown"
    assert a["dimensions"]["human_translation"] == "unknown"
    assert a["ortholog_status"] == "not_provided"
    assert "human_ortholog_map" in a["gaps"]
    assert a["manual_review_required"] is True
    assert b["bucket"] == "evidence_gap_first" and b["intervention_direction"] == "unknown"
    sensitivity = read_json(pipeline["assessment"] / "sensitivity.json")
    assert any(s["bucket_changed"] and s["removed"].startswith("UniProt:") for s in sensitivity)
    assert any(s["direction_changed"] and s["removed"].startswith("OpenTargets:") for s in sensitivity)


def test_no_knowledge_means_gaps_not_low_risk_or_invented_direction(pipeline):
    assessed = assess_archive(pipeline["import"], pipeline["root"] / "no-knowledge")
    for row in read_json(assessed / "assessments.json"):
        assert row["bucket"] == "evidence_gap_first"
        assert row["dimensions"]["risk_review"] == "unknown"
        assert row["intervention_direction"] == "unknown"


def test_cross_source_primary_assertion_is_one_record(pipeline):
    paths = pipeline["snapshots"]
    ot_path = next(p for p in paths if "OpenTargets" in p.name)
    chembl_path = next(p for p in paths if "ChEMBL" in p.name)
    original = read_json(ot_path)["records"][0]
    chembl = read_json(chembl_path)
    chembl["records"].append({**original, "record_id": "reprinted_direction_A"})
    write_json(chembl_path, chembl)
    knowledge = load_snapshots(paths)
    assert len(knowledge["records"]) == 3
    duplicated = next(r for r in knowledge["records"] if r["evidence_type"] == "direction")
    assert len(duplicated["source_refs"]) == 2


def test_direction_conflicts_and_scoped_risk_cannot_be_outweighed(pipeline):
    path = next(p for p in pipeline["snapshots"] if "OpenTargets" in p.name)
    value = read_json(path)
    other = {**value["records"][0], "record_id": "opposing", "primary_record_id": "synthetic:opposing", "direction": "activate"}
    value["records"].append(other)
    write_json(path, value)
    first = assess_archive(pipeline["import"], pipeline["root"] / "conflict", snapshot_paths=pipeline["snapshots"])
    a = next(r for r in read_json(first / "assessments.json") if r["entity_id"] == "DEMO_GENE_A")
    assert a["bucket"] == "conflict_resolution_first" and a["intervention_direction"] == "unknown"
    value["records"].append({**other, "record_id": "risk", "primary_record_id": "synthetic:risk", "evidence_type": "risk", "blocking": True})
    write_json(path, value)
    second = assess_archive(pipeline["import"], pipeline["root"] / "risk", snapshot_paths=pipeline["snapshots"])
    a = next(r for r in read_json(second / "assessments.json") if r["entity_id"] == "DEMO_GENE_A")
    assert a["bucket"] == "hold_for_review"


def test_wrong_context_cannot_grant_direction(pipeline):
    path = next(p for p in pipeline["snapshots"] if "OpenTargets" in p.name)
    value = read_json(path)
    value["records"][0]["context_id"] = "different_disease"
    write_json(path, value)
    out = assess_archive(pipeline["import"], pipeline["root"] / "different-context", snapshot_paths=pipeline["snapshots"])
    a = next(r for r in read_json(out / "assessments.json") if r["entity_id"] == "DEMO_GENE_A")
    assert a["intervention_direction"] == "unknown"


def test_synthetic_knowledge_cannot_support_unmarked_real_data(pipeline):
    # A format-integrity-valid archive with no synthetic declaration.
    path = pipeline["import"] / "manifest.json"
    value = read_json(path)
    value["synthetic_input"] = False
    write_json(path, value)
    with pytest.raises(ValueError, match="Synthetic knowledge"):
        assess_archive(pipeline["import"], pipeline["root"] / "real", snapshot_paths=pipeline["snapshots"])


def prepare_review(pipeline):
    root = pipeline["root"]
    plans = create_plans(pipeline["assessment"], root / "plans")
    plan = next(p for p in read_json(plans / "plans.json") if p["entity_id"] == "DEMO_GENE_A")
    review = {
        "reviewer": "Synthetic reviewer", "reviewed_at": "2026-10-30T00:00:00Z", "rationale": "Synthetic software test only",
        "primary_endpoint": {"name": "synthetic endpoint", "unit": "arbitrary_units", "desired_direction": "decrease", "minimum_meaningful_effect": 1.0, "confidence_level": 0.95},
        "design": {k: "Synthetic pre-specified design" for k in ("experimental_unit", "sample_size_basis", "randomization", "blinding", "comparison", "multiplicity_plan", "exclusions", "controls")},
        "decision_rule": "benefit_ci_excludes_zero_and_point_meets_minimum",
        "effort": {"decision_to_change": "marker_versus_functional_link", "cost_level": "not_recorded", "duration_level": "not_recorded",
                   "laboratory_capability": "not_recorded", "basis": "Synthetic review; no cost was calculated"},
    }
    write_json(root / "review.json", review)
    reviewed = review_plan(plans, plan["plan_id"], root / "review.json", root / "reviewed")
    return plans, reviewed, read_json(reviewed / "plan.json")


@pytest.mark.parametrize("effect,lower,upper,engagement,qc,expected", [
    (-2, -3, -1, True, True, "supported"),
    (-2, -3, -1, False, True, "inconclusive"),
    (-2, -3, -1, True, False, "inconclusive"),
    (-0.1, -1, 1, True, True, "inconclusive"),
    (2, 1, 3, True, True, "not_supported"),
])
def test_feedback_is_scoped_and_requires_successful_perturbation(pipeline, effect, lower, upper, engagement, qc, expected):
    plans, reviewed, plan = prepare_review(pipeline)
    outcome = {"plan_id": plan["plan_id"], "plan_version": plan["version"], "endpoint_name": "synthetic endpoint", "unit": "arbitrary_units",
               "effect": effect, "ci_lower": lower, "ci_upper": upper, "confidence_level": 0.95,
               "target_engagement_confirmed": engagement, "qc_passed": qc, "observed_by": "Synthetic reviewer",
               "source_analysis": "urn:synthetic:analysis", "execution_deviations": "none reported (synthetic)"}
    write_json(pipeline["root"] / "outcome.json", outcome)
    out = record_outcome(reviewed, pipeline["root"] / "outcome.json", pipeline["root"] / "feedback")
    feedback = read_json(out / "feedback.json")
    assert feedback["interpretation"] == expected
    assert feedback["global_target_refuted"] is False
    assert next(p for p in read_json(plans / "plans.json") if p["plan_id"] == plan["plan_id"])["status"] == "draft"
    assert (reviewed / "omicsweave_draft" / "DRAFT.txt").is_file()


def test_feedback_cannot_change_endpoint_unit_or_plan_version(pipeline):
    _, reviewed, plan = prepare_review(pipeline)
    outcome = {"plan_id": plan["plan_id"], "plan_version": plan["version"] - 1, "endpoint_name": "synthetic endpoint", "unit": "arbitrary_units",
               "effect": -2, "ci_lower": -3, "ci_upper": -1, "confidence_level": 0.95,
               "target_engagement_confirmed": True, "qc_passed": True, "observed_by": "Synthetic reviewer", "source_analysis": "urn:synthetic", "execution_deviations": "none"}
    write_json(pipeline["root"] / "bad-outcome.json", outcome)
    with pytest.raises(ValueError, match="exact reviewed plan"):
        record_outcome(reviewed, pipeline["root"] / "bad-outcome.json", pipeline["root"] / "invalid-feedback")


def test_tampered_archive_is_rejected_before_assessment(pipeline):
    (pipeline["import"] / "context.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="integrity"):
        assess_archive(pipeline["import"], pipeline["root"] / "tampered")
