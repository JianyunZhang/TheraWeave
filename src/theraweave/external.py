"""File handoff for an external prediction. No backend is executed."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .artifacts import new_archive, read_archive, read_member
from .contract import resource_json, schema_check
from .core import BundleValidationError, ValidationReport, content_id, read_json, write_json

_TASKS = {
    "docking": {"prediction_type": "docking_score", "quantity_kind": "binding_score", "molecule": True, "value": True, "sampling": False},
    "fep_absolute": {"prediction_type": "binding_free_energy", "quantity_kind": "free_energy", "molecule": True, "value": True, "sampling": False},
    "fep_relative": {"prediction_type": "relative_binding_free_energy", "quantity_kind": "free_energy", "molecule": True, "value": True, "sampling": False},
    "md": {"prediction_type": "conformational_summary", "quantity_kind": "conformational_descriptor", "molecule": False, "value": False, "sampling": True},
    "structure_preparation": {"prediction_type": "structural_compatibility", "quantity_kind": "structural_descriptor", "molecule": False, "value": False, "sampling": False},
    "antibody_model": {"prediction_type": "antibody_property", "quantity_kind": "structural_descriptor", "molecule": False, "value": False, "sampling": False},
}


def _load(path, schema_name: str) -> dict:
    report = ValidationReport()
    name = Path(path).name
    try:
        document = read_json(Path(path))
    except (OSError, ValueError) as error:
        report.add("EXTERNAL_READ", "error", name, str(error))
        raise BundleValidationError(report) from error
    schema_check(document, resource_json(schema_name), report, name)
    if not report.valid:
        raise BundleValidationError(report)
    return document


def hypothesis_version(row: dict) -> str:
    return content_id({"hypothesis_id": row["hypothesis_id"], "bucket": row["bucket"],
                       "intervention_direction": row["intervention_direction"], "gaps": row["gaps"]})


def prepare_external_request(assessment_directory, request_path, destination) -> Path:
    root, manifest = read_archive(assessment_directory, "theraweave.assessment-preview")
    context = read_member(root, manifest, "context.json")
    assessments = read_member(root, manifest, "assessments.json")
    request = _load(request_path, "external_request.schema.json")
    datetime.fromisoformat(request["reviewed_at"].replace("Z", "+00:00"))
    matches = [row for row in assessments if row["hypothesis_id"] == request["hypothesis_id"]]
    if len(matches) != 1:
        raise ValueError("Hypothesis ID is missing or ambiguous.")
    row = matches[0]
    if request["gap_id"] not in row["gaps"]:
        raise ValueError("The request must name a gap already recorded for this hypothesis.")
    task = _TASKS[request["task_type"]]
    if task["molecule"] and request["molecule"] is None:
        raise ValueError("This task requires a stable molecule identifier and content hash, not a name alone.")
    target = request["target"]
    same_entity = (target["entity_id"], target["namespace"], target["taxon_id"]) == (row["entity_id"], row["namespace"], row["taxon_id"])
    if target["identity_basis"] in {"same_entity_as_hypothesis", "reviewed_construct"} and not same_entity:
        raise ValueError("The construct must stay on the assessed entity.")
    if target["identity_basis"] == "reviewed_ortholog":
        orthologs = {(item["entity_id"], item["namespace"], item["taxon_id"]) for item in row.get("human_orthologs", [])}
        if (target["entity_id"], target["namespace"], target["taxon_id"]) not in orthologs or target["orthology_type"] is None or not target["ortholog_reviewer"]:
            raise ValueError("A reviewed ortholog request must use an ortholog already recorded on the assessment.")
    elif target["orthology_type"] is not None or target["ortholog_reviewer"] is not None:
        raise ValueError("Orthology fields belong only on a reviewed-ortholog request.")
    prepared = {**request, "hypothesis_version": hypothesis_version(row), "assessment_run_id": manifest["run_id"],
                "status": "prepared_not_executed", "allowed_conclusion_is_not_phenotype": True}
    with new_archive(destination, format_name="theraweave.external-request", identity={"parent_run_id": manifest["run_id"],
                     "request_hash": content_id(prepared)}, forbidden_roots=[root]) as temp:
        write_json(temp / "context.json", context)
        write_json(temp / "request.json", prepared)
        write_json(temp / "limits.json", {"executed": False, "network_authorized": False, "fills_functional_gap": False,
                                          "counts_as_independent_replication": False})
    return Path(destination).resolve()


def record_external_result(request_directory, result_path, destination) -> Path:
    root, manifest = read_archive(request_directory, "theraweave.external-request")
    context = read_member(root, manifest, "context.json")
    prepared = read_member(root, manifest, "request.json")
    result = _load(result_path, "external_result.schema.json")
    if result["request_id"] != prepared["request_id"] or result["hypothesis_id"] != prepared["hypothesis_id"] or result["hypothesis_version"] != prepared["hypothesis_version"]:
        raise ValueError("Result must cite the exact prepared request and hypothesis version.")
    task = _TASKS[prepared["task_type"]]
    if result["prediction_type"] != task["prediction_type"] or result["quantity_kind"] != task["quantity_kind"]:
        raise ValueError("Prediction type does not match the prepared task. Scores are not converted into one another.")
    completed = result["status"] == "completed"
    if completed and task["value"] and (isinstance(result["value"], bool) or not isinstance(result["value"], (int, float)) or result["unit"] is None):
        raise ValueError("A completed scored task needs a finite value and unit.")
    if completed and not task["value"] and result["value"] is not None:
        raise ValueError("This task does not reduce to a single scored value.")
    if not completed and result["value"] is not None:
        raise ValueError("A failed or inconclusive run cannot carry a usable value.")
    if completed and result["favorable_direction"] == "not_applicable" and task["value"]:
        raise ValueError("A scored prediction needs an explicit favorable direction.")
    if completed and (result["reference_system"] is None or (task["sampling"] and not result["sampling_note"])):
        raise ValueError("Completed runs need their reference system; molecular-dynamics runs also need a sampling note.")
    interpretation = "predicted_unconfirmed" if completed else "inconclusive"
    recorded = {**result, "evidence_level": "predicted", "measurement_basis": "predicted", "interpretation": interpretation,
                "independent_support_added": 0, "overwrites_observations": False, "fills_functional_gap": False,
                "same_variable_as_phenotype_or_flux": False, "time_series_is_biological_replicate": False,
                "allowed_conclusion": prepared["allowed_conclusion"], "derived_from": [prepared["request_id"]]}
    with new_archive(destination, format_name="theraweave.external-result", identity={"parent_run_id": manifest["run_id"],
                     "result_hash": content_id(result)}, forbidden_roots=[root]) as temp:
        write_json(temp / "context.json", context)
        write_json(temp / "request.json", prepared)
        write_json(temp / "result.json", recorded)
    return Path(destination).resolve()
