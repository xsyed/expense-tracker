# Phase 6: Goals Tab — Core Widgets

## Description

Populate the **Goals tab** on the Insights page with two widgets that give users visibility into their goal progress:

1. **Goal Progress Cards** — a card per goal showing progress bar, amounts, deadline countdown, and a health status badge.
2. **Contribution Timeline** — a stacked bar chart showing monthly contribution amounts over time for savings goals.

A JSON API endpoint powers these widgets, computing progress, health status, and projections for each goal.

---

## Requirements

### API

- A JSON endpoint that returns a summary for every goal the user has:
  - Goal name, type, target amount, current progress amount, percentage complete.
  - Deadline and days remaining (if deadline is set).
  - Health status:
    - **Savings goals**: "on_track" if projected to reach target by deadline (based on average monthly contribution rate), "behind" if not, "completed" if already reached, "ahead" if ahead of pace. If no deadline, status is based on whether contributions are happening.
    - **Spending goals**: "on_track" if current month's spending ≤ target, "over" if exceeded.

### Widget: Goal Progress Cards

- One card per goal.
- Progress bar colored by health: green (on track / ahead), yellow (approaching limit), red (behind / over).
- Shows: current amount / target amount, percentage complete.
- Deadline countdown: "X days left" or "No deadline".
- Health badge: On Track, Behind, Ahead, Completed (with distinct visual indicators).

### Widget: Contribution Timeline

- Stacked bar chart (ApexCharts).
- X-axis: months. Y-axis: dollar amount contributed.
- One stacked series per savings goal (spending goals excluded — they don't have contributions).
- Shows the pattern of contributions over time.
- Only renders if the user has at least one savings goal with contributions.

---

## Acceptance Criteria

- [ ] The Goals tab shows a progress card for every goal the user has.
- [ ] Savings goal cards show progress based on total contributions.
- [ ] Spending goal cards show progress based on current month's category spending.
- [ ] Progress bars are color-coded by health status.
- [ ] Health badges display the correct status: On Track, Behind, Ahead, or Completed.
- [ ] Deadline countdown shows correct days remaining or "No deadline".
- [ ] The contribution timeline chart shows monthly stacked bars for savings goals.
- [ ] Goals without contributions show an appropriate empty state.
- [ ] A user with no goals sees a helpful empty state (not a broken UI).
- [ ] All data is scoped to the authenticated user.
- [ ] `make check` passes.
