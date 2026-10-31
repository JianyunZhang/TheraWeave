"""Run the full local preview on synthetic data, including an explicit fake review.

All science values, knowledge assertions, reviewers and outcomes are synthetic.
No database query, real hypothesis approval, or wet experiment is performed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from theraweave import DiscoveryProject
from theraweave.assessment import assess_archive
from theraweave.core import read_json, write_json
from theraweave.demo import create_demo
from theraweave.planning import create_plans, record_outcome, review_plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    root = parser.parse_args().destination.resolve()
    root.mkdir(parents=True, exist_ok=False)
    demo = create_demo(root / "inputs")
    imported = DiscoveryProject.from_bundle(demo / "bundle", context=demo / "context.json", allow_draft=True).write_evidence_report(root / "import")
    assessed = assess_archive(imported, root / "assessment", snapshot_paths=sorted((demo / "knowledge").glob("*.json")))
    plans = create_plans(assessed, root / "plans")
    plan = next(p for p in read_json(plans / "plans.json") if p["entity_id"] == "DEMO_GENE_A")
    review = {
        "reviewer": "SYNTHETIC REVIEWER", "reviewed_at": "2026-10-30T00:00:00Z", "rationale": "Synthetic software demonstration only",
        "primary_endpoint": {"name": "synthetic phenotype", "unit": "arbitrary_units", "desired_direction": "decrease", "minimum_meaningful_effect": 1.0, "confidence_level": 0.95},
        "design": {k: "Synthetic pre-specified design; no actual experiment" for k in ("experimental_unit", "sample_size_basis", "randomization", "blinding", "comparison", "multiplicity_plan", "exclusions", "controls")},
        "decision_rule": "benefit_ci_excludes_zero_and_point_meets_minimum",
        "effort": {"decision_to_change": "marker_versus_functional_link", "cost_level": "not_recorded", "duration_level": "weeks",
                   "laboratory_capability": "not_recorded", "basis": "Synthetic demonstration; no experiment cost was calculated"},
    }
    write_json(root / "synthetic-review.json", review)
    reviewed = review_plan(plans, plan["plan_id"], root / "synthetic-review.json", root / "reviewed")
    reviewed_plan = read_json(reviewed / "plan.json")
    outcome = {"plan_id": plan["plan_id"], "plan_version": reviewed_plan["version"], "endpoint_name": "synthetic phenotype", "unit": "arbitrary_units",
               "effect": -2.0, "ci_lower": -3.0, "ci_upper": -1.0, "confidence_level": 0.95,
               "target_engagement_confirmed": True, "qc_passed": True, "observed_by": "SYNTHETIC REVIEWER",
               "source_analysis": "urn:theraweave:synthetic-outcome", "execution_deviations": "Synthetic only; no experiment executed"}
    write_json(root / "synthetic-outcome.json", outcome)
    feedback = record_outcome(reviewed, root / "synthetic-outcome.json", root / "feedback")
    summary = {"synthetic": True, "network_used": False, "import": str(imported), "assessment": str(assessed),
               "plans": str(plans), "reviewed": str(reviewed), "feedback": str(feedback),
               "interpretation": read_json(feedback / "feedback.json")["interpretation"],
               "real_scientific_validation": False}
    write_json(root / "demo-summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
