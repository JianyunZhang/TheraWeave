"""Independent reader for a pinned OmicsWeave draft, with explicit opt-in.

Only manifest-listed output files are read. Input provenance paths are retained
but never dereferenced. No upstream modules or network clients are imported.
"""
from __future__ import annotations

import base64
import math
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from importlib.resources import files
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
from jsonschema import Draft202012Validator, FormatChecker

from .core import ValidationReport, content_id, read_json, sha256_file

OMICS = {"transcriptomics", "proteomics", "metabolomics", "mfa"}
ROLES = {"disease_effect", "treatment_effect", "time_effect", "other"}
KEY = ("contrast_id", "tissue", "omics", "feature_id")
MAX_PREVIEW_ROWS = 1_000_000


def resource_json(name: str) -> dict | list:
    import json
    return json.loads(files("theraweave").joinpath("schemas", name).read_text(encoding="utf-8"))


def snapshot() -> dict:
    return resource_json("omicsweave_0_1/snapshot.json")


def json_safe(value: Any) -> Any:
    """Typed encodings for extension columns; original Parquet is also archived."""
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, (datetime, date, Decimal)):
        return {"__type__": type(value).__name__, "value": str(value)}
    if isinstance(value, bytes):
        return {"__type__": "bytes", "base64": base64.b64encode(value).decode("ascii")}
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    return value


def schema_check(instance: Any, schema: dict, report: ValidationReport, name: str) -> None:
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for error in sorted(validator.iter_errors(instance), key=lambda e: str(list(e.absolute_path))):
        report.add("JSON_SCHEMA", "error", name, error.message,
                   field="/" + "/".join(map(str, error.absolute_path)))


def safe_output_path(root: Path, relative: str) -> Path:
    posix, windows = PurePosixPath(relative), PureWindowsPath(relative)
    if (not relative or "\\" in relative or ":" in relative or posix.is_absolute()
            or windows.drive or ".." in posix.parts or relative != posix.as_posix()):
        raise ValueError("Expected a canonical relative path inside the bundle.")
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or path == root.resolve():
        raise ValueError("The resolved output path escapes the bundle.")
    return path


@dataclass
class ValidatedBundle:
    root: Path
    manifest: dict
    report: ValidationReport
    rows: list[dict] = field(default_factory=list)
    output_files: dict[str, Path] = field(default_factory=dict)
    manifest_sha256: str = ""


