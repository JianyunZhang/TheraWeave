from pathlib import Path

import pytest

from theraweave import DiscoveryProject
from theraweave.assessment import assess_archive
from theraweave.core import BundleValidationError, read_json, write_json
from theraweave.demo import create_demo
from theraweave.knowledge import load_snapshots
from theraweave.modalities import screen_modalities
from theraweave.planning import create_plans, record_override, review_plan


@pytest.fixture
def assessed(tmp_path):
    demo = create_demo(tmp_path / "demo")
    archive = DiscoveryProject.from_bundle(demo / "bundle", context=demo / "context.json", allow_draft=True).write_evidence_report(tmp_path / "import")
    out = assess_archive(archive, tmp_path / "assessed", snapshot_paths=sorted((demo / "knowledge").glob("*.json")))
    return {"demo": demo, "import": archive, "assessment": out, "root": tmp_path}


def _options(assessment: Path, entity_id: str) -> dict:
    rows = [row for row in read_json(assessment / "intervention_options.json") if row["entity_id"] == entity_id]
    return {row["modality"]: row for row in rows}


def test_modality_screen_keeps_mechanisms_separate_and_unranked(assessed):
    gene_a = _options(assessed["assessment"], "DEMO_GENE_A")
    gene_b = _options(assessed["assessment"], "DEMO_GENE_B")
    assert gene_a["small_molecule"]["disposition"] == "open_research_probe"
    assert gene_a["small_molecule"]["use"] == "research_probe"
    assert gene_a["small_molecule"]["therapeutic_concept"] is False
    assert gene_a["small_molecule"]["rank"] is None
    assert {"selectivity", "tissue_exposure"} <= set(gene_a["small_molecule"]["open_questions"])
    assert any("enzyme" in item and "does not assign a modality" in item for item in gene_a["small_molecule"]["basis"])
    assert gene_a["antibody"]["disposition"] == "attribute_mismatch"
    assert gene_a["peptide"]["disposition"] == "attribute_mismatch"
    assert {item["id"] for item in gene_a["siRNA"]["conditions"]} != {item["id"] for item in gene_a["ASO"]["conditions"]}
    assert gene_a["siRNA"]["disposition"] == gene_a["ASO"]["disposition"] == "pending_conditions"
    assert gene_a["mRNA"]["disposition"] == gene_a["gene_delivery"]["disposition"] == "attribute_mismatch"
    assert gene_a["DNA_editing"]["disposition"] == "pending_conditions"
    assert "persistence" in gene_a["DNA_editing"]["open_questions"]
    assert all(row["disposition"] == "insufficient_records" for row in gene_b.values())
    assert all(row["rank"] is None and row["not_a_recommendation"] is True for row in gene_a.values())
    plans = create_plans(assessed["assessment"], assessed["root"] / "plans")
    plan = next(row for row in read_json(plans / "plans.json") if row["entity_id"] == "DEMO_GENE_A")
    assert plan["modality_screen"]["open_research_probes"] == ["small_molecule"]
    assert plan["modality_screen"]["attribute_mismatches"] == ["antibody", "peptide", "mRNA", "gene_delivery"]
    assert plan["modality_screen"]["pending_conditions"] == ["siRNA", "ASO", "DNA_editing"]
    assert plan["modality_screen"]["not_a_recommendation"] is True


def test_unreviewed_location_and_cross_modality_tools_are_not_reused():
    row = {"hypothesis_id": "h", "entity_key": "e", "entity_id": "G", "entity_type": "gene",
           "intervention_direction": "inhibit", "dimensions": {"direction_evidence": "supported"}}
    options = {item["modality"]: item for item in screen_modalities(row, [
        {"evidence_type": "identity", "reviewed": False, "subcellular_location": "extracellular", "stance": "supports"},
        {"evidence_type": "tool", "reviewed": True, "modality": "siRNA", "intervention_mechanism": "RNA_knockdown", "tool_id": "S"},
    ])}
    assert options["antibody"]["disposition"] != "attribute_mismatch"
    knockdown = {item["id"]: item["status"] for item in options["siRNA"]["conditions"]}
    aso = {item["id"]: item["status"] for item in options["ASO"]["conditions"]}
    assert knockdown["rna_knockdown"] == "met"
    assert aso["splice_modulation"] == "unknown"
    assert aso["aso_rna_knockdown"] == "unknown"
    assert options["siRNA"]["disposition"] == "pending_conditions"
    metabolite = screen_modalities({"hypothesis_id": "h2", "entity_key": "m", "entity_id": "M", "entity_type": "metabolite",
                                     "intervention_direction": "inhibit", "dimensions": {}}, [])
    assert metabolite and all(item["disposition"] == "insufficient_identity" for item in metabolite)


