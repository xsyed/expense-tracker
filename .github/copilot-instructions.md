# GitHub Copilot Instructions — django-expense-month

## Project Overview

Personal expense tracking app. All 6 phases complete.

- **Framework**: Django 4.2 LTS, Python 3.9
- **Database**: SQLite (dev + prod)
- **Frontend**: Bootstrap 5 + django-crispy-forms + HTMX + Aggrid community 32
- **Charts**: ApexCharts v5
- **Auth**: Custom `core.User` (email-based, no username)
- **Deployment**: Local only
---

## Toolchain & Quality Gate

Every quality check runs through `make check`:

```
make check   # typecheck + lint + unused + duplication + modulesize + security
```

Individual targets:
| Command | Tool | What it checks |
|---|---|---|
| `make typecheck` | mypy (strict) | Type correctness |
| `make lint` | ruff | Style, imports, complexity, annotations |
| `make unused` | vulture (≥80% confidence) | Dead code |
| `make duplication` | pylint R0801 | Code duplication (≥6 similar lines) |
| `make modulesize` | `scripts/check_module_sizes.py` | File line count (limit: 600 → 500 → 400) |
| `make security` | semgrep django/python | Security issues |

Pre-commit hooks run ruff, mypy, and `make unused duplication modulesize security` automatically on every commit.

**Never mark a task complete without running `make check` and confirming it passes.**

---

## Core Principles

### 1. Simplicity First
Make every change as simple as possible. Impact minimal code. When the same outcome can be achieved with less, choose less.

### 2. No Laziness — Senior Standards
- Find root causes. No temporary fixes, no workarounds.
- If a fix feels hacky, stop and ask: *"Knowing everything I know now, what is the elegant solution?"*
- A staff engineer must be able to approve the change without hesitation.

### 3. Minimal Impact
- Changes touch only what is necessary.
- Do not refactor surrounding code unless asked.
- Do not add docstrings, comments, or type annotations to untouched code.
- Do not add error handling for scenarios that cannot happen.

### 4. Self-Improvement Loop
After **any** correction from the user:
1. Open `tasks/lessons.md`.
2. Add the pattern as a new lesson: what went wrong, the root cause, the rule to enforce.
3. Review `tasks/lessons.md` at the start of every session — apply all relevant lessons before writing any code. 
4. IMPORTANT: be honest and specific in the lessons and also be concise, sacrifice grammar for the sake of concision. The more precise you are, the better you will learn. 

### 5. Verification Before Done
- Prove it works before declaring done.
- Run `make check`. If it fails, fix it — do not skip or suppress rules.
- For behaviour changes: diff what changed and confirm the diff is the minimum required.

### 6. Demand Elegance (Balanced)
- For non-trivial changes: pause and ask *"Is there a more elegant way?"*
- For simple, obvious fixes: skip this — don't over-engineer.

---

## Code Style

- **Line length**: 120 characters (enforced by ruff).
- **Type hints**: required everywhere; mypy strict mode must pass. Use `from __future__ import annotations` at the top of every module.
- **Annotations rule**: `ANN401` (Any) is forbidden; `PLR0913` (too-many-args) is ignored. All other ANN rules apply.
- **Imports**: isort-style ordering enforced by ruff `I` rules.
- **Complexity**: max McCabe complexity 10, max 50 statements per function, max 6 returns, max 12 branches.
- **Module size**: keep every file under 600 lines. Target is 500, then eventually 400. Split by functional concern when a file grows.
- No pandas dependency anywhere in this project.

---

## Pre-commit Hook

The pre-commit config (`.pre-commit-config.yaml`) runs:
1. `ruff --fix` + `ruff-format`
2. `mypy`
3. `make unused duplication modulesize security`

All hooks must pass before a commit lands. If they fail, fix the root cause — do not bypass with `--no-verify`.

SUPER CRITICAL: You have to run make check before completing a task, but the pre-commit hooks are an additional safety net to catch anything you missed. Do not disable or bypass them.

## Comment Strategy:

* **Minimize Comments:** Do not add comments for self-explanatory code (e.g., standard variable assignments, obvious loops, or boilerplate).
* **Code as Documentation:** Prioritize expressive naming for variables and functions over adding descriptive comments.
* **Exception Rule:** Only provide comments for "Why," not "What." Use them exclusively for non-obvious business logic, complex algorithms ($O(n \log n)$ or higher), or technical debt workarounds.
* **Formatting:** If a comment is necessary, keep it to a single line above the relevant code.

## Plan mode
- Ask any clarifying questions before writing code or proposing a solution.