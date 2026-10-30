from __future__ import annotations

import json
import shutil
import socket
import subprocess
import sys
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from theraweave import DiscoveryProject
from theraweave.cli import main
from theraweave.contract import resource_json, snapshot, validate_bundle
from theraweave.core import BundleValidationError, read_json, sha256_file, write_json
from theraweave.demo import create_demo


@pytest.fixture
def demo(tmp_path):
    return create_demo(tmp_path / "demo")


def manifest(demo):
    return read_json(demo / "bundle" / "manifest.json")


def change_manifest(demo, change):
    value = manifest(demo)
    change(value)
    write_json(demo / "bundle" / "manifest.json", value)


def rewrite_table(demo, change):
    value = manifest(demo)
    path = demo / "bundle" / value["files"][0]["path"]
    table = change(pq.ParquetFile(path).read())
    pq.write_table(table, path)
    value["files"][0].update(size=path.stat().st_size, sha256=sha256_file(path))
    write_json(demo / "bundle" / "manifest.json", value)


def codes(result):
    return {d.rule_id for d in result.report.diagnostics}


def load(demo):
    return DiscoveryProject.from_bundle(demo / "bundle", context=demo / "context.json", allow_draft=True)


def test_requires_explicit_draft_opt_in(demo):
    result = validate_bundle(demo / "bundle")
    assert not result.report.valid
    assert "DRAFT_OPT_IN_REQUIRED" in codes(result)


@pytest.mark.parametrize("version", [None, "1.0.0", "0.2", 0.1])
def test_version_is_not_guessed(demo, version):
    change_manifest(demo, lambda v: v.update(bundle_schema_version=version))
    result = validate_bundle(demo / "bundle", allow_draft=True)
    assert "UNSUPPORTED_VERSION" in codes(result)