def test_tool_attributes_cannot_be_stored_as_identity(tmp_path):
    demo = create_demo(tmp_path / "demo")
    path = demo / "knowledge" / "UniProt.synthetic.json"
    value = read_json(path)
    value["records"][0]["modality"] = "antibody"
    write_json(path, value)
    with pytest.raises(BundleValidationError) as exc:
        load_snapshots([path])
    assert any(item.rule_id == "TOOL_ATTRIBUTE" for item in exc.value.report.diagnostics)


def test_ortholog_map_keeps_one_to_many_and_does_not_transfer_claims(assessed):
    human = read_json(assessed["demo"] / "knowledge" / "OpenTargets.synthetic.json")
    human["source"].update(name="curated", release="synthetic-human-1")
    human["records"][0].update(record_id="human_direction", primary_record_id="synthetic:human", entity_id="HUMAN_A1",
                               taxon_id=9606, direction="activate")
    human_path = assessed["root"] / "human.json"
    write_json(human_path, human)
    ortholog = {"format": "theraweave.ortholog-map", "version": "0.1", "reviewed": True, "reviewer": "Synthetic reviewer",
                "source_name": "synthetic-compara", "source_release": "synthetic-1", "retrieved_at": "2026-10-31",
                "method": "synthetic orthology fixture", "synthetic": True, "links": [{
                    "source_entity_id": "DEMO_GENE_A", "source_namespace": "demo", "source_taxon_id": 10090,
                    "orthology_type": "one2many", "orthologs": [
                        {"entity_id": "HUMAN_A1", "namespace": "demo", "taxon_id": 9606},
                        {"entity_id": "HUMAN_A2", "namespace": "demo", "taxon_id": 9606},
                    ]}]}
    path = assessed["root"] / "orthologs.json"
    write_json(path, ortholog)
    out = assess_archive(assessed["import"], assessed["root"] / "ortholog-assessment",
                         snapshot_paths=[*sorted((assessed["demo"] / "knowledge").glob("*.json")), human_path], ortholog_map=path)
    gene = next(row for row in read_json(out / "assessments.json") if row["entity_id"] == "DEMO_GENE_A")
    assert gene["intervention_direction"] == "inhibit"
    assert gene["ortholog_status"] == "reviewed_map"
    assert gene["orthology_type"] == "one2many"
    assert [item["entity_id"] for item in gene["human_orthologs"]] == ["HUMAN_A1", "HUMAN_A2"]
    assert gene["dimensions"]["human_translation"] == "limited"
    assert "human_functional_conservation" in gene["gaps"]
    assert "HUMAN_A1" not in {row["entity_id"] for row in read_json(out / "assessments.json")}
    ortholog["links"][0].update(orthology_type="none", orthologs=[])
    write_json(path, ortholog)
    none = assess_archive(assessed["import"], assessed["root"] / "no-ortholog",
                          snapshot_paths=sorted((assessed["demo"] / "knowledge").glob("*.json")), ortholog_map=path)
    gene = next(row for row in read_json(none / "assessments.json") if row["entity_id"] == "DEMO_GENE_A")
    assert gene["ortholog_status"] == "no_human_ortholog"
    assert gene["human_orthologs"] == []
    assert "no_human_ortholog" in gene["gaps"]
    ortholog["links"][0].update(orthology_type="one2one", orthologs=[
        {"entity_id": "HUMAN_A1", "namespace": "demo", "taxon_id": 9606},
        {"entity_id": "HUMAN_A2", "namespace": "demo", "taxon_id": 9606},
    ])
    write_json(path, ortholog)
    with pytest.raises(BundleValidationError) as exc:
        assess_archive(assessed["import"], assessed["root"] / "bad-count", snapshot_paths=[], ortholog_map=path)
    assert any(item.rule_id == "ORTHOLOGY_COUNT" for item in exc.value.report.diagnostics)


