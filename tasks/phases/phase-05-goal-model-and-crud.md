# Phase 5: Goal Model & CRUD

## Description

Introduce **financial goals** — targets the user wants to achieve. There are two types:

- **Savings goals**: The user wants to save a target amount (e.g., $5,000 for a vacation). Progress is tracked via manual contributions the user logs over time.
- **Spending goals**: The user wants to keep spending in a category under a target amount per month (e.g., spend less than $200/month on dining). Progress is automatically derived from transaction data.

This phase creates the data layer (two new models: one for goals, one for contributions) and a full set of pages to create, edit, delete, and view goals, plus a page to log contributions toward savings goals.

---

## Requirements

### Models

- **Goal model**:
  - Belongs to a user.
  - Has a name (up to 100 characters).
  - Has a type: either "savings" or "spending".
  - Has a target amount (decimal, 2 places).
  - Optionally linked to a category (required for spending goals, optional for savings).
  - Optional deadline (date).
  - Tracks creation date automatically.

- **Goal Contribution model**:
  - Belongs to a goal.
  - Has an amount (decimal, 2 places).
  - Has a date.
  - Has an optional note (up to 200 characters).
  - Tracks creation date automatically.
  - Ordered by most recent first.

### Pages

- **Goal list**: Shows all the user's goals as cards, each displaying the goal name, type, target amount, current progress (as a progress bar), and deadline (if set).
  - Savings goal progress = sum of all contributions.
  - Spending goal progress = current month's category spending vs. target (lower is better — shows how close to the limit).
- **Create goal**: Form to create a new goal with all required fields. Category field is conditionally required based on goal type.
- **Edit goal**: Pre-filled form to modify an existing goal.
- **Delete goal**: Confirmation page before deleting a goal and all its contributions.
- **Log contribution** (savings goals only): Simple form with amount, date, and optional note.

### Validation

- Spending goals must have a category selected.
- Users can only manage their own goals.
- All pages require authentication.

---

## Acceptance Criteria

- [ ] Two new migrations exist and apply cleanly.
- [ ] Creating a savings goal without a category works; creating a spending goal without a category is rejected.
- [ ] Goal list displays all the user's goals with correct progress bars.
- [ ] Savings goal progress reflects the sum of logged contributions.
- [ ] Spending goal progress reflects actual category spending for the current month.
- [ ] Contributions can be added to savings goals with amount, date, and optional note.
- [ ] Editing a goal updates all editable fields correctly.
- [ ] Deleting a goal removes the goal and all associated contributions.
- [ ] Users cannot access or modify another user's goals.
- [ ] Unauthenticated users are redirected to login.
- [ ] New models are registered in the admin interface.
- [ ] `make check` passes.