def _check_table(table: pa.Table, name: str, report: ValidationReport) -> list[dict]:
    columns = resource_json("omicsweave_0_1/differential.columns.json")
    rules = resource_json("omicsweave_0_1/differential.rules.json")
    start_errors = sum(d.severity == "error" for d in report.diagnostics)
    if len(table.column_names) != len(set(table.column_names)):
        report.add("DUPLICATE_COLUMN", "error", name, "Parquet column names must be unique.")
        return []
    for column in columns:
        column_name = column["name"]
        if column_name not in table.column_names:
            if column["required"]:
                report.add("REQUIRED_COLUMN", "error", name, "Missing required differential column.", field=column_name)
            continue
        dtype = table.schema.field(column_name).type
        if pa.types.is_dictionary(dtype):
            dtype = dtype.value_type
        valid_type = (
            (column["kind"] == "str" and (pa.types.is_string(dtype) or pa.types.is_large_string(dtype)))
            or (column["kind"] == "int" and pa.types.is_integer(dtype))
            or (column["kind"] == "bool" and pa.types.is_boolean(dtype))
            or (column["kind"] == "float" and (pa.types.is_floating(dtype) or pa.types.is_integer(dtype)))
            or (pa.types.is_null(dtype) and not column["required"])
        )
        if not valid_type:
            report.add("COLUMN_TYPE", "error", name, f"Expected {column['kind']}; found {dtype}.", field=column_name)
    if sum(d.severity == "error" for d in report.diagnostics) > start_errors:
        return []
    result = []
    local_keys = set()
    missing_statistics = 0
    low_counts = 0
    for number, original in enumerate(table.to_pylist(), start=1):
        row = json_safe(original)
        report.rows_checked += 1
        for column in columns:
            value = row.get(column["name"])
            if column["required"] and column["kind"] == "str" and (not isinstance(value, str) or not value.strip()):
                report.add("EMPTY_REQUIRED_VALUE", "error", name, "Required string is empty.", field=column["name"], row_or_record_id=number)
            if isinstance(value, (int, float)) and not math.isfinite(value):
                report.add("NONFINITE_VALUE", "error", name, "Infinite numeric values are not supported.", field=column["name"], row_or_record_id=number)
        for column_name in ("pvalue", "padj", "min_achievable_p", "frac_at_bound", "selection_probability", "direction_stability", "permutation_pvalue"):
            value = row.get(column_name)
            if value is not None and not 0 <= value <= 1:
                report.add("P_VALUE_RANGE", "error", name, "Probability must lie in [0, 1].", field=column_name, row_or_record_id=number)
        for column_name in ("n_numerator", "n_denominator"):
            value = row.get(column_name)
            if value is None or value < 0:
                report.add("BIOLOGICAL_N", "error", name, "Biological replicate count must be a nonnegative integer.", field=column_name, row_or_record_id=number)
            elif value < 3:
                low_counts += 1
        if row["contrast_role"] not in ROLES:
            report.add("CONTRAST_ROLE", "error", name, "Unrecognized contrast role.", row_or_record_id=number)
        if row["omics"] not in OMICS:
            report.add("OMICS_VALUE", "error", name, "Unrecognized omics type.", row_or_record_id=number)
        if row.get("evidence_level") is not None and row["evidence_level"] not in rules["evidence_levels"]:
            report.add("SOURCE_STATISTICAL_LEVEL", "error", name, "Unrecognized source differential evidence_level (statistical strength, not Evidence Graph layer).", row_or_record_id=number)
        for required in rules["required_by_omics"].get(row["omics"], []):
            value = row.get(required)
            undefined_effect = required == "effect_size" and (row.get("evidence_level") == "insufficient" or "effect_size_undefined" in (row.get("flags") or ""))
            if (value is None or (isinstance(value, str) and not value.strip())) and not undefined_effect:
                report.add("MFA_EFFECT" if required in {"effect_size", "effect_size_type"} else "MFA_REQUIRED_CONTEXT",
                           "error", name, f"MFA differential result requires {required}; fits are not biological replicates.", field=required, row_or_record_id=number)
        if row["omics"] == "mfa" and row.get("inference_unit") not in {"biological_replicate", "animal", "subject", "donor"}:
            report.add("MFA_INFERENCE_UNIT_REVIEW", "warning", name, "Review MFA inference_unit; fitted iterations cannot be independent biological replicates.", row_or_record_id=number)
        key = tuple(row.get(k) for k in KEY)
        if key in local_keys:
            report.add("DUPLICATE_TABLE_KEY", "error", name, "Duplicate differential key within one table.", row_or_record_id=number)
        local_keys.add(key)
        if any(row.get(k) is None for k in ("log2fc", "pvalue", "padj")):
            missing_statistics += 1
        result.append({"values": row, "source_rows": [{"file": name, "row": number}]})
        if len(report.diagnostics) >= 100:
            report.add("DIAGNOSTIC_LIMIT", "error", name, "Stopped after 100 diagnostics; fix this batch before continuing.")
            break
    if missing_statistics:
        report.add("MISSING_STATISTICS", "warning", name, f"{missing_statistics} rows have missing statistics; they remain unknown, not negative.")
    if low_counts:
        report.add("LOW_BIOLOGICAL_N", "warning", name, "Some groups contain fewer than 3 biological units; inspect precision and design.")
    return result


