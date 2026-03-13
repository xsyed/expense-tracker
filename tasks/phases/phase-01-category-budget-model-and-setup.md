# Phase 1: Category Budget Model & Setup Page

## Description

Introduce the concept of **budgeting per category**. Users should be able to assign a monthly budget amount to any of their categories. This is a global setting — one budget amount per category, automatically applied to every month.

The data layer needs a new model that links a user's category to a dollar amount. The UI is a dedicated setup page where the user sees all their categories in a table and can assign (or update) a budget amount to each one, then save everything in a single action.

This phase is foundational — it creates the data that all Budget-related insights (Phases 3–4) will consume.

---

## Requirements

- A new database model representing a per-category budget amount, scoped to the logged-in user.
- Each user can have at most one budget entry per category (enforced at the database level).
- Budget amounts are decimal values with 2 decimal places, supporting values up to 99,999,999.99.
- A setup page where the user can view all their categories and assign/edit budget amounts in one form.
- Categories without a budget amount are shown with an empty/zero field (not hidden).
- A single "Save" action persists all budget entries at once (create new ones, update existing ones).
- The setup page is only accessible to authenticated users.
- The page is reachable via a URL (linked later in Phase 2 from the Insights page).
- Register the new model in the admin interface.

---

## Acceptance Criteria

- [ ] A new migration exists and applies cleanly.
- [ ] The database enforces uniqueness of (user, category) for budget entries.
- [ ] Visiting the setup page shows every category the user owns, each with an editable amount field.
- [ ] Saving the form correctly creates new budget entries and updates existing ones.
- [ ] A category with no budget saved shows as empty/zero (not missing from the list).
- [ ] Users cannot see or modify another user's budgets.
- [ ] Unauthenticated users are redirected to login.
- [ ] `make check` passes (typecheck, lint, unused, duplication, modulesize, security).
