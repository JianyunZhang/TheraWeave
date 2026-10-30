"""Local CLI; exit codes: 0 success, 1 operational error, 2 invalid input."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .contract import snapshot, validate_bundle, validate_context
from .core import BundleValidationError
from .demo import create_demo
from .project import DiscoveryProject
from .assessment import assess_archive
from .knowledge import load_snapshots
from .planning import create_plans, review_plan, record_outcome
from .core import read_json
from .source_adapters import convert_source


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="theraweave", description="Local evidence import preview; not a validated target-ranking model.")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("contract-info", help="Show the pinned upstream draft snapshot and source hashes.")
    demo = commands.add_parser("demo", help="Write a synthetic draft bundle into a NEW directory.")
    demo.add_argument("destination", type=Path)
    knowledge = commands.add_parser("knowledge-validate", help="Validate normalized local snapshots without network access.")
    knowledge.add_argument("snapshots", nargs="+", type=Path)
    convert = commands.add_parser("knowledge-convert", help="Normalize local Open Targets evidence, UniProt JSON, or ChEMBL mechanism+target files.")
    convert.add_argument("source", choices=["OpenTargets", "UniProt", "ChEMBL"])
    convert.add_argument("input", type=Path)
    convert.add_argument("--metadata", type=Path, required=True)
    convert.add_argument("--taxon-id", type=int)
    convert.add_argument("--target-map", type=Path)
    convert.add_argument("--output", type=Path, required=True)
    assess = commands.add_parser("assess", help="Create an evidence profile and explicit rule-based experimental priorities.")
    assess.add_argument("archive", type=Path)
    assess.add_argument("--snapshot", action="append", type=Path, default=[])
    assess.add_argument("--policy", type=Path)
    assess.add_argument("--output", required=True, type=Path)
    plan = commands.add_parser("plan", help="Create draft validation plans from an assessment archive.")
    plan.add_argument("assessment", type=Path)
    plan.add_argument("--output", type=Path, required=True)
    review = commands.add_parser("review-plan", help="Save an explicit scientific review as a new immutable plan version.")
    review.add_argument("plans", type=Path)
    review.add_argument("--plan-id", required=True)
    review.add_argument("--review", required=True, type=Path)
    review.add_argument("--output", required=True, type=Path)
    feedback = commands.add_parser("record-outcome", help="Record a quantitative result against the exact reviewed plan.")
    feedback.add_argument("reviewed_plan", type=Path)
    feedback.add_argument("--outcome", required=True, type=Path)
    feedback.add_argument("--output", required=True, type=Path)
    for name in ("validate", "import"):
        command = commands.add_parser(name, help="Validate a draft bundle." if name == "validate" else "Create a new evidence archive and offline report.")
        command.add_argument("bundle", type=Path)
        command.add_argument("--allow-draft", action="store_true", help="Explicitly accept draft 0.1 limitations.")
        command.add_argument("--context", type=Path, required=name == "import")
        if name == "import":
            command.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "contract-info":
            output = snapshot()
        elif args.command == "demo":
            output = {"demo": str(create_demo(args.destination)), "synthetic": True}
        elif args.command == "knowledge-validate":
            knowledge = load_snapshots(args.snapshots)
            output = {"sources": list(knowledge["sources"]), "deduplicated_assertions": len(knowledge["records"]), "valid": True}
        elif args.command == "knowledge-convert":
            output = {"output": str(convert_source(args.source, args.input, args.output, metadata=read_json(args.metadata),
                                                   taxon_id=args.taxon_id, target_map=args.target_map)), "reviewed": False}
        elif args.command == "assess":
            path = assess_archive(args.archive, args.output, snapshot_paths=args.snapshot,
                                  policy=read_json(args.policy) if args.policy else None)
            output = {"output": str(path), "report": str(path / "decision_report.html"), "policy_validated_on_real_studies": False}
        elif args.command == "plan":
            output = {"output": str(create_plans(args.assessment, args.output)), "status": "draft"}
        elif args.command == "review-plan":
            output = {"output": str(review_plan(args.plans, args.plan_id, args.review, args.output)), "status": "reviewed"}
        elif args.command == "record-outcome":
            output = {"output": str(record_outcome(args.reviewed_plan, args.outcome, args.output))}
        elif args.command == "validate":
            bundle = validate_bundle(args.bundle, allow_draft=args.allow_draft)
            if args.context and bundle.report.valid:
                validate_context(args.context, bundle)
            print(json.dumps(bundle.report.to_dict(), ensure_ascii=False, indent=2))
            return 0 if bundle.report.valid else 2
        else:
            project = DiscoveryProject.from_bundle(args.bundle, context=args.context, allow_draft=args.allow_draft)
            path = project.write_evidence_report(args.output)
            output = {"output": str(path), "report": str(path / "import_report.html"), "validation": project.bundle.report.to_dict()}
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0
    except BundleValidationError as exc:
        print(json.dumps(exc.report.to_dict(), ensure_ascii=False, indent=2))
        return 2
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": type(exc).__name__, "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