def test_synthetic_identity_map_cannot_support_unmarked_input(assessed):
    path = assessed["import"] / "manifest.json"
    value = read_json(path)
    value["synthetic_input"] = False
    write_json(path, value)
    ortholog = {"format": "theraweave.ortholog-map", "version": "0.1", "reviewed": True, "reviewer": "Synthetic reviewer",
                "source_name": "synthetic-compara", "source_release": "synthetic-1", "retrieved_at": "2026-10-31",
                "method": "synthetic orthology fixture", "synthetic": True, "links": []}
    map_path = assessed["root"] / "empty-orthologs.json"
    write_json(map_path, ortholog)
    with pytest.raises(ValueError, match="Synthetic knowledge"):
        assess_archive(assessed["import"], assessed["root"] / "rejected", ortholog_map=map_path)


def test_reaction_map_preserves_one_flux_source_and_unknown_direction(tmp_path):
    demo = create_demo(tmp_path / "demo", include_reaction=True)
    archive = DiscoveryProject.from_bundle(demo / "bundle", context=demo / "context.json", allow_draft=True).write_evidence_report(tmp_path / "import")
    reaction_map = {"format": "theraweave.reaction-map", "version": "0.1", "reviewed": True, "reviewer": "Synthetic reviewer",
                    "model_id": "synthetic-network", "model_version": "synthetic-1", "synthetic": True, "links": [{
                        "reaction_id": "DEMO_RXN_1", "namespace": "demo_network", "taxon_id": 10090, "relation": "OR",
                        "compartment": "cytosol", "directionality": "unknown", "cross_organ": False, "flux_control": "mapping_only",
                        "components": [
                            {"entity_id": "DEMO_GENE_A", "namespace": "demo", "entity_type": "gene"},
                            {"entity_id": "DEMO_ISOFORM_2", "namespace": "demo", "entity_type": "gene"},
                        ]}]}
    path = tmp_path / "reactions.json"
    write_json(path, reaction_map)
    out = assess_archive(archive, tmp_path / "assessed", snapshot_paths=sorted((demo / "knowledge").glob("*.json")), reaction_map=path)
    rows = {row["entity_id"]: row for row in read_json(out / "assessments.json")}
    reaction, gene = rows["DEMO_RXN_1"], rows["DEMO_GENE_A"]
    assert reaction["bucket"] == "evidence_gap_first"
    assert reaction["intervention_direction"] == "unknown"
    assert reaction["qualifying_local_evidence_ids"]
    assert gene["bucket"] == "functional_validation_ready"
    link = read_json(out / "reaction_links.json")["links"][0]
    assert link["relation"] == "OR" and link["flux_control"] == "mapping_only"
    assert link["independent_flux_sources"] == 1
    assert link["evidence_ids"] == reaction["evidence_ids"]
    assert set(gene["evidence_ids"]).isdisjoint(link["evidence_ids"])
    components = {item["entity_id"]: item for item in link["components"]}
    assert components["DEMO_GENE_A"]["present_in_inventory"] is True
    assert components["DEMO_ISOFORM_2"]["present_in_inventory"] is False
    assert all(item["intervention_direction"] == "unknown" and item["not_a_control_or_inhibition_target"] for item in link["components"])
    assert "DEMO_ISOFORM_2" not in rows
    assert all(item["disposition"] == "insufficient_identity" for item in _options(out, "DEMO_RXN_1").values())
    reaction_map["links"][0]["reaction_id"] = "NOT_A_REACTION"
    write_json(path, reaction_map)
    with pytest.raises(BundleValidationError) as missing:
        assess_archive(archive, tmp_path / "missing", snapshot_paths=[], reaction_map=path)
    assert any(item.rule_id == "REACTION_ENTITY" for item in missing.value.report.diagnostics)
    reaction_map["links"][0].update(reaction_id="DEMO_RXN_1", relation="OR", components=reaction_map["links"][0]["components"][:1])
    write_json(path, reaction_map)
    with pytest.raises(BundleValidationError) as single:
        assess_archive(archive, tmp_path / "single-or", snapshot_paths=[], reaction_map=path)
    assert any(item.rule_id == "GPR_OR" for item in single.value.report.diagnostics)
    reaction_map["links"][0]["components"] = [
        {"entity_id": "DEMO_GENE_A", "namespace": "demo", "entity_type": "gene"},
        {"entity_id": "DEMO_ISOFORM_2", "namespace": "demo", "entity_type": "gene"},
    ]
    reaction_map["links"][0]["flux_control"] = "flux_control_supported"
    write_json(path, reaction_map)
    with pytest.raises(BundleValidationError) as control:
        assess_archive(archive, tmp_path / "control", snapshot_paths=[], reaction_map=path)
    assert any(item.rule_id == "JSON_SCHEMA" for item in control.value.report.diagnostics)


