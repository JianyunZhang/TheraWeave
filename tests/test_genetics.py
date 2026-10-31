import pytest

from theraweave import DiscoveryProject
from theraweave.assessment import assess_archive
from theraweave.core import BundleValidationError, read_json, write_json
from theraweave.demo import create_demo


def _record(**overrides):
    record = {
        "record_id": "genetic-1", "entity_id": "DEMO_GENE_B", "namespace": "demo", "taxon_id": 10090,
        "context_id": "synthetic_context", "method": "gwas_association", "mapping_basis": "nearest_gene",
        "allele_direction": "inhibit", "ancestry": "synthetic", "genome_build": "GRCm39", "locus": "synthetic:chr1:1-2",
        "tissue": "liver", "endpoint": "synthetic phenotype", "stance": "supports", "limitations": ["synthetic"],
        "citations": ["urn:synthetic:genetic"], "statement": "Synthetic genetic record.", "reviewed": True,
        "reviewer": "Synthetic reviewer",
    }
    record.update(overrides)
    return record


def _document(records):
    return {"format": "theraweave.genetic-evidence", "version": "0.1", "reviewed": True, "reviewer": "Synthetic reviewer",
            "synthetic": True, "records": records}


@pytest.fixture
def imported(tmp_path):
    demo = create_demo(tmp_path / "demo")
    archive = DiscoveryProject.from_bundle(demo / "bundle", context=demo / "context.json", allow_draft=True).write_evidence_report(tmp_path / "import")
    snapshots = sorted((demo / "knowledge").glob("*.json"))
    return {"root": tmp_path, "import": archive, "snapshots": snapshots}


def _gene(path, entity_id):
    return next(row for row in read_json(path / "assessments.json") if row["entity_id"] == entity_id)


def test_opposite_signs_remain_a_clue_without_setting_direction(imported):
    bare = assess_archive(imported["import"], imported["root"] / "bare")
    gene_a, gene_b = _gene(bare, "DEMO_GENE_A"), _gene(bare, "DEMO_GENE_B")
    assert gene_a["sign_pattern"]["status"] == "opposite_direction"
    assert gene_a["sign_pattern"]["sets_intervention_direction"] is False
    assert gene_a["sign_pattern"]["establishes_causal_reversal"] is False
    assert gene_a["intervention_direction"] == "unknown"
    assert gene_b["sign_pattern"]["status"] == "not_assessed"
    compared = read_json(bare / "comparisons.json")
    assert compared["accuracy"] is None and compared["labels"] is None and compared["ranked_winner"] is None
    assert compared["absolute_effect_order"][0]["feature_id"] == "DEMO_GENE_A"
    assert compared["without_mfa"]["status"] == "not_applicable"


def test_comparisons_report_knowledge_changes_without_an_accuracy(imported):
    out = assess_archive(imported["import"], imported["root"] / "assessed", snapshot_paths=imported["snapshots"])
    compared = read_json(out / "comparisons.json")
    changed = {row["entity_id"]: row for row in compared["without_external_knowledge"]["bucket_or_direction_changes"]}
    assert changed["DEMO_GENE_A"]["full"]["intervention_direction"] == "inhibit"
    assert changed["DEMO_GENE_A"]["alternate"]["intervention_direction"] == "unknown"
    assert changed["DEMO_GENE_A"]["alternate"]["bucket"] == "evidence_gap_first"
    source = next(row for row in compared["single_source"] if row["source"].startswith("OpenTargets:"))
    assert any(row["entity_id"] == "DEMO_GENE_A" and row["alternate"]["bucket"] == "evidence_gap_first" for row in source["bucket_or_direction_changes"])


