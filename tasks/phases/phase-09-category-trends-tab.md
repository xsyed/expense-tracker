# Phase 9: Category Trends Tab

## Description

Populate the **Category Trends tab** to answer: *"Where is my spending going up or down?"* This tab analyzes spending by category over a configurable number of months and presents visual trend indicators.

Two widgets:

1. **Category Sparkline Grid** — a grid of small cards, each showing a category name, a tiny sparkline chart, a trend arrow, and the percentage change.
2. **Movers Table** — a two-column layout highlighting the top 5 biggest increases and top 5 biggest decreases in spending by category.

---

## Requirements

### API

- A JSON endpoint that accepts an optional `months` parameter (default 6) and returns:
  - Per-category: name, array of monthly spending amounts (one per month in the range), trend direction ("up", "down", or "stable"), and percentage change (comparing most recent month to the average of prior months, or first vs last — pick a sensible comparison).
  - Handles months with no spending in a category by including $0, not by skipping the month.

### Widget: Category Sparkline Grid

- Grid of cards (responsive — multiple per row on wide screens, fewer on narrow).
- Each card shows:
  - Category name.
  - A small sparkline line chart (ApexCharts sparkline) showing spending over the selected months.
  - A trend arrow: ↑ (spending increasing), ↓ (spending decreasing), → (stable, defined as <5% change).
  - Percentage change with appropriate color (red for increases, green for decreases — since lower spending is good).
- A selector to choose the time range: 3 months, 6 months, 12 months.

### Widget: Movers Table

- Two-column layout:
  - **Left column ("Spending Up ↑")**: Top 5 categories with the biggest percentage increase.
  - **Right column ("Spending Down ↓")**: Top 5 categories with the biggest percentage decrease.
- Each entry shows: category name, percentage change, absolute change ($).
- Categories with zero spending in the baseline period are excluded from percentage calculations (avoid divide-by-zero).

---

## Acceptance Criteria

- [ ] The sparkline grid shows a card for every category with spending in the selected range.
- [ ] Each sparkline correctly reflects the category's monthly spending pattern.
- [ ] Trend arrows are correct: ↑ for increases, ↓ for decreases, → for stable (<5% change).
- [ ] Percentage changes are color-coded: red for increases (bad), green for decreases (good).
- [ ] The time range selector (3M / 6M / 12M) re-fetches and re-renders all data.
- [ ] Movers table shows the top 5 biggest increases and decreases.
- [ ] Categories with both zero baseline and zero current spending are excluded from movers.
- [ ] Months with no transactions for a category show as $0 (not omitted).
- [ ] A user with only one month of data sees sparklines with a single point and no percentage change.
- [ ] All data is scoped to the authenticated user.
- [ ] `make check` passes.
