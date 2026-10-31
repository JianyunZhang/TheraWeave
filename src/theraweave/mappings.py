"""Reviewed ortholog and reaction maps.

A map records identity relationships supplied by the user. It does not copy
disease, direction, safety, or flux-control claims across the relationship.
"""
from __future__ import annotations

from pathlib import Path

from .contract import resource_json, schema_check
from .core import BundleValidationError, ValidationReport, read_json, sha256_file


def _load(path, schema_name: str) -> tuple[dict, ValidationReport, str]:
    report = ValidationReport()
    name = Path(path).name
    try:
        document = read_json(Path(path))
    except (OSError, ValueError) as error:
        report.add("MAP_READ", "error", name, str(error))
        raise BundleValidationError(report) from error
    schema_check(document, resource_json(schema_name), report, name)
    return document, report, sha256_file(Path(path))


def _counts(orthology_type: str, orthologs: list) -> bool:
    count = len(orthologs)
    if orthology_type == "none":
        return count == 0
    if orthology_type == "one2one":
        return count == 1
    return count >= 2


def load_ortholog_map(path, entities: list[dict]) -> dict:
    """Load a reviewed mouse-to-human map and require every link to match an entity."""
    document, report, digest = _load(path, "ortholog_map.schema.json")
    if not report.valid:
        raise BundleValidationError(report)
    known = {(row["entity_id"], row["namespace"], row["taxon_id"]) for row in entities}
    index = {}
    name = Path(path).name
    for link in document["links"]:
        key = (link["source_entity_id"], link["source_namespace"], link["source_taxon_id"])
        if key in index:
            report.add("ORTHOLOG_DUPLICATE", "error", name, "The same source entity has more than one ortholog link.", row_or_record_id=key[0])
        if not _counts(link["orthology_type"], link["orthologs"]):
            report.add("ORTHOLOGY_COUNT", "error", name, "Ortholog count does not match one2one, one2many/many2many, or none.", row_or_record_id=key[0])
        pairs = [(item["entity_id"], item["namespace"]) for item in link["orthologs"]]
        if len(pairs) != len(set(pairs)):
            report.add("ORTHOLOG_REPEAT", "error", name, "Repeated human orthologs must stay distinct rather than be collapsed.", row_or_record_id=key[0])
        if key not in known:
            report.add("ORTHOLOG_ENTITY", "error", name, "Ortholog link does not match an imported entity.", row_or_record_id=key[0])
        index[key] = link
    if not report.valid:
        raise BundleValidationError(report)
    return {**{k: document[k] for k in ("reviewer", "source_name", "source_release", "retrieved_at", "method", "synthetic")},
            "sha256": digest, "index": index}


def ortholog_view(entity: dict, document: dict | None) -> dict:
    if entity["taxon_id"] == 9606:
        return {"status": "source_taxon_is_human", "orthology_type": None, "orthologs": [], "dimension": "limited"}
    if document is None:
        return {"status": "not_provided", "orthology_type": None, "orthologs": [], "dimension": "unknown"}
    link = document["index"].get((entity["entity_id"], entity["namespace"], entity["taxon_id"]))
    if link is None:
        return {"status": "not_provided", "orthology_type": None, "orthologs": [], "dimension": "unknown"}
    if link["orthology_type"] == "none":
        return {"status": "no_human_ortholog", "orthology_type": "none", "orthologs": [], "dimension": "limited"}
    return {"status": "reviewed_map", "orthology_type": link["orthology_type"],
            "orthologs": [dict(item) for item in link["orthologs"]], "dimension": "limited"}


