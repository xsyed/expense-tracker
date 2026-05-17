# Debt Payoff Goals

## Summary
Add `Debt` as a third goal type. A debt goal represents paying off a starting debt balance by a deadline, with progress autotracked from transactions in a required expense category, starting on the goal creation date.

## Key Changes
- Add `("debt", "Debt")` to `Goal.GOAL_TYPES` and create a Django migration altering `goal_type` choices.
- Update `GoalForm` so `spending` and `debt` goals require a category, and the selected category must be an expense category.
- Keep `target_amount` meaning fixed as starting debt for debt goals.
- Debt progress calculation:
  - Sum expense transactions for the attached category.
  - Only include transactions with `transaction.date >= goal.created_at.date()`.
  - Never count manual `GoalContribution` rows for debt goals.
- Reuse existing deadline fields and “needed to reach goal” math:
  - Debt card tooltip should say “Needed to pay off debt”.
  - Daily/weekly/monthly needed amount = remaining debt divided by days remaining.
- Update goal list cards:
  - Savings: existing contribution progress and Log Contribution button.
  - Spending: existing current-month limit tracking.
  - Debt: show `paid / target`, no manual contribution button, category displayed as autotrack source.
- Update Insights goals API/UI:
  - Include debt goals in the goal cards.
  - Reuse the existing projection widget for savings and debt goals, fed by savings contributions or debt category payments.
  - Rename contribution timeline to a neutral label such as “Goal Progress Timeline” and include monthly savings contributions plus debt payments.
  - Keep the spending trend widget limited to `spending` goals.

## Test Plan
- Add tests for debt goal creation:
  - `debt` appears as a valid goal type.
  - Debt goal without category is rejected.
  - Debt goal with an income category is rejected.
  - Debt goal with an expense category is accepted.
- Add tests for debt autotrack progress:
  - Transactions before the goal creation date do not count.
  - Transactions on or after the goal creation date count.
  - Transactions in other categories do not count.
- Add tests for insights data:
  - Debt goals return correct `progress_amount`, `pct_complete`, `health`, deadline fields, and projection data.
  - Projection endpoint works for `savings` and `debt`, still returns 404 for `spending`.
- Run `make check` before marking implementation complete.

## Assumptions
- “Pay full debt” means paying down a starting balance entered as `target_amount`.
- Debt payments are expense transactions, usually categorized as the existing default `Debt Payment` category or another user-selected expense category.
- Progress starts from the local date the goal was created; same-day payments count.
