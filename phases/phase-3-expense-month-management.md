# Phase 3 — Expense Month Management

## Overview
Introduce the `ExpenseMonth` model and deliver the core lifecycle screens: creating a month, viewing a list of all months, editing a month label, and deleting a month along with all its associated data. The Home / Dashboard screen is also built here as the primary landing page after login, displaying a grid of expense month cards with key financial summaries. By the end of this phase a user can organise their finances by month and navigate freely between months.

---

## Goals
- Allow the user to create named expense months tied to a specific calendar month and year.
- Provide a Home screen that gives an at-a-glance overview of all months (income, expense, net balance).
- Enforce one expense month per calendar month per user — no accidental duplicates.
- Allow safe deletion of a month and all its downstream data (transactions, CSV upload records).

---

## Scope

### Data Model
- `ExpenseMonth` belongs to a `User` (FK).
- Fields: `label` (human-readable name, e.g. "February 2026"), `month` (DateField — day always stored as 1, encodes year + month), `created_at`.
- Unique constraint on `(user, month)` — one record per calendar month per user.

### Home / Dashboard Screen (`/`)
- Authenticated landing page shown after login.
- Displays a responsive card grid — one card per expense month.
- Each card shows: month label, total income, total expenses, net balance, and date range of transactions in that month.
- Cards are ordered with the most recent month first.
- "New Month" / "Create Expense Month" call-to-action button prominently placed.
- Placeholder section reserved at the bottom for Phase 6 chart widgets (visually distinct "Coming Soon" area or empty container).

### Expense Month List Screen (`/months/`)
- Tabular or card list of all expense months for the logged-in user.
- Shows label, month, transaction count, and action links (View, Edit, Delete).
- Link to create a new expense month.

### Create Expense Month (`/months/create/`)
- Form fields: month label (text) and month/year selector (month + year, or a date picker constrained to the 1st of the month).
- Validates that the selected month does not already exist for this user.
- On success, redirects to the new month's detail screen.

### Expense Month Detail (`/months/<id>/`)
- Header showing the month label and date range.
- **Summary cards row**: Total Income, Total Expenses, Net Balance — computed from all transactions in this month.
- Placeholder for the CSV upload area (built in Phase 4) and transaction table (built in Phase 5).
- Edit and Delete action buttons for the month.

### Edit Expense Month (`/months/<id>/edit/`)
- Allows updating the label only (the calendar month itself is immutable after creation to preserve data integrity).
- Pre-filled form, validates non-empty label.
- Redirects to the month detail screen on success.

### Delete Expense Month (`/months/<id>/delete/`)
- Confirmation screen clearly stating that all transactions and CSV upload records for this month will also be permanently deleted.
- On confirmation, cascades deletion of all related data.
- Redirects to Home on success with a confirmation flash message.

### Access Control
- A user can only view, edit, or delete their own expense months.
- Attempting to access another user's month returns a 404.

---

## Acceptance Criteria

| # | Criterion |
|---|-----------|
| 1 | After login, the user lands on the Home screen (`/`) and sees a card for each expense month they have created. |
| 2 | Each Home screen card displays the correct month label, total income, total expenses, and net balance. |
| 3 | A user with no months sees an empty state with a clear prompt to create their first expense month. |
| 4 | The user can create a new expense month by selecting a month/year and providing a label; on success they are taken to that month's detail screen. |
| 5 | Attempting to create a second expense month for the same calendar month shows a validation error; no duplicate record is created. |
| 6 | The expense month detail screen shows correct summary card totals (Income, Expenses, Net) based on any existing transactions. |
| 7 | The user can edit the label of an expense month; the updated label is reflected on the detail screen, list, and Home card. |
| 8 | The calendar month (year/month) cannot be changed after an expense month is created. |
| 9 | The delete confirmation screen explicitly warns the user that all transactions will be deleted. |
| 10 | Deleting an expense month removes the month and all its transactions and CSV upload records; the month no longer appears on Home or the list. |
| 11 | A user cannot access, edit, or delete an expense month that belongs to another user (returns 404). |
| 12 | The Home screen placeholder section for future dashboard charts is visible but clearly marked as not yet active. |
