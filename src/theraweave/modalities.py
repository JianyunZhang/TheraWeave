"""Condition-level modality screen.

Each modality keeps its own conditions. A recorded tool can leave a research
probe open while selectivity, exposure, delivery, or persistence stay unknown.
Nothing here is a rank, a therapeutic recommendation, or a design.
"""
from __future__ import annotations

MODALITIES = ("small_molecule", "antibody", "peptide", "siRNA", "ASO", "mRNA", "gene_delivery", "DNA_editing")
RULE_VERSION = "modality-rules-1"
_DIRECT = {"gene", "transcript", "protein"}
_ALIGNED = {
    "inhibit": {"inhibition", "receptor_antagonism"},
    "activate": {"activation", "receptor_agonism"},
}


def _condition(name: str, status: str, detail: str) -> dict:
    return {"id": name, "status": status, "detail": detail}


def _option(modality: str, disposition: str, conditions: list[dict], basis: list[str]) -> dict:
    return {
        "modality": modality, "disposition": disposition, "use": "research_probe", "therapeutic_concept": False,
        "rank": None, "not_a_recommendation": True, "conditions": conditions,
        "open_questions": [item["id"] for item in conditions if item["status"] == "unknown"],
        "basis": basis, "rule_version": RULE_VERSION,
    }


def _finish(conditions: list[dict], *, opened: bool) -> str:
    if any(item["status"] == "unmet" for item in conditions):
        return "attribute_mismatch"
    if opened:
        return "open_research_probe"
    if all(item["status"] == "unknown" for item in conditions):
        return "insufficient_records"
    return "pending_conditions" if any(item["status"] != "unknown" for item in conditions) else "insufficient_records"


def _direction(row: dict) -> str:
    if row["dimensions"].get("direction_evidence") == "conflicting":
        return "unknown"
    return row["intervention_direction"]


def _locations(records: list[dict]) -> set[str]:
    return {row["subcellular_location"] for row in records
            if row["evidence_type"] == "identity" and row.get("subcellular_location")}


def _tools(records: list[dict], modality: str | None = None) -> list[dict]:
    return [row for row in records if row["evidence_type"] == "tool" and row.get("reviewed", True)
            and (modality is None or row.get("modality") == modality)]


def _accessibility(locations: set[str]) -> tuple[str, str]:
    if not locations:
        return "unknown", "Subcellular location is not reviewed. Organ expression is not cell or compartment accessibility."
    if len(locations) > 1:
        return "unknown", "Reviewed location records conflict, so none is selected."
    location = next(iter(locations))
    if location in {"extracellular", "plasma_membrane"}:
        return "met", f"Reviewed location is {location}. Cross-species recognition is still separate."
    return "unmet", "Reviewed location is intracellular. An unrecorded isoform is not invented to reverse this."


def _small_molecule(row: dict, records: list[dict]) -> dict:
    direction = _direction(row)
    tools = _tools(records, "small_molecule")
    mechanisms = {tool.get("intervention_mechanism") for tool in tools if tool.get("intervention_mechanism")}
    aligned = _ALIGNED.get(direction, set())
    if direction in _ALIGNED:
        direction_status, direction_detail = "met", "Reviewed direction is recorded separately from the expression sign."
    elif direction == "restore":
        direction_status, direction_detail = "unmet", "Restore is not read as small-molecule inhibition or activation."
    else:
        direction_status, direction_detail = "unknown", "No single reviewed functional direction is available."
    if tools:
        tool_status, tool_detail = "met", "A reviewed small-molecule tool record is present."
    else:
        tool_status, tool_detail = "unknown", "No reviewed small-molecule tool. Protein class does not substitute for one."
    if not tools or not mechanisms or direction_status != "met":
        mechanism_status, mechanism_detail = "unknown", "No reviewed mechanism is aligned to a usable direction."
    elif mechanisms <= aligned:
        mechanism_status, mechanism_detail = "met", "Reviewed mechanism matches the recorded direction."
    else:
        mechanism_status, mechanism_detail = "unmet", "Reviewed mechanism contradicts the recorded direction."
    conditions = [
        _condition("functional_direction", direction_status, direction_detail),
        _condition("recorded_small_molecule_tool", tool_status, tool_detail),
        _condition("mechanism_alignment", mechanism_status, mechanism_detail),
        _condition("selectivity", "unknown", "Selectivity across related proteins is not established."),
        _condition("tissue_exposure", "unknown", "Cell or tissue exposure is not established."),
    ]
    opened = direction_status == "met" and tool_status == "met" and mechanism_status == "met"
    return _option("small_molecule", _finish(conditions, opened=opened), conditions,
                   ["tool_and_direction_only", "protein_class_is_not_a_modality_assignment"])


def _protein_binder(row: dict, records: list[dict], modality: str) -> dict:
    status, detail = _accessibility(_locations(records))
    direction = _direction(row)
    own_tools = _tools(records, modality)
    direction_status = "met" if direction in {"inhibit", "activate", "restore"} else "unknown"
    conditions = [
        _condition("compartment_accessibility", status, detail),
        _condition("functional_direction", direction_status,
                   "Reviewed direction is required; a shared protein-class label is not a mechanism."),
        _condition("modality_specific_tool", "met" if own_tools else "unknown",
                   "An antibody record is not a peptide record, and the reverse is also unused."),
        _condition("agonist_or_antagonist", "unknown", "Agonist and antagonist mechanisms stay unresolved."),
        _condition("cross_species_recognition", "unknown", "An ortholog map does not establish species recognition."),
        _condition("tissue_distribution", "unknown", "Tissue distribution is not established."),
    ]
    return _option(modality, _finish(conditions, opened=False), conditions, ["separate_from_the_other_protein_modality"])


