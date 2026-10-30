import pytest

from theraweave.core import read_json, write_json
from theraweave.knowledge import load_snapshots
from theraweave.source_adapters import convert_source


def metadata():
    return {"release": "synthetic-test", "retrieved_at": "2026-10-30", "origin_url": "urn:synthetic:source",
            "license": "Synthetic fixture only", "synthetic": True}


def test_uniprot_native_shape_remains_unreviewed_and_species_explicit(tmp_path):
    source = tmp_path / "uniprot.json"
    write_json(source, {"results": [{"primaryAccession": "SYNTHETIC_ACCESSION", "organism": {"taxonId": 10090}, "genes": [{"geneName": {"value": "SYMBOL"}}]}]})
    out = convert_source("UniProt", source, tmp_path / "normalized.json", metadata=metadata())
    row = load_snapshots([out])["records"][0]
    assert row["entity_id"] == "SYNTHETIC_ACCESSION" and row["namespace"] == "UniProt"
    assert row["reviewed"] is False and row["direction"] == "unknown"
    assert row["source_payload"]["genes"][0]["geneName"]["value"] == "SYMBOL"


def test_opentargets_score_cannot_become_causal_or_directional_evidence(tmp_path):
    source = tmp_path / "ot.json"
    write_json(source, [{"id": "synthetic_evidence", "targetId": "SYNTHETIC_ENSEMBL", "diseaseId": "synthetic_disease", "score": 0.99, "literature": ["synthetic_paper"]}])
    with pytest.raises(ValueError, match="taxon_id"):
        convert_source("OpenTargets", source, tmp_path / "invalid.json", metadata=metadata())
    out = convert_source("OpenTargets", source, tmp_path / "ot-normalized.json", metadata=metadata(), taxon_id=9606)
    row = read_json(out)["records"][0]
    assert row["evidence_type"] == "association" and row["stance"] == "unclear"
    assert row["source_payload"]["score"] == 0.99 and row["reviewed"] is False


def test_chembl_requires_unambiguous_target_species_and_preserves_mechanism(tmp_path):
    source, targets = tmp_path / "mechanisms.json", tmp_path / "targets.json"
    write_json(source, {"mechanisms": [{"molecule_chembl_id": "SYNTHETIC_MOLECULE", "target_chembl_id": "SYNTHETIC_TARGET", "action_type": "INHIBITOR"}]})
    write_json(targets, {"targets": [{"target_chembl_id": "SYNTHETIC_TARGET", "target_type": "SINGLE PROTEIN", "tax_id": 10090, "target_components": [{"accession": "SYNTHETIC_PROTEIN"}]}]})
    out = convert_source("ChEMBL", source, tmp_path / "chembl-normalized.json", metadata=metadata(), target_map=targets)
    value = read_json(out)
    assert "target_map" in value["source"]["auxiliary_input_hashes"]
    row = value["records"][0]
    assert row["tool_id"] == "SYNTHETIC_MOLECULE" and row["entity_id"] == "SYNTHETIC_PROTEIN"
    assert row["direction"] == "unknown" and row["reviewed"] is False
    changed = read_json(targets)
    changed["targets"][0]["target_components"].append({"accession": "OTHER"})
    write_json(targets, changed)
    with pytest.raises(ValueError, match="Ambiguous"):
        convert_source("ChEMBL", source, tmp_path / "ambiguous.json", metadata=metadata(), target_map=targets)


def test_metadata_cannot_override_source_name(tmp_path):
    with pytest.raises(ValueError, match="Metadata"):
        convert_source("UniProt", tmp_path / "unused.json", tmp_path / "out.json", metadata={**metadata(), "name": "ChEMBL"})
