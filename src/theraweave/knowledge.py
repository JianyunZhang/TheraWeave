"""Offline normalized snapshot intake with study-level de-duplication.

These are curated source-independent records, not raw Open Targets, ChEMBL or
UniProt API response adapters. Source scores alone cannot grant causal support.
"""
from __future__ import annotations

from pathlib import Path

from .contract import resource_json, schema_check
from .core import BundleValidationError, ValidationReport, content_id, read_json, sha256_file


def load_snapshots(paths: list[str | Path]) -> dict:
    report, sources, records = ValidationReport(), {}, {}
    for filename in paths:
        path = Path(filename)
        try:
            value = read_json(path)
        except (OSError, ValueError) as error:
            report.add("SNAPSHOT_READ", "error", path.name, str(error))
            continue
        schema_check(value, resource_json("knowledge.schema.json"), report, path.name)
        if not report.valid:
            continue
        source = value["source"]
        source_key = f"{source['name']}:{source['release']}"
        source_hash = sha256_file(path)
        if source_key in sources and sources[source_key]["sha256"] != source_hash:
            report.add("SNAPSHOT_RELEASE_CONFLICT", "error", path.name, "The same source release has different content.")
        sources[source_key] = {**source, "sha256": source_hash}
        local_ids = set()
        for record in value["records"]:
            if record["record_id"] in local_ids:
                report.add("SNAPSHOT_RECORD_ID", "error", path.name, "Repeated record_id within a source.")
            local_ids.add(record["record_id"])
            if record["reviewed"] and not record.get("reviewer"):
                report.add("REVIEWER_REQUIRED", "error", path.name, "Reviewed knowledge requires a named reviewer.", row_or_record_id=record["record_id"])
            if record.get("blocking") and (record["evidence_type"] != "risk" or not record["reviewed"] or not record["context_id"]):
                report.add("RISK_SCOPE", "error", path.name, "Blocking risk requires reviewed, context-specific risk evidence.", row_or_record_id=record["record_id"])
            if record["evidence_type"] in {"functional", "direction", "risk"} and record["reviewed"] and not record["context_id"]:
                report.add("CLAIM_CONTEXT", "error", path.name, "Mechanistic, directional and risk claims require an explicit context.", row_or_record_id=record["record_id"])
            if record["evidence_type"] == "tool" and record["reviewed"] and not record.get("tool_id"):
                report.add("TOOL_ID", "error", path.name, "Reviewed tool evidence requires a tool_id.", row_or_record_id=record["record_id"])
            # The same primary record/assertion carried by multiple databases
            # is one assertion. Conflicting interpretations remain separate.
            assertion = {k: v for k, v in record.items() if k not in {"record_id", "reviewer", "citations", "statement", "source_payload"}}
            evidence_id = "knowledge-" + content_id(assertion)[:24]
            if evidence_id not in records:
                records[evidence_id] = {"evidence_id": evidence_id, **record, "source_refs": [], "all_citations": []}
            normalized = records[evidence_id]
            ref = {"source": source_key, "record_id": record["record_id"]}
            if ref not in normalized["source_refs"]:
                normalized["source_refs"].append(ref)
            normalized["all_citations"] = sorted(set(normalized["all_citations"]) | set(record["citations"]))
    if not report.valid:
        raise BundleValidationError(report)
    return {"sources": sources, "records": sorted(records.values(), key=lambda v: v["evidence_id"]), "validation": report.to_dict()}
