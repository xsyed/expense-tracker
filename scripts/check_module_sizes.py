#!/usr/bin/env python3
"""Check that no Python source files exceed configured size thresholds."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

MAX_LINES = 500  # hard ceiling — target is 400 (see split_files_plan.md)
MAX_IMPORTS = 20
SEARCH_DIRS = ["core", "expense_month"]
SKIP_DIRS = {"migrations", "__pycache__"}


def count_imports(path: Path) -> int:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return 0
    return sum(1 for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom)))


def main() -> int:
    violations: list[str] = []
    root = Path(__file__).resolve().parent.parent

    for dir_name in SEARCH_DIRS:
        search_root = root / dir_name
        if not search_root.exists():
            continue
        for py_file in sorted(search_root.rglob("*.py")):
            if any(part in SKIP_DIRS for part in py_file.parts):
                continue
            rel = py_file.relative_to(root)
            text = py_file.read_text(encoding="utf-8")
            lines = len(text.splitlines())
            if lines > MAX_LINES:
                violations.append(f"  {rel}: {lines} lines (max {MAX_LINES})")
            imports = count_imports(py_file)
            if imports > MAX_IMPORTS:
                violations.append(f"  {rel}: {imports} imports (max {MAX_IMPORTS})")

    if violations:
        print("Module size violations:")
        for v in violations:
            print(v)
        return 1

    print("Module size check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
