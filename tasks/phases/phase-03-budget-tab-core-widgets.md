# Phase 3: Budget Tab — Core Widgets

## Description

Bring the **Budget tab** to life with its first two widgets and a month selector. The user picks a month and sees how their actual spending compares against the budgets they set up in Phase 1.

There are two core elements:

1. **Summary Cards** — four top-level numbers giving an at-a-glance view: total budgeted, total spent, remaining, and overall percentage used. Color-coded by health (green/yellow/red).
2. **Budget vs Actual Bar Chart** — a horizontal bar chart with one bar per category showing actual spending, with a marker at the budget line. Colors reflect status.

Data is served via a JSON API endpoint that the frontend fetches when the tab loads or the month changes. The endpoint computes per-category budget vs. actual spending and overall totals.

---

## Requirements

- A **month selector** dropdown defaulting to the current month. Changing it refreshes the tab's data.
- A **JSON API endpoint** that accepts a `month` parameter (YYYY-MM) and returns:
  - Per-category breakdown: category name, budgeted amount, spent amount, remaining, percentage used.
  - Overall totals: total budgeted, total spent, total remaining, overall percentage used.
  - Only includes categories that have a budget set.
- **Summary Cards** (4 cards row):
  - Total Budgeted | Total Spent | Remaining | Overall % Used.
  - Color logic: green when under 80% used, yellow at 80–100%, red when over 100%.
- **Budget vs Actual Horizontal Bar Chart** (ApexCharts):
  - One bar per category.
  - Each bar shows the spent amount; a marker/annotation indicates the budget limit.
  - Bar color reflects status (under/near/over budget).
- Data is fetched lazily — only when the Budget tab is active (not on initial page load if another tab could be default, though Budgets is default for now).
- The API is scoped to the authenticated user's data only.

---

## Acceptance Criteria

- [ ] The month selector defaults to the current month and lists available months.
- [ ] Changing the month re-fetches and re-renders all budget data.
- [ ] Summary cards display correct totals derived from the user's budgets and transactions.
- [ ] Cards are color-coded: green (<80%), yellow (80–100%), red (>100%).
- [ ] The bar chart shows one bar per budgeted category with correct spent amounts.
- [ ] Budget markers/annotations are visible on the chart for each category.
- [ ] Categories without a budget set do not appear in the chart or summary.
- [ ] A user with no budgets sees an empty state / helpful message (not a broken chart).
- [ ] A user with budgets but no transactions for the selected month sees $0 spent, full remaining.
- [ ] The API returns only the authenticated user's data.
- [ ] `make check` passes.
