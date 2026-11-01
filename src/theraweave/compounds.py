"""Local compound review. Pathway membership, approval, and properties stay in separate claims."""
from __future__ import annotations

from pathlib import Path

from .artifacts import new_archive, read_archive, read_member
from .contract import resource_json, schema_check
from .core import BundleValidationError, ValidationReport, read_json, write_json

_ACTIVITY = ("activity_type", "relation", "value", "unit")


def review_compounds(assessment_directory, compounds_path, destination) -> Path:
    root, manifest = read_archive(assessment_directory, "theraweave.assessment-preview")
    context = read_member(root, manifest, "context.json")
    assessments = read_member(root, manifest, "assessments.json")
    document = _load(compounds_path)
    if document["synthetic"] and not manifest.get("identity", {}).get("synthetic_input"):
        raise ValueError("Synthetic compound records are accepted only with an explicitly synthetic assessment.")
    by_entity = {}
    for row in assessments:
        key = (row["entity_id"], row["namespace"], row["taxon_id"])
        if key in by_entity:
            raise ValueError(f"Assessment entity is ambiguous: {key[0]}")
        by_entity[key] = row
    seen = set()
    reviewed = []
    report = ValidationReport()
    name = Path(compounds_path).name
    for record in document["records"]:
        if record["record_id"] in seen:
            report.add("COMPOUND_RECORD_ID", "error", name, "Repeated compound record_id.", row_or_record_id=record["record_id"])
        seen.add(record["record_id"])
        if record["reviewed"] and not record.get("reviewer"):
            report.add("COMPOUND_REVIEWER", "error", name, "A reviewed compound record needs its own reviewer.", row_or_record_id=record["record_id"])
        _activity_shape(record, report, name)
        hypothesis = by_entity.get((record["entity_id"], record["namespace"], record["taxon_id"]))
        if hypothesis is None:
            report.add("COMPOUND_ENTITY", "error", name, "Compound record does not match an assessed entity.", row_or_record_id=record["record_id"])
            continue
        reviewed.append({**record, "hypothesis_id": hypothesis["hypothesis_id"], **_classify(record, hypothesis)})
    if not report.valid:
        raise BundleValidationError(report)
    reviewed.sort(key=lambda row: row["record_id"])
    with new_archive(destination, format_name="theraweave.compound-review", identity={"parent_run_id": manifest["run_id"],
                     "synthetic": document["synthetic"]}, forbidden_roots=[root]) as temp:
        write_json(temp / "context.json", context)
        write_json(temp / "compounds.json", reviewed)
        write_json(temp / "limits.json", {"potency_rank": None, "mixed_activity_comparison": False, "admet_conclusion": False,
                                          "virtual_screening": False, "therapeutic_recommendation": False, "network_used": False})
    return Path(destination).resolve()


def _load(path) -> dict:
    report = ValidationReport()
    name = Path(path).name
    try:
        document = read_json(Path(path))
    except (OSError, ValueError) as error:
        report.add("COMPOUND_READ", "error", name, str(error))
        raise BundleValidationError(report) from error
    schema_check(document, resource_json("compound_review.schema.json"), report, name)
    if not report.valid:
        raise BundleValidationError(report)
    return document


def _activity_shape(record: dict, report: ValidationReport, name: str) -> None:
    present = [record[key] is not None for key in _ACTIVITY]
    if record["link_type"] == "property_only":
        if record["activity_type"] is not None or record["relation"] is not None or None in (record["property_kind"], record["property_basis"], record["value"], record["unit"]):
            report.add("PROPERTY_SHAPE", "error", name, "A property record needs kind, basis, value, and unit, and cannot carry an activity type.", row_or_record_id=record["record_id"])
        return
    if record["property_kind"] is not None or record["property_basis"] is not None:
        report.add("PROPERTY_SHAPE", "error", name, "Property fields belong only on a property record.", row_or_record_id=record["record_id"])
    if any(present) and not all(present):
        report.add("ACTIVITY_SHAPE", "error", name, "Activity type, relation, value, and unit must be recorded together.", row_or_record_id=record["record_id"])
    if isinstance(record["value"], bool):
        report.add("ACTIVITY_VALUE", "error", name, "Activity value must be numeric.", row_or_record_id=record["record_id"])


def _classify(record: dict, hypothesis: dict) -> dict:
    result = {"repurposing_candidate": False, "therapeutic_recommendation": False, "potency_rank": None,
              "admet_conclusion": False, "approval_is_sufficient": False, "disposition": "recorded_only", "reasons": []}
    if not record["reviewed"]:
        result["reasons"].append("unreviewed_record_is_not_used")
        return result
    if record["link_type"] == "property_only":
        result["disposition"] = "property_record"
        result["reasons"].append("property_is_not_potency_or_efficacy")
        if record["property_basis"] == "predicted":
            result["reasons"].append("predicted_property_is_not_a_measurement")
        return result
    if record["link_type"] == "pathway_only":
        result["disposition"] = "pathway_clue"
        result["reasons"].append("same_pathway_is_not_a_repurposing_candidate")
        if record["approval_status"] == "approved":
            result["reasons"].append("approval_does_not_upgrade_a_pathway_clue")
        return result
    if record["assay_type"] in {"cytotoxicity", "phenotypic"}:
        result["disposition"] = "not_target_engagement"
        result["reasons"].append("phenotypic_or_cytotoxicity_assay_is_not_binding_evidence")
        return result
    if record["context_id"] != hypothesis["context_id"]:
        result["disposition"] = "indication_not_matched"
        result["reasons"].append("indication_context_does_not_match_the_hypothesis")
        return result
    if record["assay_taxon_id"] != hypothesis["taxon_id"]:
        result["disposition"] = "cross_species_activity"
        result["reasons"].append("assay_species_does_not_match_the_hypothesis")
        return result
    if hypothesis["intervention_direction"] == "unknown" or record["direction"] != hypothesis["intervention_direction"]:
        result["disposition"] = "direction_not_matched"
        return result
    if record["assay_type"] not in {"binding", "functional"}:
        result["disposition"] = "assay_not_usable"
        return result
    result.update(disposition="repurposing_clue", repurposing_candidate=True)
    result["reasons"].extend(["selectivity_not_established", "exposure_not_established", "not_a_treatment_recommendation"])
    return result
