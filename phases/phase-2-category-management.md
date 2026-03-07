# Phase 2 — Category Management

## Overview
Introduce the `Category` model and deliver a full CRUD interface so users can view, create, rename, and delete their transaction categories. The system ships with **12 seeded default categories** that are pre-populated on the first run. By the end of this phase, categories are available as a reference list that later phases (transactions) will link to.

---

## Goals
- Persist a user-owned set of named categories in the database.
- Seed 12 meaningful default categories automatically on first run so the user starts with a useful foundation.
- Give the user a simple screen to manage (add / rename / remove) their categories.
- Ensure category names remain unique per user to avoid ambiguity in later dropdowns.

---

## Scope

### Data Model
- `Category` belongs to a `User` (FK).
- Fields: `name` (unique per user), `created_at`.
- A category can eventually be soft-deleted (or hard-deleted), but Phase 1 uses hard delete.

### Seeded Default Categories (12)
Automatically created once per new account (or on migrate for the single user):

1. Housing & Utilities
2. Transportation
3. Grocery
4. Food / Uber Eats
5. Money Transfers
6. Savings & Investments
7. Amazon / Online Shopping
8. Clothing & Grooming
9. Movies & Entertainment
10. Donations
11. Miscellaneous
12. Debt Payment

### Category List Screen (`/categories/`)
- Displays all categories belonging to the logged-in user in a table or card grid.
- Shows category name and action buttons (Edit, Delete) for each row.
- "Add Category" button / inline form at the top or bottom of the list.

### Create Category
- Single-field form: category name.
- Validated for uniqueness (per user) and non-empty value.
- Redirects back to the category list on success with a success flash message.

### Edit Category (`/categories/<id>/edit/`)
- Pre-filled form with the existing name.
- Updates the name; re-validates uniqueness excluding the current record.
- Redirects back to the list on success.

### Delete Category (`/categories/<id>/delete/`)
- Confirmation screen or modal before deletion.
- Hard-deletes the category.
- Redirects back to the list on success with a confirmation message.

### Navigation
- "Categories" link in the main navigation bar (from Phase 1 base template) is now active and routes to `/categories/`.

---

## Acceptance Criteria

| # | Criterion |
|---|-----------|
| 1 | After the first login (new account), all 12 default categories are present on the Categories screen without any manual action. |
| 2 | The user can view the full list of their categories at `/categories/`. |
| 3 | The user can add a new category with a unique name; it appears in the list immediately. |
| 4 | Attempting to create a category with a name that already exists shows a validation error; no duplicate is saved. |
| 5 | The user can edit an existing category name; the updated name is reflected everywhere the category is referenced. |
| 6 | Renaming a category to a name that already exists shows a validation error; the original name is preserved. |
| 7 | The user can delete a category; it is removed from the list and no longer available in dropdowns. |
| 8 | Deleting a category requires an explicit confirmation step (confirm screen or modal); accidental single-click does not delete. |
| 9 | All category operations (create, edit, delete) are scoped to the logged-in user — a user cannot see, edit, or delete another user's categories. |
| 10 | The Categories navigation link is visible in the top nav on all authenticated screens. |
