# Task 1: Category Expense Type Classification

## Goal

Add an `expense_type` enum field to the Category model so categories can be classified as fixed, variable, or savings_transfer.

## Description

Add a `CharField` with choices `("fixed", "Fixed")`, `("variable", "Variable")`, `("savings_transfer", "Savings Transfer")` and `default="variable"` to the `Category` model. Create a migration (0014) with a data migration that sets defaults for seed categories. Expose the field in the category form and list UI.

### Model Change

- Field: `expense_type = CharField(max_length=17, choices=EXPENSE_TYPES, default="variable")`
- Add `EXPENSE_TYPES` choices list to `Category` class

### Migration `0014_category_expense_type.py`

Schema migration + `RunPython` data migration:
- "Housing & Utilities" → `fixed`
- "Debt Payment" → `fixed`
- "Savings & Investments" → `savings_transfer`
- All others stay `variable` (default)
- Exact name match only — users correct renamed categories manually

### Form Change

- Add `expense_type` to `CategoryForm.Meta.fields`
- Add Select widget with `class: form-select`

### Template Changes

**`templates/categories/list.html`** — Show expense_type badge next to each expense category:
- `fixed` → blue badge
- `variable` → secondary/gray badge
- `savings_transfer` → green badge
- Hidden for income categories (`{% if category.category_type == "expense" %}`)

**`templates/categories/edit.html`** — Show `expense_type` Select dropdown, hidden for income categories via template conditional.

## Acceptance Criteria

- [ ] `Category` model has `expense_type` field with 3 choices and default `"variable"`
- [ ] Migration `0014_category_expense_type.py` exists with schema + data migration
- [ ] Running `python manage.py migrate` applies cleanly
- [ ] "Housing & Utilities" and "Debt Payment" are `fixed`; "Savings & Investments" is `savings_transfer` after migration
- [ ] `CategoryForm` includes `expense_type` as a Select dropdown
- [ ] Category list page shows colored badge per expense category
- [ ] Income categories show no badge and no `expense_type` dropdown in edit form
- [ ] `make check` passes

## Files

- `core/models.py`
- `core/forms.py`
- `core/migrations/0014_category_expense_type.py`
- `templates/categories/list.html`
- `templates/categories/edit.html`

## Dependencies

None
