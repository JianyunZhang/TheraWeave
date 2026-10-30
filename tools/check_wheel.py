"""Install a built wheel into a clean environment and exercise packaged assets."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment", type=Path, required=True)
    parser.add_argument("--dist", type=Path, required=True)
    parser.add_argument("--no-install", action="store_true", help="Use an already provisioned wheel environment (offline local check).")
    args = parser.parse_args()
    executable = args.environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    wheels = list(args.dist.glob("theraweave-*.whl"))
    if len(wheels) != 1:
        raise SystemExit("Expected exactly one TheraWeave wheel.")
    if not args.no_install:
        subprocess.run([str(executable), "-m", "pip", "install", str(wheels[0])], check=True)
    check = """
import importlib.util, json, pathlib, tempfile
import theraweave
from theraweave.demo import create_demo
from theraweave import DiscoveryProject
from theraweave.contract import snapshot
from theraweave import assess_archive, create_plans
assert importlib.util.find_spec('omicsweave') is None
assert 'site-packages' in str(pathlib.Path(theraweave.__file__)).replace('\\\\', '/')
with tempfile.TemporaryDirectory() as temp:
    root = pathlib.Path(temp)
    demo = create_demo(root / 'demo')
    out = DiscoveryProject.from_bundle(demo / 'bundle', context=demo / 'context.json', allow_draft=True).write_evidence_report(root / 'result')
    assert (out / 'import_report.html').is_file()
    assert snapshot()['contract_version'] == '0.1'
    assessment = assess_archive(out, root / 'assessment', snapshot_paths=sorted((demo / 'knowledge').glob('*.json')))
    plans = create_plans(assessment, root / 'plans')
    assert (assessment / 'decision_report.html').is_file()
    assert (plans / 'plans.json').is_file()
print(json.dumps({'wheel_import': True, 'demo_archive': True, 'assessment_and_plans': True, 'upstream_installed': False}))
"""
    subprocess.run([str(executable), "-I", "-c", check], check=True)


if __name__ == "__main__":
    main()
