# Lessons Learned

This file is updated after every correction from the user.
Format: **What went wrong → Root cause → Rule to enforce**

---

<!-- Add new lessons below this line. Most recent first. -->

## Savings planner historical minimum must not use injected zero months

**What went wrong**: I explained `$0` historical minimums as expected before checking whether the table label matched user intent.
**Root cause**: `_category_stats()` filled missing category months with `0.0` for all metrics, so "Historical Min" showed missing-month zeros instead of the lowest observed spend month.
**Rule**: When displaying a category's historical minimum, compute it from observed category months only. Use full selected range for monthly average only when the metric is explicitly average monthly impact.

## Static 403 can be caused by parent directory traversal, not missing files

**What went wrong**: nginx returned `403` for `/expense-tracker/static/js/csv_mapper.js` even after the file existed in `/home/sami/expense-tracker/staticfiles/js/`.
**Root cause**: `www-data` could not traverse `/home/sami` because it was `750` (`drwxr-x---`). File and lower directories were readable, but the parent home directory blocked access.
**Rule**: When nginx returns `403` for an existing static file: verify the full path with `namei -l` and test access as the nginx user (`sudo -u www-data test -r ...`) before changing nginx or app code. Prefer a targeted ACL fix like `setfacl -m u:www-data:rx /home/sami` over broad `chmod 755`.

## CSP must account for data: URIs used by third-party libraries

**What went wrong**: AG Grid 32 embeds icon fonts as `data:font/woff2;base64,...` URIs. CSP `font-src 'self' https://cdn.jsdelivr.net` blocked them — icons didn't render on the months detail page.
**Root cause**: Assumed CDN fonts only come from CDN URLs. Libraries like AG Grid inline fonts as data URIs in their CSS.
**Rule**: When adding a CDN library to a CSP-protected site: (1) Check if the library uses `data:` URIs for fonts/images — AG Grid, FontAwesome, and others do. (2) Add `data:` to the relevant CSP directive (`font-src`, `img-src`). (3) Also add the CDN to `connect-src` if DevTools source maps are requested. (4) Test every page that uses the library after deploying CSP changes.

## FORCE_SCRIPT_NAME breaks hardcoded JS fetch URLs and raw path settings

**What went wrong**: Deployed to subpath `/expense-tracker/` but JS fetch calls used hardcoded `/api/...` paths — nginx strips the prefix but Django URLs don't include it, so the browser requests went to wrong path. Also `LOGIN_REDIRECT_URL = "/"` is a raw path Django doesn't prepend `FORCE_SCRIPT_NAME` to.
**Root cause**: `FORCE_SCRIPT_NAME` only affects `{% url %}` tags and `reverse()`. Hardcoded paths in JS and raw path settings are invisible to it.
**Rule**: (1) Never hardcode URL paths in JS — always use `SCRIPT_PREFIX` global (set via context processor in `base.html`). (2) Always use named URLs for Django settings like `LOGIN_REDIRECT_URL`. (3) When adding new `fetch()` calls, prefix with `SCRIPT_PREFIX +`. (4) `{% url %}` in templates is always safe. (5) Audit all fetch calls on any deployment-related change.

## django-stubs-ext must be in requirements-prod.txt if code uses generic subscripts

**What went wrong**: `BaseUserAdmin[Any]` and `admin.ModelAdmin[Model]` crashed at import time in production container — `TypeError: 'MediaDefiningClass' object is not subscriptable`.
**Root cause**: `django_stubs_ext.monkeypatch()` patches Django classes to support `[]` syntax. It runs in dev (in `settings.py`) but the package was excluded from `requirements-prod.txt`.
**Rule**: If any module uses `SomeDjangoClass[T]` syntax at runtime (not just in TYPE_CHECKING), `django-stubs-ext` must be in prod dependencies.

## nginx proxy_pass trailing slash forbidden in regex location blocks

**What went wrong**: Adding trailing `/` to `proxy_pass http://.../:` inside `location ~ regex {}` caused nginx config test failure.
**Root cause**: nginx forbids URI part in `proxy_pass` inside regex/named/if/limit_except locations.
**Rule**: For regex location blocks, use `rewrite ^/prefix(/.*)$ $1 break;` + `proxy_pass http://host;` (no trailing slash). For prefix location blocks, `proxy_pass http://host/;` with trailing slash is fine.

## Health check URL must bypass FORCE_SCRIPT_NAME when hitting gunicorn directly

**What went wrong**: Docker healthcheck and CI deploy curled `http://localhost:8000/expense-tracker/health/` directly to gunicorn, got 404.
**Root cause**: `/expense-tracker/` prefix is stripped by nginx. Gunicorn serves at `/health/` directly.
**Rule**: Internal health checks (docker-compose healthcheck, CI deploy script) must use `http://localhost:8000/health/` — no subpath prefix.

## When user asks for doc update after fix, update artifact immediately

**What went wrong**: I fixed the bug in code but left `bug.md` describing only the earlier attempted fix.
**Root cause**: I closed the task at code validation and missed the user-visible task artifact.
**Rule**: If the workspace includes a bug/task note tied to the issue, update it to match the final implemented fix before finishing.

## Always activate the virtual environment before running any command

**What went wrong**: Commands like `make check`, `mypy`, `ruff`, `python manage.py ...` fail or use the wrong interpreter when the venv is not active.
**Root cause**: The project dependencies are installed inside the venv, not globally.
**Rule**: Before running *any* command in this project, check whether the venv is active (`which python` should point inside `.venv/`). If not, activate it first:
```bash
source .venv/bin/activate
```