def test_genetic_methods_do_not_grant_each_others_claims(imported):
    path = imported["root"] / "genetic.json"
    write_json(path, _document([
        _record(record_id="nearest", entity_id="DEMO_GENE_A"),
        _record(record_id="coloc", method="colocalization", mapping_basis="qtl_colocalization", allele_direction="activate"),
        _record(record_id="fine", entity_id="DEMO_GENE_B", method="fine_mapping", mapping_basis="credible_set"),
        _record(record_id="mr", method="mendelian_randomization", mapping_basis="reviewed_manual"),
    ]))
    out = assess_archive(imported["import"], imported["root"] / "genetic", snapshot_paths=imported["snapshots"], genetic_evidence=path)
    gene_a = _gene(out, "DEMO_GENE_A")
    gene_b = _gene(out, "DEMO_GENE_B")
    stored = {row["record_id"]: row for row in read_json(out / "genetic_evidence.json")["records"]}
    assert gene_a["intervention_direction"] == "inhibit"
    assert gene_a["bucket"] == "functional_validation_ready"
    assert "nearest_gene_not_causal" in gene_a["gaps"]
    assert stored["nearest"]["direction_used"] is False and stored["nearest"]["nearest_gene_is_causal"] is False
    assert stored["coloc"]["use"] == "shared_signal" and stored["coloc"]["direction_used"] is False
    assert stored["mr"]["direction_used"] is False
    assert stored["fine"]["identity_used"] is True and stored["fine"]["direction_used"] is False
    assert gene_b["dimensions"]["identity_and_tools"] == "unknown"
    assert gene_b["intervention_direction"] == "unknown"


def test_functional_variant_can_conflict_but_not_replace_a_model_perturbation(imported):
    path = imported["root"] / "variant.json"
    write_json(path, _document([_record(record_id="variant", entity_id="DEMO_GENE_A", method="functional_variant",
                                       mapping_basis="coding_variant", allele_direction="activate")]))
    out = assess_archive(imported["import"], imported["root"] / "conflict", snapshot_paths=imported["snapshots"], genetic_evidence=path)
    gene = _gene(out, "DEMO_GENE_A")
    assert gene["bucket"] == "conflict_resolution_first"
    assert gene["intervention_direction"] == "unknown"
    assert "genetic_evidence_is_not_this_model_perturbation" in gene["gaps"]
    assert read_json(out / "genetic_evidence.json")["records"][0]["direction_used"] is True


def test_removed_mfa_observations_do_not_invent_an_enzyme_direction(tmp_path):
    demo = create_demo(tmp_path / "demo", include_reaction=True)
    archive = DiscoveryProject.from_bundle(demo / "bundle", context=demo / "context.json", allow_draft=True).write_evidence_report(tmp_path / "import")
    out = assess_archive(archive, tmp_path / "assessed", snapshot_paths=sorted((demo / "knowledge").glob("*.json")))
    compared = read_json(out / "comparisons.json")["without_mfa"]
    assert compared["status"] == "compared" and compared["observations_removed"] == 1
    reaction = _gene(out, "DEMO_RXN_1")
    assert reaction["intervention_direction"] == "unknown"
    assert all(row["alternate"]["intervention_direction"] == "unknown" for row in compared["bucket_or_direction_changes"] if row["entity_id"] == "DEMO_RXN_1")


def test_synthetic_or_unmatched_genetic_records_are_rejected(imported):
    path = imported["root"] / "bad.json"
    write_json(path, _document([_record(entity_id="NOT_A_GENE")]))
    with pytest.raises(BundleValidationError) as missing:
        assess_archive(imported["import"], imported["root"] / "missing", genetic_evidence=path)
    assert any(item.rule_id == "GENETIC_ENTITY" for item in missing.value.report.diagnostics)
    manifest = read_json(imported["import"] / "manifest.json")
    manifest["synthetic_input"] = False
    write_json(imported["import"] / "manifest.json", manifest)
    write_json(path, _document([]))
    with pytest.raises(ValueError, match="Synthetic knowledge"):
        assess_archive(imported["import"], imported["root"] / "synthetic", genetic_evidence=path)
