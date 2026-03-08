# Split Files Plan

## Context

`scripts/check_module_sizes.py` enforces a **600-line ceiling** today.
The goal is to tighten that to **500 lines**, then eventually **400 lines**.

Current file sizes (as of plan creation):

| File | Lines | 500 limit | 400 limit |
|------|-------|-----------|-----------|
| `core/views.py` | 592 | ❌ fails | ❌ fails |
| `core/csv_parser.py` | 272 | ✅ passes | ✅ passes |
| `core/models.py` | 190 | ✅ passes | ✅ passes |
| `core/forms.py` | 200 | ✅ passes | ✅ passes |
| `core/admin.py` | 58 | ✅ passes | ✅ passes |

Only `core/views.py` needs to be split before the limit is tightened.

---

## Proposed Split: `core/views.py` → 6 modules

Split by functional concern. Each resulting file targets **< 150 lines**.

### New modules

| New file | Views to move | Est. lines |
|---|---|---|
| `core/views_auth.py` | `signup_view`, `login_view`, `logout_view`, `home_view` | ~55 |
| `core/views_months.py` | `_month_summary`, `_cutoff_date`, `month_list_view`, `month_create_view`, `month_detail_view`, `month_edit_view`, `month_delete_view` | ~145 |
| `core/views_transactions.py` | `transaction_update_view`, `transaction_delete_view`, `update_grid_preferences_view`, `transaction_bulk_delete_view` | ~165 |
| `core/views_csv.py` | `csv_upload_view` | ~65 |
| `core/views_categories.py` | `category_list_view`, `category_edit_view`, `category_delete_view` | ~55 |
| `core/views_charts.py` | `chart_monthly_totals_view`, `chart_category_breakdown_view` | ~165 |

`core/views.py` becomes a **thin re-export shim** (or is deleted in favour of
updating `core/urls.py` to import directly from each sub-module).

### Approach A — Re-export shim (minimal urls.py change)

Keep `core/views.py`, replace its body with:

```python
# Re-export shim — import all view names so urls.py requires no changes.
from core.views_auth import home_view, login_view, logout_view, signup_view
from core.views_categories import category_delete_view, category_edit_view, category_list_view
from core.views_charts import chart_category_breakdown_view, chart_monthly_totals_view
from core.views_csv import csv_upload_view
from core.views_months import (
    month_create_view, month_delete_view, month_detail_view,
    month_edit_view, month_list_view,
)
from core.views_transactions import (
    transaction_bulk_delete_view, transaction_delete_view,
    transaction_update_view, update_grid_preferences_view,
)

__all__ = [
    "home_view", "login_view", "logout_view", "signup_view",
    "category_delete_view", "category_edit_view", "category_list_view",
    "chart_category_breakdown_view", "chart_monthly_totals_view",
    "csv_upload_view",
    "month_create_view", "month_delete_view", "month_detail_view",
    "month_edit_view", "month_list_view",
    "transaction_bulk_delete_view", "transaction_delete_view",
    "transaction_update_view", "update_grid_preferences_view",
]
```

### Approach B — Direct imports in urls.py (cleaner, no shim)

Delete `core/views.py` and update every import in `core/urls.py` to reference
the appropriate sub-module directly.

**Recommended: Approach B** — no shim file to maintain.

---

## Steps to Execute

1. Create each `core/views_*.py` file with the relevant functions cut from `core/views.py`.
2. Update `core/urls.py` to import from the new sub-modules.
3. Delete `core/views.py` (or replace with shim).
4. Run `make check` — all checks should pass.
5. Lower `MAX_LINES` in `scripts/check_module_sizes.py` from `600` → `500`.
6. Run `make check` again to confirm the new limit is met.
7. (Later) Repeat with `MAX_LINES = 400` once each sub-module is under 400 lines.

---

## Shared Imports to Factor Out

Several views import the same models/forms. Create a small shared import block
at the top of each new file rather than a separate `_imports.py` helper.
The common imports are:

```python
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from .models import Category, ExpenseMonth, Transaction, UserGridPreference
from .forms import ...
```
