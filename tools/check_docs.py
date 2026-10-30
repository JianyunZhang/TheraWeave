"""Check local Markdown links and parse fenced JSON/YAML examples."""
from __future__ import annotations

import json
import re
from pathlib import Path

import yaml


def main():
    paths = [Path("README.md"), *Path("docs").glob("*.md")]
    problems, blocks = [], 0
    for path in paths:
        text = path.read_text(encoding="utf-8")
        fences = [line for line in text.splitlines() if line.startswith("```")]
        if len(fences) % 2:
            problems.append(f"{path}: unclosed code fence")
        for label, link in re.findall(r"\[([^\]]+)\]\(([^)]+)\)", text):
            if not re.match(r"[a-z]+://|#", link) and not (path.parent / link.split("#")[0]).exists():
                problems.append(f"{path}: missing local link {link}")
        for language, block in re.findall(r"```(json|yaml)\n(.*?)\n```", text, re.S):
            try:
                json.loads(block) if language == "json" else yaml.safe_load(block)
                blocks += 1
            except (ValueError, yaml.YAMLError) as error:
                problems.append(f"{path}: {error}")
    print(json.dumps({"markdown_files": len(paths), "parsed_examples": blocks, "problems": problems}, ensure_ascii=False))
    return int(bool(problems))


if __name__ == "__main__":
    raise SystemExit(main())
