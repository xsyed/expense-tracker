# Phase 8: Recurring Expenses Tab

## Description

Populate the **Recurring Expenses tab** with automatic detection of recurring transactions. The system analyzes the user's transaction history to identify expenses that repeat regularly (monthly, quarterly, etc.) based on description similarity and amount consistency.

This is a fully computed tab — no manual input from the user. The detection algorithm groups transactions by normalized description and flags those that appear in 3+ distinct months with similar amounts. The result is a table of recurring obligations and a summary of total recurring costs.

---

## Requirements

### Detection Logic

- Normalize transaction descriptions (lowercase, strip trailing numbers/dates) to group similar entries.
- A transaction pattern is "recurring" if:
  - The same normalized description appears in **3 or more distinct months**.
  - The amounts are within **±20%** of each other (to account for slight billing variations).
- For each recurring pattern, compute:
  - Average amount.
  - Frequency: monthly (appears most months), quarterly (every ~3 months), or other.
  - Number of months detected.
  - Estimated annual cost (average amount × inferred frequency).
- A JSON API endpoint returns the list of detected recurring expenses and summary totals.

### Widget: Recurring Expenses Table

- Sortable table with columns: Description, Average Amount, Frequency, Months Detected, Annual Estimate.
- Sorted by annual estimate descending by default (biggest recurring costs first).

### Widget: Recurring Summary Cards

- Two summary cards:
  - **Total Monthly Recurring**: Sum of average amounts for monthly-frequency items.
  - **Total Annual Recurring**: Sum of annual estimates for all recurring items.

### Edge Cases

- One-time large purchases that happen to have similar descriptions should not be flagged (the 3-month minimum protects against this).
- A user with very few transactions may see an empty state.

---

## Acceptance Criteria

- [ ] The tab detects recurring transactions based on description similarity and amount consistency.
- [ ] Only transactions appearing in 3+ distinct months with amounts within ±20% are flagged.
- [ ] The recurring expenses table shows description, average amount, frequency, months detected, and annual estimate.
- [ ] The table is sortable by any column.
- [ ] Summary cards show correct total monthly and annual recurring costs.
- [ ] One-time purchases with similar descriptions across fewer than 3 months are not flagged.
- [ ] A user with no recurring patterns sees a helpful empty state.
- [ ] All data is scoped to the authenticated user.
- [ ] `make check` passes.