def _override(row, bucket):
    return {"hypothesis_id": row["hypothesis_id"], "operator": "Synthetic reviewer", "overridden_at": "2026-10-31T00:00:00Z",
            "rationale": "Synthetic decision record only", "requested_bucket": bucket, "evidence_ids": [row["evidence_ids"][0]]}


def test_override_cannot_relax_algorithm_or_blocking_risk(assessed):
    rows = {row["entity_id"]: row for row in read_json(assessed["assessment"] / "assessments.json")}
    relax = assessed["root"] / "relax.json"
    write_json(relax, _override(rows["DEMO_GENE_B"], "functional_validation_ready"))
    with pytest.raises(ValueError, match="cannot relax"):
        record_override(assessed["assessment"], relax, assessed["root"] / "rejected-override")
    hold = assessed["root"] / "hold.json"
    write_json(hold, _override(rows["DEMO_GENE_A"], "hold_for_review"))
    overridden = record_override(assessed["assessment"], hold, assessed["root"] / "held")
    saved = next(row for row in read_json(overridden / "assessments.json") if row["entity_id"] == "DEMO_GENE_A")
    assert saved["bucket"] == "hold_for_review"
    assert saved["algorithm_bucket"] == "functional_validation_ready"
    assert read_json(overridden / "decision_log.json")[0]["clears_blocking_risk"] is False
    plans = create_plans(overridden, assessed["root"] / "held-plans")
    plan = next(row for row in read_json(plans / "plans.json") if row["entity_id"] == "DEMO_GENE_A")
    review = {"reviewer": "Synthetic reviewer", "reviewed_at": "2026-10-31T00:00:00Z", "rationale": "Synthetic review",
              "primary_endpoint": {"name": "synthetic endpoint", "unit": "arbitrary_units", "desired_direction": "decrease",
                                   "minimum_meaningful_effect": 1.0, "confidence_level": 0.95},
              "design": {key: "Synthetic pre-specified design" for key in ("experimental_unit", "sample_size_basis", "randomization", "blinding", "comparison", "multiplicity_plan", "exclusions", "controls")},
              "decision_rule": "benefit_ci_excludes_zero_and_point_meets_minimum",
              "effort": {"decision_to_change": "marker_versus_functional_link", "cost_level": "not_recorded", "duration_level": "not_recorded",
                         "laboratory_capability": "not_recorded", "basis": "Synthetic review; no cost was calculated"}}
    write_json(assessed["root"] / "review.json", review)
    with pytest.raises(ValueError, match="Blocking risk"):
        review_plan(plans, plan["plan_id"], assessed["root"] / "review.json", assessed["root"] / "reviewed")
    write_json(relax, _override(saved, "functional_validation_ready"))
    with pytest.raises(ValueError, match="cannot relax"):
        record_override(overridden, relax, assessed["root"] / "cleared")
