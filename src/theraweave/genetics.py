"""Reviewed genetic records. This is an import, not a GWAS, colocalization, or MR engine."""
from __future__ import annotations

from pathlib import Path

from .contract import resource_json, schema_check
from .core import BundleValidationError, ValidationReport, read_json, sha256_file

MR_LIMITS = ("instrument_strength", "horizontal_pleiotropy", "sample_overlap", "directionality")
_DIRECTION_BASES = {"coding_variant", "functional_assay", "reviewed_manual"}


def load_genetic_evidence(path, entities: list[dict]) -> dict:
    report = ValidationReport()
    name = Path(path).name
    try:
        document = read_json(Path(path))
    except (OSError, ValueError) as error:
        report.add("GENETIC_READ", "error", name, str(error))
        raise BundleValidationError(report) from error
    schema_check(document, resource_json("genetic_evidence.schema.json"), report, name)
    if not report.valid:
        raise BundleValidationError(report)
    known = {(row["entity_id"], row["namespace"], row["taxon_id"]) for row in entities}
    seen = set()
    records = []
    for record in document["records"]:
        if record["record_id"] in seen:
            report.add("GENETIC_RECORD_ID", "error", name, "Repeated genetic record_id.", row_or_record_id=record["record_id"])
        seen.add(record["record_id"])
        if record["reviewed"] and not record.get("reviewer"):
            report.add("GENETIC_REVIEWER", "error", name, "A reviewed genetic record needs its own reviewer.", row_or_record_id=record["record_id"])
        key = (record["entity_id"], record["namespace"], record["taxon_id"])
        if key not in known:
            report.add("GENETIC_ENTITY", "error", name, "Genetic record does not match an imported entity.", row_or_record_id=record["record_id"])
        records.append(_classify(record))
    if not report.valid:
        raise BundleValidationError(report)
    return {"reviewer": document["reviewer"], "synthetic": document["synthetic"], "sha256": sha256_file(Path(path)), "records": records}


def _classify(record: dict) -> dict:
    classified = {**record, "nearest_gene_is_causal": False, "direction_used": False, "mechanism_used": False,
                  "identity_used": False, "use": "recorded_only", "reasons": []}
    if not record["reviewed"]:
        classified["reasons"].append("unreviewed_record_is_not_used")
        return classified
    if record["context_id"] is None:
        classified["reasons"].append("context_required_for_use")
        return classified
    if record["mapping_basis"] == "nearest_gene":
        classified["reasons"].append("nearest_gene_is_not_a_causal_target")
        return classified
    method = record["method"]
    if method == "colocalization":
        classified["use"] = "shared_signal"
        classified["reasons"].append("colocalization_does_not_prove_mediation")
        return classified
    if method == "gwas_association":
        classified["reasons"].append("gwas_association_is_not_direction_or_mechanism")
        return classified
    if method == "fine_mapping":
        if record["mapping_basis"] == "credible_set" and record["stance"] == "supports":
            classified.update(use="identity_only", identity_used=True)
        classified["reasons"].append("fine_mapping_does_not_set_direction")
        return classified
    usable_direction = record["allele_direction"] != "unknown" and record["stance"] in {"supports", "contradicts"}
    if method == "mendelian_randomization":
        missing = [item for item in MR_LIMITS if item not in set(record["limitations"])]
        if missing or not usable_direction:
            classified["reasons"].append("mr_not_used_without_reviewed_direction_and_limitation_statements")
            classified["reasons"].extend(f"missing_{item}" for item in missing)
            return classified
        classified.update(use="direction", direction_used=True)
        classified["reasons"].append("mr_direction_is_not_functional_proof")
        return classified
    if method == "functional_variant" and record["mapping_basis"] in _DIRECTION_BASES and usable_direction:
        classified.update(use="direction", direction_used=True)
        if record["mapping_basis"] == "functional_assay" and record["stance"] == "supports":
            classified["mechanism_used"] = True
            classified["reasons"].append("assay_supports_a_direction_outside_this_model")
        else:
            classified["reasons"].append("variant_direction_is_not_a_perturbation_in_this_model")
        return classified
    classified["reasons"].append("method_and_mapping_basis_not_used")
    return classified
