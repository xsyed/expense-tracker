# Phase 5 — Transaction Table & Inline Editing

## Overview
Make every imported transaction visible and fully editable directly within the expense month detail screen. Users can classify each transaction as income or expense, assign a category, correct the date, description, amount, or account — all without leaving the page. Changes are saved automatically as the user interacts with each field, powered by HTMX. The summary cards (Total Income, Total Expense, Net Balance) stay in sync with every edit. Individual transactions can also be deleted. By the end of this phase the core working loop of the application is complete.

---

## Goals
- Render all transactions for an expense month in a sortable, readable table on the detail screen. 
- IMPORTANT: Use AG Grid Community v32 (LTS) version for the transaction table to leverage its built-in features like sorting, pagination, and inline editing. This will save development time and provide a more robust user experience compared to building a custom table from scratch.
- Make every column of every transaction row editable inline with auto-save (no separate edit page).
- Keep the page summary cards (Income / Expense / Net) live and accurate after every change.
- Allow users to delete individual transactions.
- Provide enough visual feedback that the user always knows whether a save succeeded or failed.

---

## Scope

### Transaction Table Layout
- Displayed on the Expense Month Detail screen (`/months/<id>/`) below the summary cards and upload area.
- Columns: **Date** | **Description** | **Amount** | **Account** | **Type** | **Category** | **Actions**
- Each row represents one `Transaction` record.
- Default sort: by `date` ascending; the user can sort by any column header.
- When a month has no transactions, an empty-state message is shown (e.g. "No transactions yet — upload a CSV above.").

### Inline Editing — Field Behaviour

| Column | Input type | Save trigger |
|--------|-----------|--------------|
| Date | Date input | On blur |
| Description | Text input | On blur |
| Amount | Number input (2 decimal places) | On blur |
| Account | Text input | On blur |
| Type | Select dropdown (Income / Expense / Unassigned) | On change |
| Category | Select dropdown (user's categories + blank option) | On change |

- Each editable cell uses HTMX to POST the updated value to the inline update endpoint on trigger.
- The server validates the new value, saves it, and returns the refreshed `<tr>` row partial which replaces the current row in the DOM (HTMX `outerHTML` swap).
- The summary cards are updated in the same server response via HTMX out-of-band swap so totals stay accurate without a full page reload.

### Inline Update Endpoint (`/months/<id>/transactions/<tx_id>/update/`)
- Accepts a POST with the field name and new value.
- Validates the input (e.g. date is a valid date, amount is a positive number, type is a recognised choice).
- Saves the change and returns the updated row partial.
- On validation failure, returns the row partial with an inline error indicator — the original value is preserved in the database.

### Summary Cards (Live Totals)
- **Total Income** — sum of `amount` for all `income` transactions in the month.
- **Total Expense** — sum of `amount` for all `expense` transactions in the month.
- **Net Balance** — Total Income minus Total Expense. Shown in green when positive, red when negative.
- All three cards re-render via HTMX out-of-band swap after every successful inline save or transaction deletion.
- Cards also recalculate after a CSV upload (from Phase 4).

### Delete Transaction
- Each row has a **Delete** button in the Actions column.
- Clicking Delete shows a confirmation step (inline confirm button swap or a small modal) — no accidental single-click deletes.
- On confirmation, the row is removed from the DOM and the summary cards update to reflect the deletion.

### Visual Feedback
- While an HTMX request is in-flight, a subtle loading state (spinner or opacity change) is shown on the row being updated.
- A brief success indicator (e.g. green highlight flash on the saved cell) confirms the save completed.
- Validation errors are surfaced inline next to the offending cell without disrupting the rest of the table.

### Keyboard & Usability
- Pressing **Enter** on a text/number input triggers blur and therefore auto-save.
- Tab order moves naturally across cells in a row.

---

## Acceptance Criteria

| # | Criterion |
|---|-----------|
| 1 | All transactions for the expense month are displayed in the table with correct date, description, amount, account, type, and category values. |
| 2 | The table is sorted by date ascending by default. |
| 3 | Clicking a date, description, amount, or account cell activates an input field; tabbing or clicking away saves the change without a page reload. |
| 4 | Changing the Type dropdown immediately saves the new value; the row reflects the update without a page reload. |
| 5 | Changing the Category dropdown immediately saves the new value; the row reflects the update without a page reload. |
| 6 | After any inline save, the Total Income, Total Expense, and Net Balance summary cards update to reflect the new totals. |
| 7 | Entering an invalid value (e.g. letters in the Amount field, invalid date) shows a clear inline error on that cell; the database retains the previous valid value. |
| 8 | The user can delete an individual transaction row; the row disappears and summary cards update accordingly. |
| 9 | Deleting a transaction requires an explicit confirmation step; a single accidental click does not delete. |
| 10 | An expense month with no transactions shows an empty-state message instead of an empty table. |
| 11 | A row shows a visible loading/pending state while its HTMX save request is in flight. |
| 12 | Net Balance is displayed in green when positive and red when negative (or zero). |
| 13 | The Category dropdown in each row is populated with the user's current categories (including any added or renamed since the page loaded — categories list is fresh per request). |
| 14 | All inline edits and deletes are scoped to the logged-in user's own transactions; direct URL manipulation against another user's transactions returns a 404. |


SUPER CRITICAL: Use AG Grid Community v32 (LTS) version for the transaction table