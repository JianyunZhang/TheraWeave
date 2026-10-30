"""Narrow local-file adapters. Imported assertions always start unreviewed."""
from __future__ import annotations

from pathlib import Path

import pyarrow.parquet as pq

from .contract import json_safe
from .core import canonical_json, content_id, parse_json, read_json, sha256_file
from .knowledge import load_snapshots


def _rows(path: Path, container: str) -> list[dict]:
    if path.suffix.lower() == ".parquet":
        parquet = pq.ParquetFile(path)
        if parquet.metadata.num_rows > 1_000_000:
            raise ValueError("Import a local subset of at most 1,000,000 records.")
        values = parquet.read().to_pylist()
    elif path.suffix.lower() in {".jsonl", ".ndjson"}:
        values = [parse_json(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    else:
        value = read_json(path)
        values = value if isinstance(value, list) else value.get(container, [value]) if isinstance(value, dict) else None
    if not isinstance(values, list) or not all(isinstance(row, dict) for row in values):
        raise ValueError("Expected a record list or the documented source response container.")
    if len(values) > 1_000_000:
        raise ValueError("Import a subset of at most 1,000,000 records.")
    return json_safe(values)


def _required(row: dict, name: str) -> str:
    value = row.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Source record requires {name}.")
    return value


def convert_source(source: str, input_path, output_path, *, metadata: dict, taxon_id=None, target_map=None) -> Path:
    if source not in {"OpenTargets", "UniProt", "ChEMBL"}:
        raise ValueError("Unsupported source adapter.")
    required_metadata = {"release", "retrieved_at", "origin_url", "license", "synthetic"}
    if (not isinstance(metadata, dict) or not required_metadata.issubset(metadata)
            or set(metadata) - required_metadata - {"coverage_notes"}):
        raise ValueError("Metadata must specify release, retrieved_at, origin_url, license and synthetic; coverage_notes is optional.")
    path, output = Path(input_path).resolve(), Path(output_path).absolute()
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"Output already exists: {output}")
    containers = {"OpenTargets": "evidence", "UniProt": "results", "ChEMBL": "mechanisms"}
    raw_rows = _rows(path, containers[source])
    target_by_id = {}
    if source == "ChEMBL":
        if target_map is None:
            raise ValueError("ChEMBL mechanism import requires a local target response map.")
        for record in _rows(Path(target_map), "targets"):
            key = _required(record, "target_chembl_id")
            if key in target_by_id:
                raise ValueError("Duplicate ChEMBL target map entry.")
            target_by_id[key] = record
    records = []
    for raw in raw_rows:
        native_id = str(raw.get("id") or content_id(raw))
        record = {
            "record_id": native_id, "primary_record_id": f"{source}:{native_id}", "primary_study_id": None,
            "entity_id": "", "namespace": "", "taxon_id": 0, "context_id": None,
            "evidence_type": "association", "stance": "unclear", "direction": "unknown", "reviewed": False,
            "reviewer": None, "citations": [metadata["origin_url"]],
            "statement": "Automatically normalized source record; context, mapping and scientific interpretation require review.",
            "source_payload": raw,
        }
        if source == "OpenTargets":
            if type(taxon_id) is not int or taxon_id < 1:
                raise ValueError("Explicit taxon_id required; Open Targets target identifiers do not encode source experimental species.")
            record.update(entity_id=_required(raw, "targetId"), namespace="Ensembl", taxon_id=taxon_id)
            _required(raw, "diseaseId")
            record["primary_study_id"] = raw.get("studyId") or None
            record["citations"] = [str(x) for x in raw.get("literature", [])] or record["citations"]
        elif source == "UniProt":
            organism = raw.get("organism", {})
            taxon = organism.get("taxonId") if isinstance(organism, dict) else None
            if type(taxon) is not int or taxon < 1:
                raise ValueError("UniProt organism.taxonId is required.")
            record.update(entity_id=_required(raw, "primaryAccession"), namespace="UniProt", taxon_id=taxon, evidence_type="identity")
        else:
            target_id = _required(raw, "target_chembl_id")
            target = target_by_id.get(target_id)
            if target is None:
                raise ValueError(f"No local ChEMBL target map for {target_id}.")
            components = target.get("target_components", [])
            if (target.get("target_type") != "SINGLE PROTEIN" or not isinstance(components, list)
                    or len(components) != 1 or not isinstance(components[0], dict)):
                raise ValueError(f"Ambiguous/non-single-protein ChEMBL target {target_id}; curate separately, no silent flattening.")
            accession = _required(components[0], "accession")
            taxon = target.get("tax_id")
            if type(taxon) is not int or taxon < 1:
                raise ValueError("ChEMBL target tax_id is required.")
            record.update(entity_id=accession, namespace="UniProt", taxon_id=taxon, evidence_type="tool", tool_id=_required(raw, "molecule_chembl_id"))
            record["source_payload"] = {"mechanism": raw, "target": target}
        records.append(record)
    value = {"format": "theraweave.knowledge-snapshot", "version": "0.1", "records": records,
             "source": {"name": source, **metadata, "input_sha256": sha256_file(path), "adapter": f"{source}-local-subset-1"}}
    if target_map is not None:
        value["source"]["auxiliary_input_hashes"] = {"target_map": sha256_file(Path(target_map))}
    # Validate via the same consumer before atomically publishing a single file.
    output.parent.mkdir(parents=True, exist_ok=True)
    import tempfile
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", encoding="utf-8", dir=output.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(canonical_json(value) + "\n")
        load_snapshots([temporary])
        if output.exists():
            raise FileExistsError(f"Output appeared during conversion: {output}")
        temporary.rename(output)
        return output.resolve()
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