def load_reaction_map(path, entities: list[dict]) -> dict:
    """Load a GPR-style map. flux_control_supported is intentionally not accepted."""
    document, report, digest = _load(path, "reaction_map.schema.json")
    if not report.valid:
        raise BundleValidationError(report)
    known = {(row["entity_id"], row["namespace"], row["taxon_id"]): row for row in entities}
    links = []
    name = Path(path).name
    seen = set()
    for link in document["links"]:
        key = (link["reaction_id"], link["namespace"], link["taxon_id"])
        entity = known.get(key)
        if key in seen:
            report.add("REACTION_DUPLICATE", "error", name, "The same reaction is mapped more than once.", row_or_record_id=key[0])
        seen.add(key)
        if entity is None or entity["entity_type"] != "reaction":
            report.add("REACTION_ENTITY", "error", name, "Reaction link must match an imported reaction, not a gene or an unknown identifier.", row_or_record_id=key[0])
        if link["relation"] == "OR" and len(link["components"]) < 2:
            report.add("GPR_OR", "error", name, "An OR relation needs at least two components; it does not choose one isozyme.", row_or_record_id=key[0])
        component_keys = [(item["entity_id"], item["namespace"], item["entity_type"]) for item in link["components"]]
        if len(component_keys) != len(set(component_keys)):
            report.add("GPR_COMPONENT", "error", name, "Repeated GPR components are not additional flux observations.", row_or_record_id=key[0])
        links.append(link)
    if not report.valid:
        raise BundleValidationError(report)
    return {**{k: document[k] for k in ("reviewer", "model_id", "model_version", "synthetic")},
            "sha256": digest, "links": links}


def reaction_links(document: dict | None, entities: list[dict], evidence: list[dict]) -> dict:
    reactions = [row for row in entities if row["entity_type"] == "reaction"]
    if document is None:
        return {"links": [], "reactions_without_map": [row["entity_id"] for row in reactions],
                "flux_control_supported": False, "rule": "mapping_only"}
    by_reaction = {(link["reaction_id"], link["namespace"], link["taxon_id"]): link for link in document["links"]}
    rendered = []
    missing = []
    entities_by_id = {(row["entity_id"], row["namespace"], row["taxon_id"]): row for row in entities}
    for entity in reactions:
        link = by_reaction.get((entity["entity_id"], entity["namespace"], entity["taxon_id"]))
        if link is None:
            missing.append(entity["entity_id"])
            continue
        observations = [row["evidence_id"] for row in evidence if row["entity_key"] == entity["entity_key"]]
        limitations = ["mapping_only", "flux_sign_does_not_set_direction", "one_flux_source_for_all_components",
                       "not_independent_replication"]
        if link["relation"] == "OR":
            limitations.append("or_relation_does_not_make_each_isozyme_the_inhibition_target")
        else:
            limitations.append("and_relation_requires_the_recorded_components_together")
        if link["cross_organ"]:
            limitations.append("cross_organ_not_assigned_to_one_tissue_enzyme")
        rendered.append({
            "reaction_entity_key": entity["entity_key"], "reaction_id": entity["entity_id"],
            "namespace": entity["namespace"], "taxon_id": entity["taxon_id"],
            "relation": link["relation"], "compartment": link["compartment"],
            "directionality": link["directionality"], "cross_organ": link["cross_organ"],
            "flux_control": "mapping_only", "model_id": document["model_id"], "model_version": document["model_version"],
            "evidence_ids": observations, "independent_flux_sources": len(observations),
            "components": [{
                "entity_id": item["entity_id"], "namespace": item["namespace"], "entity_type": item["entity_type"],
                "present_in_inventory": (item["entity_id"], item["namespace"], entity["taxon_id"]) in entities_by_id
                and entities_by_id[(item["entity_id"], item["namespace"], entity["taxon_id"])]["entity_type"] == item["entity_type"],
                "intervention_direction": "unknown", "claim": "candidate_enzyme_requires_validation",
                "not_an_independent_flux_observation": True, "not_a_control_or_inhibition_target": True,
            } for item in link["components"]],
            "limitations": limitations,
        })
    return {"links": rendered, "reactions_without_map": missing, "flux_control_supported": False,
            "rule": "mapping_only", "reviewer": document["reviewer"]}
