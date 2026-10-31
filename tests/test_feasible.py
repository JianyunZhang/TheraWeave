import pytest

from theraweave import DiscoveryProject
from theraweave.assessment import assess_archive
from theraweave.candidates import screen_candidates
from theraweave.core import BundleValidationError, read_json, write_json
from theraweave.demo import create_demo
from theraweave.external import prepare_external_request, record_external_result
from theraweave.planning import create_plans, review_plan

DIGEST = "a" * 64


@pytest.fixture
def assessed(tmp_path):
    demo = create_demo(tmp_path / "demo")
    archive = DiscoveryProject.from_bundle(demo / "bundle", context=demo / "context.json", allow_draft=True).write_evidence_report(tmp_path / "import")
    out = assess_archive(archive, tmp_path / "assessed", snapshot_paths=sorted((demo / "knowledge").glob("*.json")))
    return {"root": tmp_path, "demo": demo, "assessment": out}


def test_review_records_effort_without_computing_cost_or_sample_size(assessed):
    plans = create_plans(assessed["assessment"], assessed["root"] / "plans")
    plan = next(row for row in read_json(plans / "plans.json") if row["entity_id"] == "DEMO_GENE_A")
    assert plan["execution_ready"] is False and plan["computed_sample_size"] is None and plan["information_gain"] is None
    review = {
        "reviewer": "Synthetic reviewer", "reviewed_at": "2026-11-01T00:00:00Z", "rationale": "Synthetic review",
        "primary_endpoint": {"name": "synthetic endpoint", "unit": "arbitrary_units", "desired_direction": "decrease", "minimum_meaningful_effect": 1.0, "confidence_level": 0.95},
        "design": {key: "Synthetic pre-specified design" for key in ("experimental_unit", "sample_size_basis", "randomization", "blinding", "comparison", "multiplicity_plan", "exclusions", "controls")},
        "decision_rule": "benefit_ci_excludes_zero_and_point_meets_minimum",
        "effort": {"decision_to_change": "marker_versus_functional_link", "cost_level": "not_recorded", "duration_level": "weeks",
                   "laboratory_capability": "available", "basis": "Synthetic level only; no currency or sample size was calculated"},
    }
    write_json(assessed["root"] / "review.json", review)
    reviewed = review_plan(plans, plan["plan_id"], assessed["root"] / "review.json", assessed["root"] / "reviewed")
    saved = read_json(reviewed / "plan.json")
    assert saved["execution_ready"] is False
    assert saved["computed_sample_size"] is None and saved["information_gain"] is None
    assert saved["claims_reduced_experiment_count"] is False
    assert saved["effort"]["cost_level"] == "not_recorded"


def test_candidate_list_cannot_impersonate_a_statistical_assessment(assessed):
    path = assessed["root"] / "candidates.json"
    document = {"format": "theraweave.candidate-list", "version": "0.1", "synthetic": True, "context_id": "synthetic_context",
                "source_taxon_id": 10090, "disease_or_phenotype": "synthetic", "research_goal": "software test",
                "screening_rule": "user supplied names", "source_note": "not an evidence bundle",
                "candidates": [{"entity_id": "DEMO_GENE_A", "namespace": "demo", "entity_type": "gene", "taxon_id": 10090}]}
    write_json(path, document)
    out = screen_candidates(path, assessed["root"] / "screen", snapshot_paths=sorted((assessed["demo"] / "knowledge").glob("*.json")))
    row = read_json(out / "candidates.json")[0]
    limits = read_json(out / "limits.json")
    assert row["bucket"] == "knowledge_gap_review"
    assert row["intervention_direction"] == "inhibit"
    assert row["local_padj"] is None and limits["accuracy"] is None and limits["statistical_inference"] is False
    document["candidates"][0]["padj"] = 0.01
    write_json(path, document)
    with pytest.raises(BundleValidationError) as exc:
        screen_candidates(path, assessed["root"] / "rejected")
    assert any(item.rule_id == "JSON_SCHEMA" for item in exc.value.report.diagnostics)
    document["synthetic"] = False
    document["candidates"][0].pop("padj")
    write_json(path, document)
    with pytest.raises(ValueError, match="Synthetic knowledge"):
        screen_candidates(path, assessed["root"] / "real", snapshot_paths=sorted((assessed["demo"] / "knowledge").glob("*.json")))