def _oligonucleotide(row: dict, records: list[dict], modality: str) -> dict:
    direction = _direction(row)
    if direction in {"activate", "restore"}:
        direction_status, direction_detail = "unmet", "RNA lowering or splice modulation does not restore or activate expression."
    elif direction == "inhibit":
        direction_status, direction_detail = "met", "Recorded direction is inhibit. The expression sign is not reused as the chemistry."
    else:
        direction_status, direction_detail = "unknown", "No reviewed direction is available."
    if row["entity_type"] == "transcript":
        target_status, target_detail = "met", "The entity is a transcript."
    elif row["entity_type"] == "gene":
        target_status, target_detail = "unknown", "A gene identifier does not select a transcript isoform."
    else:
        target_status, target_detail = "unmet", "The entity is not a gene or transcript."
    if modality == "siRNA":
        mechanisms = [
            _condition("rna_knockdown", "met" if any(tool.get("intervention_mechanism") == "RNA_knockdown" for tool in _tools(records, "siRNA")) else "unknown",
                       "Only a reviewed siRNA knockdown record meets this condition. An ASO record is not reused."),
        ]
    else:
        aso = _tools(records, "ASO")
        mechanisms = [
            _condition("aso_rna_knockdown", "met" if any(tool.get("intervention_mechanism") == "RNA_knockdown" for tool in aso) else "unknown",
                       "ASO knockdown is separate from siRNA knockdown."),
            _condition("splice_modulation", "met" if any(tool.get("intervention_mechanism") == "splice_modulation" for tool in aso) else "unknown",
                       "Splice modulation is a different mechanism and is not implied by knockdown."),
        ]
    conditions = [
        _condition("functional_direction", direction_status, direction_detail),
        _condition("target_rna", target_status, target_detail),
        *mechanisms,
        _condition("cell_uptake", "unknown", "Target-cell uptake is not established."),
        _condition("delivery", "unknown", "Organ expression, including liver expression, is not delivery evidence."),
    ]
    return _option(modality, _finish(conditions, opened=False), conditions, ["delivery_remains_unmet_until_separately_reviewed"])


def _supplementation(row: dict, modality: str) -> dict:
    direction = _direction(row)
    if direction == "restore":
        direction_status, direction_detail = "met", "Recorded direction is restore. Dose and localization are still open."
    elif direction in {"inhibit", "activate"}:
        direction_status, direction_detail = "unmet", "Inhibit or activate is not converted into expression supplementation."
    else:
        direction_status, direction_detail = "unknown", "No reviewed restore direction is available."
    conditions = [
        _condition("restore_direction", direction_status, direction_detail),
        _condition("expression_localization", "unknown", "Expression localization is not established."),
        _condition("dose_and_duration", "unknown", "Dose and duration are not established."),
        _condition("overexpression_risk", "unknown", "Excess expression remains an open limitation."),
        _condition("delivery", "unknown", "Delivery is not established."),
    ]
    return _option(modality, _finish(conditions, opened=False), conditions, ["separate_supplementation_record"])


def _editing(row: dict) -> dict:
    direction = _direction(row)
    known = direction in {"inhibit", "activate", "restore"}
    conditions = [
        _condition("editing_is_a_method", "met" if known else "unknown",
                   "DNA editing is a method. It does not supply the functional direction by itself."),
        _condition("functional_direction", "met" if known else "unknown",
                   "Any direction still has to come from reviewed functional evidence."),
        _condition("delivery", "unknown", "Delivery is not established."),
        _condition("persistence", "unknown", "Persistence and reversibility are not established."),
    ]
    return _option("DNA_editing", _finish(conditions, opened=False), conditions, ["never_opened_by_expression_sign"])


def _class_note(records: list[dict]) -> str:
    classes = sorted({row["protein_class"] for row in records if row.get("evidence_type") == "identity" and row.get("protein_class")})
    if not classes:
        return "No reviewed protein class is recorded; class is not inferred."
    if len(classes) > 1:
        return "Reviewed protein-class records conflict and none is selected."
    return f"Reviewed protein class is {classes[0]}; it does not assign a modality."


def screen_modalities(row: dict, reviewed: list[dict]) -> list[dict]:
    reviewed = [record for record in reviewed if record.get("reviewed") is True]
    if row["entity_type"] not in _DIRECT:
        options = [_option(modality, "insufficient_identity", [
            _condition("direct_entity", "unmet", "Metabolites, features, protein groups, and reactions need an explicit target map before a modality applies."),
        ], ["flux_or_feature_is_not_a_modality_target"]) for modality in MODALITIES]
    else:
        options = [
            _small_molecule(row, reviewed),
            _protein_binder(row, reviewed, "antibody"),
            _protein_binder(row, reviewed, "peptide"),
            _oligonucleotide(row, reviewed, "siRNA"),
            _oligonucleotide(row, reviewed, "ASO"),
            _supplementation(row, "mRNA"),
            _supplementation(row, "gene_delivery"),
            _editing(row),
        ]
        note = _class_note(reviewed)
        for option in options:
            option["basis"] = [*option["basis"], note]
    for option in options:
        option.update({"hypothesis_id": row["hypothesis_id"], "entity_key": row["entity_key"], "entity_id": row["entity_id"]})
    return options
