# Phase 10: Accounts Overview Tab

## Description

Populate the **Accounts Overview tab** to give users a bird's-eye view of how each of their financial accounts is performing. Answers: *"Which accounts have the most activity? How does income compare to expenses across accounts?"*

Three widgets:

1. **Account Summary Cards** — one card per account showing total income, total expenses, and net.
2. **Account Comparison Bar Chart** — a grouped bar chart comparing income and expenses across all accounts.
3. **Account Usage Trend** — a line chart showing monthly transaction volume per account over time.

---

## Requirements

### API

- A JSON endpoint that accepts an optional `months` parameter (default 6) and returns:
  - Per-account: account name, total income, total expenses, net (income − expenses), monthly breakdown by month.
  - Accounts with no transactions in the period are still included (with zeros).

### Widget: Account Summary Cards

- One card per account.
- Each card shows: account name, total income (green), total expenses (red), net amount (green if positive, red if negative).
- Covers the selected time range.

### Widget: Account Comparison Bar Chart

- Grouped bar chart (ApexCharts).
- X-axis: account names. For each account, two bars side by side: income (green) and expenses (red).
- Easy visual comparison across accounts.

### Widget: Account Usage Trend

- Line chart (ApexCharts).
- X-axis: months. Y-axis: transaction amount (or count — amount is more useful).
- One line per account.
- Shows how account usage changes over time.
- A time range selector (3M / 6M / 12M) consistent with the Category Trends tab.

### Edge Cases

- Accounts with no transactions should show $0, not be hidden.
- A user with only one account still sees meaningful data (no comparison, but summary is useful).

---

## Acceptance Criteria

- [ ] A summary card is displayed for each account the user has.
- [ ] Each card shows correct total income, total expenses, and net for the selected period.
- [ ] Net is green when positive, red when negative.
- [ ] The comparison bar chart shows grouped income/expense bars per account.
- [ ] The trend line chart shows monthly amounts per account over the selected range.
- [ ] The time range selector updates all three widgets.
- [ ] Accounts with no transactions display $0 (not hidden).
- [ ] A user with no accounts sees an appropriate empty state.
- [ ] All data is scoped to the authenticated user.
- [ ] `make check` passes.
