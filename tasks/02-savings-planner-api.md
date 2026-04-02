# Task 2: Savings Planner Backend API

## Goal

Create the savings planner overview API endpoint that returns historical spending analysis data computed via pandas.

## Description

Create `core/views_savings_planner.py` with two views: a page view that renders the template, and a JSON endpoint that computes savings analysis from transaction history.

### Page View

`savings_planner_view(request)` — `@login_required`, renders `savings_planner/index.html` with no server-side data. Template created in Task 3.

### Overview Endpoint

`GET /api/savings-planner/overview/?months=6` — `@login_required`, returns `JsonResponse`.

**Query logic:**
1. Call `parse_month_range(request.GET.get("months"))` from `core.date_utils`
2. Fetch all `Transaction` objects where `expense_month__user=request.user` and `expense_month__month__in=month_starts`
3. Count unassigned transactions (`transaction_type="unassigned"`) — return count, exclude from further analysis
4. Load remaining transactions (income + expense only) into a pandas DataFrame with columns: `month` (YYYY-MM string from `expense_month__month`), `amount`, `transaction_type`, `category_name` (`category__name`), `category_type` (`category__category_type`), `expense_type` (`category__expense_type`)
5. Handle NULL category: treat as `expense_type="variable"`, `category_name="Uncategorized"`, `category_type="expense"`

**Monthly series computation (per month in range):**
- `income`: sum of amounts where `transaction_type="income"`
- `fixed`: sum where `transaction_type="expense"` AND `expense_type="fixed"`
- `variable`: sum where `transaction_type="expense"` AND `expense_type="variable"` (includes uncategorized)
- `savings_transfer`: sum where `transaction_type="expense"` AND `expense_type="savings_transfer"`
- `savings`: `income - fixed - variable` per month (savings_transfer excluded from expenses)

**Averages:** mean of each monthly series across all months in range.

**Savings rate:** `(avg_income - avg_fixed - avg_variable) / avg_income × 100` (0 if no income).

**Savings breakdown:**
- `explicit_transfers`: avg_savings_transfer
- `unallocated`: avg_income - avg_fixed - avg_variable - avg_savings_transfer

**Per-category stats** (expense categories only, `transaction_type="expense"`):
- Group by category_name. For each category, compute monthly totals.
- **Zero-fill**: for months in range where category has no transactions, use $0.
- Compute: `avg_spend` (mean of zero-filled monthly totals), `min_spend` (min including zeros), `max_spend` (max), `expense_type`
- `cut_potential = max(0, avg_spend - min_spend)` for `expense_type="variable"` only; 0 for fixed and savings_transfer

**Response shape:** as specified in plan.md (see `category_stats`, `monthly`, `savings_breakdown`, `unassigned_count` fields).

**Empty state handling:**
- 0 transactions: return all zeros/empty arrays with `months` list
- 1 month: still compute stats, frontend shows warning

### URL Wiring

Add to `expense_month/urls.py`:
```
path("savings-planner/", savings_planner_view, name="savings_planner"),
path("api/savings-planner/overview/", savings_planner_overview_api, name="savings_planner_overview_api"),
```

### pandas Usage

- Import pandas (`import pandas as pd`)
- ORM `.values()` queryset → `pd.DataFrame()`
- Use `pivot_table` or `groupby` for monthly category aggregation
- Use `.reindex()` for zero-fill across all months
- Add pandas to `requirements.txt` if not already present

## Acceptance Criteria

- [ ] `core/views_savings_planner.py` exists with `savings_planner_view` and `savings_planner_overview_api`
- [ ] Both views are `@login_required` and scope data to `request.user`
- [ ] Overview endpoint returns correct JSON shape with all fields from plan
- [ ] Monthly series arrays have one entry per month in range, in chronological order
- [ ] Zero-fill works: categories absent in some months show $0 for those months
- [ ] Uncategorized transactions (NULL category) treated as variable, named "Uncategorized"
- [ ] Unassigned transactions excluded from calculations, count returned in response
- [ ] Savings rate formula correct: `(income - fixed - variable) / income`; savings_transfer excluded
- [ ] `savings_breakdown` shows explicit_transfers + unallocated correctly
- [ ] cut_potential is 0 for fixed and savings_transfer categories
- [ ] Empty state (0 transactions) returns valid JSON with zeros
- [ ] URLs registered in `expense_month/urls.py`
- [ ] pandas is in `requirements.txt`
- [ ] Module stays under 400 lines
- [ ] `make check` passes

## Files

- `core/views_savings_planner.py` (new)
- `expense_month/urls.py` (edit)
- `requirements.txt` (edit if needed)

## Dependencies

- Task 1 (Category `expense_type` field must exist)