def validate_bundle(directory: str | Path, *, allow_draft: bool = False) -> ValidatedBundle:
    root = Path(directory).resolve()
    report = ValidationReport()
    result = ValidatedBundle(root, {}, report)
    manifest_path = root / "manifest.json"
    try:
        if not manifest_path.resolve().is_relative_to(root):
            raise ValueError("Manifest resolves outside the bundle.")
        manifest = read_json(manifest_path)
        result.manifest_sha256 = sha256_file(manifest_path)
    except (OSError, ValueError) as exc:
        report.add("MANIFEST_READ", "error", "manifest.json", str(exc))
        return result
    if not isinstance(manifest, dict):
        report.add("MANIFEST_TYPE", "error", "manifest.json", "Manifest must be a JSON object.")
        return result
    result.manifest = manifest
    if manifest.get("bundle_schema_version") != "0.1":
        report.add("UNSUPPORTED_VERSION", "error", "manifest.json", "Only the pinned explicit 0.1 draft is supported; missing versions and v1 are not inferred.")
        return result
    if not allow_draft:
        report.add("DRAFT_OPT_IN_REQUIRED", "error", "manifest.json", "Draft import requires allow_draft=True or --allow-draft.", suggested_action="Review the draft limitations before explicitly enabling draft import.")
        return result
    schema_check(manifest, resource_json("omicsweave_0_1/manifest.schema.json"), report, "manifest.json")
    if not report.valid:
        return result
    report.add("DRAFT_PROVENANCE_GAPS", "warning", "manifest.json", "Draft 0.1 does not encode completion state, sample overlap, full contrast design, or evidence graph. This reader cannot certify a stable evidence bundle.")
    listed_paths = set()
    seen: dict[tuple, dict] = {}
    differential_count = 0
    for record in manifest.get("files", []):
        if record["role"] != "output":
            continue
        name = record["path"]
        try:
            path = safe_output_path(root, name)
            folded = name.casefold()
            if folded in listed_paths:
                raise ValueError("Duplicate output paths, including case-only variants, are not portable.")
            listed_paths.add(folded)
            if path == manifest_path.resolve():
                raise ValueError("Manifest may not list itself as a checksummed output.")
            if record["size"] < 0 or path.stat().st_size != record["size"]:
                report.add("FILE_SIZE", "error", name, "Output size does not match the manifest.")
                continue
            if sha256_file(path) != record["sha256"]:
                report.add("FILE_CHECKSUM", "error", name, "Output SHA-256 does not match the manifest.")
                continue
        except (OSError, ValueError) as exc:
            report.add("OUTPUT_PATH", "error", name, str(exc))
            continue
        report.files_checked += 1
        result.output_files[name] = path
        if path.name == "dataset.json":
            try:
                meta = read_json(path)
                schema_check(meta, resource_json("omicsweave_0_1/dataset.schema.json"), report, name)
                if isinstance(meta, dict):
                    if meta.get("value_type") in ("flux", "concentration") and not meta.get("units"):
                        report.add("DATASET_UNITS", "error", name, "Flux/concentration requires units (upstream semantic rule).")
                    if meta.get("value_type") == "counts" and meta.get("scale") != "linear":
                        report.add("COUNTS_SCALE", "error", name, "Counts must use a linear scale.")
            except (OSError, ValueError) as exc:
                report.add("DATASET_READ", "error", name, str(exc))
        elif path.name == "differential.parquet" or record.get("kind") == "differential":
            differential_count += 1
            try:
                parquet = pq.ParquetFile(path)
                if parquet.metadata.num_rows > MAX_PREVIEW_ROWS:
                    report.add("PREVIEW_ROW_LIMIT", "error", name, f"Preview supports at most {MAX_PREVIEW_ROWS} rows per table.")
                    continue
                entries = _check_table(parquet.read(), name, report)
                for entry in entries:
                    row = entry["values"]
                    if row["omics"] not in manifest.get("omics", []):
                        report.add("OMICS_NOT_DECLARED", "error", name, "Row omics is absent from manifest.omics.", row_or_record_id=entry["source_rows"][0]["row"])
                    key = tuple(row[k] for k in KEY)
                    if key in seen:
                        if content_id(row) != content_id(seen[key]["values"]):
                            report.add("CONFLICTING_DUPLICATE", "error", name, "The same differential key has conflicting values; no overwrite or averaging is allowed.")
                        else:
                            seen[key]["source_rows"].extend(entry["source_rows"])
                            report.duplicate_rows += 1
                    else:
                        seen[key] = entry
            except (OSError, ValueError, pa.ArrowException) as exc:
                report.add("PARQUET_READ", "error", name, str(exc))
        else:
            report.add("OUTPUT_NOT_INTERPRETED", "warning", name, "File checksum checked; this preview does not interpret this output type.")
    if not differential_count:
        report.add("NO_DIFFERENTIAL_TABLE", "error", "manifest.json", "No listed differential table; use basename differential.parquet or kind=differential.")
    elif not seen and report.valid:
        report.add("EMPTY_RESULTS", "warning", "manifest.json", "Valid empty differential results; no candidates are fabricated.")
    result.rows = sorted(seen.values(), key=lambda entry: tuple(str(entry["values"][key]) for key in KEY))
    if report.duplicate_rows:
        report.add("DUPLICATE_EVIDENCE_COLLAPSED", "warning", "manifest.json", f"Collapsed {report.duplicate_rows} repeated rows across files; all source references retained.")
    return result


def validate_context(path: str | Path, bundle: ValidatedBundle) -> dict:
    try:
        context = read_json(Path(path))
        schema_check(context, resource_json("context.schema.json"), bundle.report, "context.json")
    except (OSError, ValueError) as exc:
        bundle.report.add("CONTEXT_READ", "error", "context.json", str(exc))
        return {}
    if not bundle.report.valid:
        return {}
    for omics in {entry["values"]["omics"] for entry in bundle.rows}:
        if omics not in context["feature_namespaces"]:
            bundle.report.add("MISSING_NAMESPACE", "error", "context.json", f"Explicit entity type and namespace required for {omics}; gene symbols are not assumed.")
        elif omics == "mfa" and context["feature_namespaces"][omics]["entity_type"] != "reaction":
            bundle.report.add("MFA_ENTITY_TYPE", "error", "context.json", "MFA observations describe reactions, not a directly measured gene target.")
    bundle.report.add("CONTEXT_USER_ASSERTED", "warning", "context.json", "Species, identity namespace, phenotype and endpoint are user-supplied context, not established by the draft manifest.")
    return context
