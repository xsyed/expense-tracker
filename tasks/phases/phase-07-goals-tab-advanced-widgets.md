# Phase 7: Goals Tab — Advanced Widgets

## Description

Add two projection/trend widgets to the Goals tab that help users understand whether they're on track to meet their goals:

1. **Goal Projection Chart** — for savings goals, plots historical contributions as a solid line, then extends a dashed projection line based on the average contribution rate. Shows the target as a horizontal line and the deadline (if set) as a vertical line, making it visually obvious whether the user will reach their goal on time.
2. **Spending Goal Trend** — for spending goals, shows the last 6 months of spending in the linked category as a line chart with a horizontal target line. Reveals whether spending is trending toward or away from the goal.

---

## Requirements

### Widget: Goal Projection Chart (Savings Goals)

- One chart per savings goal (or a selector to pick which goal to view).
- **Solid line**: Historical monthly cumulative contributions over time.
- **Dashed line**: Projected trajectory from the current point forward, based on the user's average monthly contribution.
- **Horizontal line**: Target amount.
- **Vertical line**: Deadline date (if set).
- Shows an estimated completion date (even if no deadline is set).
- A JSON API endpoint that returns historical cumulative data, projected data points, target, and deadline for a specific goal.

### Widget: Spending Goal Trend (Spending Goals)

- One chart per spending goal (or a selector).
- Line chart showing category spending for the last 6 months.
- Horizontal line at the target amount.
- Visual indication of trend direction: is spending going up or down relative to the target?
- Months with no spending in the category show as $0 (not skipped).

---

## Acceptance Criteria

- [ ] Savings goals have a projection chart with historical (solid) and projected (dashed) lines.
- [ ] The target amount appears as a horizontal line on the projection chart.
- [ ] If a deadline is set, it appears as a vertical line on the chart.
- [ ] The projection estimates a completion date and displays it.
- [ ] The projection is based on the average monthly contribution rate.
- [ ] Spending goals have a 6-month trend chart with actual spending and a target line.
- [ ] Months with no activity display as $0 on the spending trend chart.
- [ ] A goal with insufficient history (e.g., 1 month) still renders without errors.
- [ ] All data is scoped to the authenticated user.
- [ ] `make check` passes.
