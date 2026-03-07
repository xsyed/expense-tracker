# Phase 6 — Dashboard Analytics & Charts

## Overview
Bring the Home / Dashboard screen to life with five ApexCharts v5 data visualisations that give the user a rich, at-a-glance picture of their financial patterns across months. The placeholder section reserved in Phase 3 is replaced with fully interactive chart widgets. No new data models are introduced — all charts are derived from the `Transaction` data already stored. By the end of this phase the application delivers its full Phase 1 feature set and the product is considered v1.0 complete.

---

## Goals
- Surface five meaningful financial insights as interactive, visually polished charts on the Home dashboard.
- All charts derive their data server-side from existing `Transaction` records — no new models required.
- Charts load without blocking the main page; data is fetched and rendered client-side via ApexCharts.
- The dashboard remains fast and usable even when there is limited historical data (graceful empty states per widget).

---

## Scope

### Dashboard Layout
- The Home screen (`/`) is restructured into two sections:
  1. **Expense Month Cards grid** (existing from Phase 3) — kept at the top.
  2. **Analytics section** below — contains the five chart widgets in a responsive grid layout.
- Charts span the full available width on desktop; stack to single column on narrow viewports.
- A month/date range selector at the top of the analytics section allows the user to control the time window applied to all charts simultaneously (default: last 6 months).

### Chart 1 — Monthly Income vs Expense (Grouped Bar)
- X-axis: each calendar month with data.
- Y-axis: dollar amount.
- Two bars per month — one for total income, one for total expense.
- Hovering a bar shows the exact total for that month and type.

### Chart 2 — Category Breakdown (Donut / Pie)
- Visualises the expense distribution across categories for the **selected month** (or the most recent month by default).
- Each slice represents one category's share of total expenses.
- Hovering a slice shows the category name and total amount.
- Transactions still `unassigned` or without a category are grouped into an "Unclassified" slice.
- A month selector within the widget (or the global selector) controls which month's data is shown.

### Chart 3 — Spending Trend (Line Chart)
- Rolling view over the most recent 6 months (or the user's full history if less than 6 months exist).
- X-axis: month labels.
- Y-axis: total expense amount.
- A single line traces the user's spending over time.
- Hovering a data point shows the exact total for that month.

### Chart 4 — Top Spending Categories (Horizontal Bar)
- Shows the top N categories (default: top 5) ranked by total expense amount over the selected time window.
- X-axis: total expense amount.
- Y-axis: category names.
- Hovering a bar shows the exact total and percentage share of overall spending.

### Chart 5 — Month-over-Month Comparison (Stacked Bar)
- Compares the current month and the previous month side by side across categories.
- Each bar is stacked by category to show how the composition of spending shifted.
- Useful for identifying which categories drove increases or decreases.

### Data Endpoints
- Each chart retrieves its data from a dedicated JSON endpoint on the server.
- Endpoints are protected (login required) and scoped to the logged-in user's data only.
- Data is returned as JSON; ApexCharts renders it client-side.

### Empty States
- If there is insufficient data to render a chart (e.g. only one month exists for a comparison chart, or no categorised transactions exist for the donut), the widget shows a friendly empty-state message instead of a broken or empty chart.

### Performance
- Chart data endpoints aggregate data at the database level (not in Python loops over all rows).
- The Home page HTML load does not wait for chart data — charts render asynchronously after the page loads.

---

## Acceptance Criteria

| # | Criterion |
|---|-----------|
| 1 | The Home dashboard displays all five chart widgets below the expense month card grid. |
| 2 | **Chart 1** (Monthly Income vs Expense) renders two bars per month and correctly reflects the income and expense totals from stored transactions. |
| 3 | **Chart 2** (Category Breakdown donut) shows the correct proportional split of expense transactions by category for the selected month. |
| 4 | **Chart 2** groups transactions with no assigned category into an "Unclassified" slice rather than omitting them. |
| 5 | **Chart 3** (Spending Trend line) plots total monthly expenses and defaults to showing the last 6 available months. |
| 6 | **Chart 4** (Top Spending Categories) correctly ranks categories by total expense and shows at least the top 5. |
| 7 | **Chart 5** (Month-over-Month stacked bar) correctly compares the two most recent months stacked by category. |
| 8 | All charts update when the user changes the global month/date range selector without a full page reload. |
| 9 | Each chart displays a clear empty-state message when there is insufficient data to render it meaningfully. |
| 10 | All chart data endpoints return only data belonging to the logged-in user; they are not accessible when unauthenticated. |
| 11 | The Home page HTML loads and displays the expense month cards before chart data has finished loading — charts render asynchronously. |
| 12 | Hovering over any data point or bar/slice on any chart shows a tooltip with the relevant label and exact value. |
| 13 | The dashboard layout is responsive — charts stack to a single column on narrow viewports without overflowing. |
