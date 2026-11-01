import pytest

from theraweave import DiscoveryProject
from theraweave.assessment import assess_archive
from theraweave.core import read_json, write_json
from theraweave.demo import create_demo
from theraweave.planning import create_plans, record_readouts, review_plan


def _layers(**statuses):
    base = {name: "supported" for name in ("target_engagement", "functional_activity", "disease_phenotype")}
    base.update(flux_or_mechanism="not_measured", nonspecific_harm="not_supported")
    base.update(statuses)
    return [{"layer": name, "status": status, "note": f"Synthetic {name}"} for name, status in base.items()]


@pytest.fixture
def reviewed(tmp_path):
    demo = create_demo(tmp_path / "demo")
    imported = DiscoveryProject.from_bundle(demo / "bundle", context=demo / "context.json", allow_draft=True).write_evidence_report(tmp_path / "import")
    assessed = assess_archive(imported, tmp_path / "assessed", snapshot_paths=sorted((demo / "knowledge").glob("*.json")))
    plans = create_plans(assessed, tmp_path / "plans")
    plan = next(row for row in read_json(plans / "plans.json") if row["entity_id"] == "DEMO_GENE_A")
    review = {
        "reviewer": "Synthetic reviewer", "reviewed_at": "2026-11-01T00:00:00Z", "rationale": "Synthetic review",
        "primary_endpoint": {"name": "synthetic endpoint", "unit": "arbitrary_units", "desired_direction": "decrease", "minimum_meaningful_effect": 1.0, "confidence_level": 0.95},
        "design": {key: "Synthetic pre-specified design" for key in ("experimental_unit", "sample_size_basis", "randomization", "blinding", "comparison", "multiplicity_plan", "exclusions", "controls")},
        "decision_rule": "benefit_ci_excludes_zero_and_point_meets_minimum",
        "effort": {"decision_to_change": "specific_effect_versus_toxicity", "cost_level": "not_recorded", "duration_level": "not_recorded",
                   "laboratory_capability": "not_recorded", "basis": "Synthetic review; no cost was calculated"},
    }
    write_json(tmp_path / "review.json", review)
    reviewed_dir = review_plan(plans, plan["plan_id"], tmp_path / "review.json", tmp_path / "reviewed")
    return {"root": tmp_path, "reviewed": reviewed_dir, "plan": read_json(reviewed_dir / "plan.json")}


def _write(reviewed, layers, **overrides):
    report = {"plan_id": reviewed["plan"]["plan_id"], "plan_version": reviewed["plan"]["version"], "qc_passed": True,
              "flux_applicable": False, "species_translation_claimed": False, "observed_by": "Synthetic reviewer",
              "source_analysis": "urn:synthetic:readouts", "execution_deviations": "none", "layers": layers}
    report.update(overrides)
    path = reviewed["root"] / "readouts.json"
    write_json(path, report)
    return path


def test_complete_chain_can_support_this_plan_only(reviewed):
    out = record_readouts(reviewed["reviewed"], _write(reviewed, _layers()), reviewed["root"] / "supported")
    feedback = read_json(out / "feedback.json")
    assert feedback["interpretation"] == "supported"
    assert feedback["global_target_refuted"] is False and feedback["species_translation"] is False
    assert feedback["replaces_primary_endpoint"] is False


def test_harm_and_failed_engagement_do_not_become_therapeutic_results(reviewed):
    harm = record_readouts(reviewed["reviewed"], _write(reviewed, _layers(nonspecific_harm="supported")), reviewed["root"] / "harm")
    assert read_json(harm / "feedback.json")["interpretation"] == "inconclusive"
    missed = record_readouts(reviewed["reviewed"], _write(reviewed, _layers(target_engagement="not_measured", disease_phenotype="not_supported")), reviewed["root"] / "missed")
    feedback = read_json(missed / "feedback.json")
    assert feedback["interpretation"] == "inconclusive"
    assert feedback["global_target_refuted"] is False


def test_applicable_flux_must_be_established_before_support(reviewed):
    path = _write(reviewed, _layers(flux_or_mechanism="not_measured"), flux_applicable=True)
    out = record_readouts(reviewed["reviewed"], path, reviewed["root"] / "flux")
    assert read_json(out / "feedback.json")["interpretation"] == "inconclusive"
    with pytest.raises(ValueError, match="not applicable"):
        record_readouts(reviewed["reviewed"], _write(reviewed, _layers(flux_or_mechanism="supported")), reviewed["root"] / "unexpected-flux")
