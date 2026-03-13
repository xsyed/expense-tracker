# Phase 4: Budget Tab — Advanced Widgets

## Description

Extend the Budget tab with two more widgets that give deeper insight into budget health:

1. **Budget Health Donut** — a donut chart summarizing how many categories are on track, in warning, or over budget. A quick visual health check.
2. **Daily Burn Rate** — a line chart tracking cumulative spending through the current month against an ideal linear pace. Answers the question: *"Am I spending too fast this month?"*

Both widgets use the same month selector introduced in Phase 3.

---

## Requirements

- **Budget Health Donut Chart** (ApexCharts donut):
  - Three segments: On Track (green, <80% used), Warning (yellow, 80–100%), Over Budget (red, >100%).
  - Each segment represents the **count** of categories in that status.
  - Displays counts/percentages on hover.
  - Uses data already available from the Phase 3 budget summary endpoint (no new endpoint needed unless cleaner to separate).

- **Daily Burn Rate Line Chart** (ApexCharts line):
  - X-axis: day of month (1 through last day).
  - Y-axis: cumulative dollar amount.
  - **Line 1 — Actual**: cumulative daily spending (sum of all budgeted-category transactions up to each day).
  - **Line 2 — Ideal Pace**: a straight line from $0 on day 1 to total budget on the last day of the month.
  - Visual: the area between the lines or the line color should indicate whether spending is ahead of (red) or behind (green) the ideal pace.
  - A new **JSON API endpoint** that accepts `month` (YYYY-MM) and returns arrays of daily actual cumulative spending and ideal cumulative values.
  - For past months: shows complete data. For the current month: shows data up to today.

- Both widgets respond to the month selector and re-render on month change.

---

## Acceptance Criteria

- [ ] The donut chart displays three color-coded segments with correct category counts per status.
- [ ] Hovering/clicking a donut segment shows the count and percentage.
- [ ] The burn rate chart shows two lines: actual cumulative spending and ideal pace.
- [ ] The ideal pace line runs from $0 to total monthly budget over the days in the month.
- [ ] Actual spending line accumulates correctly per day based on transaction dates.
- [ ] For the current month, the actual line stops at today; for past months, it runs through the full month.
- [ ] Both charts update when the month selector changes.
- [ ] A user with no budgets sees an appropriate empty state for both widgets.
- [ ] A user with budgets but no spending sees a flat $0 actual line against the ideal pace.
- [ ] The burn rate API returns only the authenticated user's data.
- [ ] `make check` passes.
