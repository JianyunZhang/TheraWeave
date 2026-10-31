"""Candidate-list intake. Statistics and background enrichment are out of scope."""
from __future__ import annotations

from pathlib import Path

from .artifacts import new_archive
from .contract import resource_json, schema_check
from .core import BundleValidationError, ValidationReport, content_id, read_json, sha256_file, write_json
from .knowledge import load_snapshots


def screen_candidates(path, destination, snapshot_paths=()) -> Path:
    report = ValidationReport()
    name = Path(path).name
    try:
        document = read_json(Path(path))
    except (OSError, ValueError) as error:
        report.add("CANDIDATE_READ", "error", name, str(error))
        raise BundleValidationError(report) from error
    schema_check(document, resource_json("candidate_list.schema.json"), report, name)
    if not report.valid:
        raise BundleValidationError(report)
    seen = set()
    for candidate in document["candidates"]:
        key = (candidate["entity_id"], candidate["namespace"], candidate["taxon_id"])
        if key in seen:
            report.add("CANDIDATE_DUPLICATE", "error", name, "Repeated candidate entity.", row_or_record_id=candidate["entity_id"])
        seen.add(key)
        if candidate["taxon_id"] != document["source_taxon_id"]:
            report.add("CANDIDATE_TAXON", "error", name, "A candidate list cannot silently cross species.", row_or_record_id=candidate["entity_id"])
    if not report.valid:
        raise BundleValidationError(report)
    knowledge = load_snapshots(list(snapshot_paths))
    if any(source["synthetic"] for source in knowledge["sources"].values()) and not document["synthetic"]:
        raise ValueError("Synthetic knowledge is accepted only with an explicitly synthetic candidate list.")
    rows = [_row(candidate, document, knowledge["records"]) for candidate in document["candidates"]]
    identity = {"profile": "candidate_list", "statistical_inference": False, "background_enrichment": False,
                "complete_candidate_space": False, "input_sha256": sha256_file(Path(path)), "knowledge_hash": content_id(knowledge)}
    with new_archive(destination, format_name="theraweave.candidate-screen", identity=identity) as temp:
        write_json(temp / "context.json", {key: document[key] for key in
                   ("context_id", "source_taxon_id", "disease_or_phenotype", "research_goal", "screening_rule", "source_note", "synthetic")})
        write_json(temp / "candidates.json", rows)
        write_json(temp / "limits.json", {"statistical_inference": False, "background_enrichment": False,
                                          "complete_candidate_space": False, "local_effect_sizes": None, "accuracy": None})
    return Path(destination).resolve()


def _row(candidate: dict, document: dict, records: list[dict]) -> dict:
    matched = [row for row in records if (row["entity_id"], row["namespace"], row["taxon_id"]) ==
               (candidate["entity_id"], candidate["namespace"], candidate["taxon_id"])
               and row["reviewed"] and (row["context_id"] == document["context_id"] or
                                         (row["context_id"] is None and row["evidence_type"] in {"identity", "tool"}))]
    directions = {row["direction"] for row in matched if row["evidence_type"] in {"direction", "functional"}
                  and row["stance"] == "supports" and row["direction"] != "unknown" and row["context_id"] == document["context_id"]}
    contrary = any(row["evidence_type"] in {"direction", "functional"} and row["stance"] == "contradicts" and row["context_id"] == document["context_id"] for row in matched)
    direction = next(iter(directions)) if len(directions) == 1 and not contrary else "unknown"
    gaps = ["local_statistics_not_in_candidate_list", "background_enrichment_not_run", "complete_candidate_space_unknown"]
    if not any(row["evidence_type"] == "identity" and row["stance"] == "supports" for row in matched):
        gaps.append("identity_resolution")
    if not any(row["evidence_type"] == "tool" and row["stance"] == "supports" for row in matched):
        gaps.append("validated_perturbation_tool")
    if direction == "unknown":
        gaps.append("intervention_direction")
    return {**candidate, "context_id": document["context_id"], "bucket": "knowledge_gap_review",
            "intervention_direction": direction, "statistical_inference": False, "gaps": gaps,
            "local_padj": None, "local_effect": None}