def test_complete_offline_archive_and_report(demo, tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("No network call is allowed during import.")
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    output = load(demo).write_evidence_report(tmp_path / "run")
    result = read_json(output / "manifest.json")
    assert result["status"] == "complete" and result["network_used"] is False
    assert result["counts"] == {"entities": 2, "evidence": 3, "duplicate_rows": 0}
    for item in result["files"]:
        assert sha256_file(output / item["path"]) == item["sha256"]
    rows = pq.read_table(output / "evidence_inventory.parquet").to_pylist()
    assert {r["intervention_direction"] for r in rows} == {"unknown"}
    assert {r["stance"] for r in rows} == {"unclear"}
    assert len({r["dependency_group_id"] for r in rows}) == 1
    assert any(r["padj"] is None for r in rows)
    html = (output / "import_report.html").read_text(encoding="utf-8")
    assert "0.04" in html and "DEMO_GENE_A" in html and "unknown" in html
    assert "未进行靶点排序" in html


def test_deterministic_inventory_and_non_overwrite(demo, tmp_path):
    project = load(demo)
    one = project.write_evidence_report(tmp_path / "one")
    two = project.write_evidence_report(tmp_path / "two")
    for name in ("evidence_inventory.parquet", "entity_inventory.parquet", "import_report.html"):
        assert (one / name).read_bytes() == (two / name).read_bytes()
    assert read_json(one / "manifest.json")["run_id"] == read_json(two / "manifest.json")["run_id"]
    with pytest.raises(FileExistsError):
        project.write_evidence_report(one)


def test_output_inside_input_is_rejected(demo):
    with pytest.raises(ValueError, match="inside"):
        load(demo).write_evidence_report(demo / "bundle" / "new-output")


def test_source_changes_abort_without_publishing_partial_output(demo, tmp_path):
    project = load(demo)
    source = next(iter(project.bundle.output_files.values()))
    source.write_bytes(source.read_bytes() + b"tampered")
    with pytest.raises(ValueError, match="changed"):
        project.write_evidence_report(tmp_path / "result")
    assert not (tmp_path / "result").exists()
    assert not list(tmp_path.glob(".result-*"))


@pytest.mark.parametrize("name", ["../outside.parquet", "C:/outside.parquet", "/tmp/outside.parquet", "a\\b.parquet", "a/../../outside.parquet"])
def test_output_path_escape_rejected(demo, name):
    change_manifest(demo, lambda v: v["files"][0].update(path=name))
    result = validate_bundle(demo / "bundle", allow_draft=True)
    assert "OUTPUT_PATH" in codes(result)


def test_input_provenance_paths_are_never_dereferenced(demo):
    change_manifest(demo, lambda v: v["files"].append({"path": "Z:/private/raw", "role": "input", "sha256": "0" * 64, "size": 20}))
    assert validate_bundle(demo / "bundle", allow_draft=True).report.valid


def test_checksum_failure_is_not_empty_success(demo):
    change_manifest(demo, lambda v: v["files"][0].update(sha256="0" * 64))
    with pytest.raises(BundleValidationError) as exc:
        load(demo)
    assert any(d.rule_id == "FILE_CHECKSUM" for d in exc.value.report.diagnostics)


def test_duplicate_evidence_does_not_inflate_support(demo, tmp_path):
    m = manifest(demo)
    old = demo / "bundle" / m["files"][0]["path"]
    new = old.parent / "copied.parquet"
    shutil.copyfile(old, new)
    m["files"].append({**m["files"][0], "path": new.relative_to(demo / "bundle").as_posix()})
    write_json(demo / "bundle" / "manifest.json", m)
    project = load(demo)
    assert len(project.bundle.rows) == 3
    assert project.bundle.report.duplicate_rows == 3
    assert len(project.bundle.rows[0]["source_rows"]) == 2
    result = project.write_evidence_report(tmp_path / "dedup")
    assert pq.read_table(result / "entity_inventory.parquet")["independent_replications"].null_count == 2


def test_conflicting_duplicate_is_not_overwritten(demo):
    m = manifest(demo)
    old = demo / "bundle" / m["files"][0]["path"]
    new = old.parent / "conflicting.parquet"
    table = pq.read_table(old)
    table = table.set_column(table.schema.get_field_index("log2fc"), "log2fc", pa.array([9.0, -0.8, None]))
    pq.write_table(table, new)
    m["files"].append({**m["files"][0], "path": new.relative_to(demo / "bundle").as_posix(), "sha256": sha256_file(new), "size": new.stat().st_size})
    write_json(demo / "bundle" / "manifest.json", m)
    assert "CONFLICTING_DUPLICATE" in codes(validate_bundle(demo / "bundle", allow_draft=True))


@pytest.mark.parametrize("field,values,expected", [
    ("padj", [1.2, 0.1, None], "P_VALUE_RANGE"),
    ("log2fc", [float("inf"), 1.0, None], "NONFINITE_VALUE"),
    ("n_numerator", [1.5, 4.0, 4.0], "COLUMN_TYPE"),
    ("n_numerator", [-1, 4, 4], "BIOLOGICAL_N"),
    ("contrast_role", ["invalid", "disease_effect", "other"], "CONTRAST_ROLE"),
    ("feature_id", [None, "A", "B"], "EMPTY_REQUIRED_VALUE"),
    ("omics", ["proteomics"] * 3, "OMICS_NOT_DECLARED"),
])
def test_invalid_rows_have_actionable_diagnostics(demo, field, values, expected):
    rewrite_table(demo, lambda t: t.set_column(t.schema.get_field_index(field), field, pa.array(values)))
    result = validate_bundle(demo / "bundle", allow_draft=True)
    assert not result.report.valid
    assert expected in codes(result)


def test_empty_table_is_valid_and_reportable(demo, tmp_path):
    rewrite_table(demo, lambda t: t.slice(0, 0))
    project = load(demo)
    assert "EMPTY_RESULTS" in codes(project.bundle)
    out = project.write_evidence_report(tmp_path / "empty")
    assert read_json(out / "manifest.json")["counts"]["evidence"] == 0


def test_namespace_is_explicit_and_html_is_escaped(demo, tmp_path):
    context = read_json(demo / "context.json")
    context["disease_or_phenotype"] = '<script>alert("x")</script>'
    write_json(demo / "context.json", context)
    out = load(demo).write_evidence_report(tmp_path / "escaped")
    assert "<script>" not in (out / "import_report.html").read_text(encoding="utf-8")
    context["feature_namespaces"] = {"proteomics": {"namespace": "UniProt", "entity_type": "protein"}}
    write_json(demo / "context.json", context)
    with pytest.raises(BundleValidationError):
        load(demo)


def test_cli_exit_codes_and_diagnostics(demo, capsys, tmp_path):
    assert main(["validate", str(demo / "bundle")]) == 2
    assert json.loads(capsys.readouterr().out)["valid"] is False
    assert main(["import", str(demo / "bundle"), "--context", str(demo / "context.json"), "--output", str(tmp_path / "cli"), "--allow-draft"]) == 0
    assert json.loads(capsys.readouterr().out)["validation"]["valid"] is True


def test_runtime_does_not_depend_on_upstream():
    completed = subprocess.run([sys.executable, "-I", "-c", "import importlib.util; assert importlib.util.find_spec('omicsweave') is None; import theraweave; print(theraweave.__version__)"], capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr


def test_snapshot_hashes_and_schema_integrity():
    from importlib.resources import files
    import hashlib
    for name, expected in snapshot()["artifact_hashes"].items():
        data = files("theraweave").joinpath("schemas", "omicsweave_0_1", name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == expected
    assert resource_json("omicsweave_0_1/manifest.schema.json")["title"] == "RunManifest"


def test_no_upstream_or_network_imports_in_production_source():
    import ast
    import theraweave
    root = Path(theraweave.__file__).parent
    prohibited = {"omicsweave", "requests", "httpx", "urllib", "socket"}
    for path in root.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""] if isinstance(node, ast.ImportFrom) else []
            assert not any(name.split(".")[0] in prohibited for name in names)


def test_duplicate_json_keys_are_rejected(demo):
    path = demo / "bundle" / "manifest.json"
    path.write_text('{"bundle_schema_version":"1.0","bundle_schema_version":"0.1"}', encoding="utf-8")
    assert "MANIFEST_READ" in codes(validate_bundle(demo / "bundle", allow_draft=True))


def test_unknown_manifest_capabilities_are_not_silently_ignored(demo):
    change_manifest(demo, lambda v: v.update(required_capabilities=["future-causal-model"]))
    assert "JSON_SCHEMA" in codes(validate_bundle(demo / "bundle", allow_draft=True))


def test_duplicate_key_within_table_is_rejected(demo):
    rewrite_table(demo, lambda t: pa.concat_tables([t, t.slice(0, 1)]))
    assert "DUPLICATE_TABLE_KEY" in codes(validate_bundle(demo / "bundle", allow_draft=True))


@pytest.mark.parametrize("meta,expected", [
    ({"value_type": "concentration", "scale": "linear"}, "DATASET_UNITS"),
    ({"value_type": "counts", "scale": "log2"}, "COUNTS_SCALE"),
])
def test_upstream_dataset_semantics_not_captured_by_json_schema(demo, meta, expected):
    value = {"schema_version": 1, "omics": "transcriptomics", "tissue": "liver", "feature_id_type": "demo", **meta}
    path = demo / "bundle" / "dataset.json"
    write_json(path, value)
    change_manifest(demo, lambda v: v["files"].append({"path": "dataset.json", "role": "output", "size": path.stat().st_size, "sha256": sha256_file(path)}))
    assert expected in codes(validate_bundle(demo / "bundle", allow_draft=True))


def test_extension_values_are_preserved_with_original_table(demo, tmp_path):
    rewrite_table(demo, lambda t: t.append_column("custom_annotation", pa.array(["source_A", "source_B", "source_C"])))
    out = load(demo).write_evidence_report(tmp_path / "extended")
    rows = pq.read_table(out / "evidence_inventory.parquet").to_pylist()
    assert {json.loads(r["source_values_json"])["custom_annotation"] for r in rows} == {"source_A", "source_B", "source_C"}
    assert (out / "source_bundle" / manifest(demo)["files"][0]["path"]).is_file()


def test_mfa_requires_effect_type_and_remains_a_reaction(demo):
    rewrite_table(demo, lambda t: t.set_column(t.schema.get_field_index("omics"), "omics", pa.array(["mfa"] * 3)))
    change_manifest(demo, lambda v: v.update(omics=["mfa"]))
    assert "MFA_EFFECT" in codes(validate_bundle(demo / "bundle", allow_draft=True))
    rewrite_table(demo, lambda t: t.append_column("effect_size", pa.array([0.1, 0.2, 0.3])).append_column("effect_size_type", pa.array(["hedges_g"] * 3)))
    for name, values in {"mean_numerator": [1.0] * 3, "mean_denominator": [2.0] * 3,
                         "units": ["nmol/min/g"] * 3, "inference_unit": ["biological_replicate"] * 3,
                         "evidence_level": ["effect_size_only"] * 3}.items():
        rewrite_table(demo, lambda t, name=name, values=values: t.append_column(name, pa.array(values)))
    context = read_json(demo / "context.json")
    context["feature_namespaces"] = {"mfa": {"namespace": "demo_network", "entity_type": "gene"}}
    write_json(demo / "context.json", context)
    with pytest.raises(BundleValidationError) as exc:
        load(demo)
    assert any(d.rule_id == "MFA_ENTITY_TYPE" for d in exc.value.report.diagnostics)


def test_corrupt_parquet_is_a_structured_failure(demo):
    path = demo / "bundle" / manifest(demo)["files"][0]["path"]
    path.write_bytes(b"not parquet")
    change_manifest(demo, lambda v: v["files"][0].update(size=path.stat().st_size, sha256=sha256_file(path)))
    assert "PARQUET_READ" in codes(validate_bundle(demo / "bundle", allow_draft=True))


def test_upstream_optional_bool_and_mfa_insufficient_effect_are_preserved(demo, tmp_path):
    def mfa(t):
        t = t.set_column(t.schema.get_field_index("omics"), "omics", pa.array(["mfa"] * 3))
        for name, values in {"effect_size": pa.array([None, 0.2, 0.3], type=pa.float64()),
                             "effect_size_type": ["hedges_g"] * 3, "mean_numerator": [1.0] * 3,
                             "mean_denominator": [2.0] * 3, "units": ["nmol/min/g"] * 3,
                             "inference_unit": ["biological_replicate"] * 3,
                             "evidence_level": ["insufficient", "effect_size_only", "statistical_test"],
                             "selected": [False, True, False]}.items():
            t = t.append_column(name, values if isinstance(values, pa.Array) else pa.array(values))
        return t
    rewrite_table(demo, mfa)
    change_manifest(demo, lambda v: v.update(omics=["mfa"]))
    context = read_json(demo / "context.json")
    context["feature_namespaces"] = {"mfa": {"namespace": "demo_model", "entity_type": "reaction"}}
    write_json(demo / "context.json", context)
    project = load(demo)
    out = project.write_evidence_report(tmp_path / "mfa")
    evidence = pq.read_table(out / "evidence_inventory.parquet").to_pylist()
    assert {r["source_statistical_level"] for r in evidence} == {"insufficient", "effect_size_only", "statistical_test"}
    assert any(r["effect_size"] is None for r in evidence)