def _request(row, **overrides):
    request = {
        "request_id": "request-1", "hypothesis_id": row["hypothesis_id"], "gap_id": "functional_causality",
        "scientific_question": "Does a recorded construct have a usable binding hypothesis?", "task_type": "docking",
        "allowed_conclusion": "binding_hypothesis", "reviewer": "Synthetic reviewer", "reviewed_at": "2026-11-01T00:00:00Z",
        "network_authorized": False, "executes_backend": False,
        "target": {"taxon_id": row["taxon_id"], "namespace": row["namespace"], "entity_id": row["entity_id"],
                   "construct_id": "synthetic-construct", "sequence_or_structure_sha256": DIGEST, "structure_source": "synthetic structure",
                   "preparation_assumptions": "synthetic preparation", "identity_basis": "same_entity_as_hypothesis",
                   "orthology_type": None, "ortholog_reviewer": None},
        "molecule": {"stable_id": "SYNTHETIC_MOL", "stereochemistry_or_modification": "unspecified synthetic stereo", "content_sha256": DIGEST},
    }
    request.update(overrides)
    return request


def _result(prepared, **overrides):
    result = {
        "request_id": prepared["request_id"], "hypothesis_id": prepared["hypothesis_id"], "hypothesis_version": prepared["hypothesis_version"],
        "run_id": "synthetic-run", "tool_name": "synthetic-docker", "tool_version": "0", "parameters": {"poses": 1},
        "status": "completed", "prediction_type": "docking_score", "quantity_kind": "binding_score", "value": -8.0, "unit": "synthetic_score",
        "favorable_direction": "lower_is_better", "uncertainty": "not calibrated", "applicability_domain": "synthetic domain",
        "reference_system": "synthetic receptor", "sampling_note": None, "artifact_sha256": DIGEST, "warnings": [],
        "resource_note": "no external program was run", "counts_as_independent_replication": False, "evidence_level": "predicted",
    }
    result.update(overrides)
    return result


def test_external_request_is_not_executed_and_prediction_stays_predicted(assessed):
    row = next(item for item in read_json(assessed["assessment"] / "assessments.json") if item["entity_id"] == "DEMO_GENE_A")
    path = assessed["root"] / "request.json"
    write_json(path, _request(row))
    prepared_dir = prepare_external_request(assessed["assessment"], path, assessed["root"] / "request-archive")
    prepared = read_json(prepared_dir / "request.json")
    limits = read_json(prepared_dir / "limits.json")
    assert prepared["status"] == "prepared_not_executed" and limits["executed"] is False
    result_path = assessed["root"] / "result.json"
    write_json(result_path, _result(prepared))
    recorded_dir = record_external_result(prepared_dir, result_path, assessed["root"] / "result-archive")
    recorded = read_json(recorded_dir / "result.json")
    assert recorded["evidence_level"] == "predicted"
    assert recorded["interpretation"] == "predicted_unconfirmed"
    assert recorded["independent_support_added"] == 0 and recorded["fills_functional_gap"] is False
    assert recorded["time_series_is_biological_replicate"] is False
    write_json(path, _request(row, target={**_request(row)["target"], "entity_id": "HUMAN_A", "identity_basis": "reviewed_ortholog",
                                           "orthology_type": "one2one", "ortholog_reviewer": "Synthetic reviewer"}))
    with pytest.raises(ValueError, match="reviewed ortholog"):
        prepare_external_request(assessed["assessment"], path, assessed["root"] / "bad-ortholog")
    write_json(result_path, _result(prepared, prediction_type="binding_free_energy", quantity_kind="free_energy"))
    with pytest.raises(ValueError, match="does not match"):
        record_external_result(prepared_dir, result_path, assessed["root"] / "mixed-score")
    write_json(result_path, _result(prepared, evidence_level="observed"))
    with pytest.raises(BundleValidationError):
        record_external_result(prepared_dir, result_path, assessed["root"] / "observed")
