import pytest

from theraweave import DiscoveryProject
from theraweave.assessment import assess_archive
from theraweave.compounds import review_compounds
from theraweave.core import BundleValidationError, read_json, write_json
from theraweave.demo import create_demo


def _record(**overrides):
    record = {
        "record_id": "direct-ic50", "compound_id": "SYNTHETIC_DRUG", "entity_id": "DEMO_GENE_A", "namespace": "demo",
        "taxon_id": 10090, "assay_taxon_id": 10090, "context_id": "synthetic_context", "link_type": "direct_target",
        "direction": "inhibit", "approval_status": "approved", "assay_type": "functional", "activity_type": "IC50",
        "relation": "=", "value": 100.0, "unit": "nM", "property_kind": None, "property_basis": None,
        "indication": "synthetic phenotype", "citations": ["urn:synthetic:compound"], "statement": "Synthetic direct-target record.",
        "reviewed": True, "reviewer": "Synthetic reviewer",
    }
    record.update(overrides)
    return record


def _document(records, synthetic=True):
    return {"format": "theraweave.compound-review", "version": "0.1", "reviewed": True, "reviewer": "Synthetic reviewer",
            "synthetic": synthetic, "records": records}


@pytest.fixture
def assessed(tmp_path):
    demo = create_demo(tmp_path / "demo")
    archive = DiscoveryProject.from_bundle(demo / "bundle", context=demo / "context.json", allow_draft=True).write_evidence_report(tmp_path / "import")
    out = assess_archive(archive, tmp_path / "assessed", snapshot_paths=sorted((demo / "knowledge").glob("*.json")))
    return {"root": tmp_path, "assessment": out}


def test_direct_target_clue_is_not_ranked_or_recommended(assessed):
    path = assessed["root"] / "compounds.json"
    write_json(path, _document([
        _record(record_id="b-ki", activity_type="Ki", value=1.0, unit="nM"),
        _record(),
        _record(record_id="pathway", link_type="pathway_only", activity_type=None, relation=None, value=None, unit=None, direction="unknown"),
        _record(record_id="cyto", assay_type="cytotoxicity"),
        _record(record_id="property", link_type="property_only", direction="unknown", approval_status="not_recorded", assay_type="unknown",
                activity_type=None, relation=None, value=2.0, unit="1", property_kind="logP", property_basis="predicted", indication=None),
        _record(record_id="opposite", direction="activate"),
        _record(record_id="human-assay", assay_taxon_id=9606),
        _record(record_id="draft", reviewed=False, reviewer=None),
    ]))
    out = review_compounds(assessed["assessment"], path, assessed["root"] / "review")
    rows = {row["record_id"]: row for row in read_json(out / "compounds.json")}
    assert [row["record_id"] for row in read_json(out / "compounds.json")] == sorted(rows)
    assert rows["direct-ic50"]["disposition"] == "repurposing_clue"
    assert rows["direct-ic50"]["repurposing_candidate"] is True
    assert rows["direct-ic50"]["therapeutic_recommendation"] is False
    assert rows["direct-ic50"]["potency_rank"] is None and rows["b-ki"]["potency_rank"] is None
    assert rows["pathway"]["disposition"] == "pathway_clue" and rows["pathway"]["repurposing_candidate"] is False
    assert "approval_does_not_upgrade_a_pathway_clue" in rows["pathway"]["reasons"]
    assert rows["cyto"]["disposition"] == "not_target_engagement"
    assert rows["property"]["disposition"] == "property_record" and rows["property"]["admet_conclusion"] is False
    assert rows["opposite"]["disposition"] == "direction_not_matched"
    assert rows["human-assay"]["disposition"] == "cross_species_activity"
    assert rows["draft"]["disposition"] == "recorded_only"
    limits = read_json(out / "limits.json")
    assert limits["virtual_screening"] is False and limits["mixed_activity_comparison"] is False


def test_incomplete_activity_and_unmatched_entity_are_rejected(assessed):
    path = assessed["root"] / "bad.json"
    write_json(path, _document([_record(unit=None)]))
    with pytest.raises(BundleValidationError) as shape:
        review_compounds(assessed["assessment"], path, assessed["root"] / "shape")
    assert any(item.rule_id == "ACTIVITY_SHAPE" for item in shape.value.report.diagnostics)
    write_json(path, _document([_record(entity_id="NOT_A_TARGET")]))
    with pytest.raises(BundleValidationError) as missing:
        review_compounds(assessed["assessment"], path, assessed["root"] / "missing")
    assert any(item.rule_id == "COMPOUND_ENTITY" for item in missing.value.report.diagnostics)


def test_synthetic_compounds_require_a_synthetic_assessment(assessed):
    manifest = read_json(assessed["assessment"] / "manifest.json")
    manifest["identity"]["synthetic_input"] = False
    write_json(assessed["assessment"] / "manifest.json", manifest)
    path = assessed["root"] / "compounds.json"
    write_json(path, _document([_record()]))
    with pytest.raises(ValueError, match="Synthetic compound records"):
        review_compounds(assessed["assessment"], path, assessed["root"] / "rejected")
