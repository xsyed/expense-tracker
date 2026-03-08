# Lessons Learned

This file is updated after every correction from the user.
Format: **What went wrong → Root cause → Rule to enforce**

---

<!-- Add new lessons below this line. Most recent first. -->

## Always activate the virtual environment before running any command

**What went wrong**: Commands like `make check`, `mypy`, `ruff`, `python manage.py ...` fail or use the wrong interpreter when the venv is not active.
**Root cause**: The project dependencies are installed inside the venv, not globally.
**Rule**: Before running *any* command in this project, check whether the venv is active (`which python` should point inside `.venv/`). If not, activate it first:
```bash
source .venv/bin/activate
```
