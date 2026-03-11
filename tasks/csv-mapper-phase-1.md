# CSV Mapper — Phase 1: Backend

## Goal
Implement all server-side logic for the CSV mapper feature: three views, shared parsing helper, and URL registration.

---

## Files to Create / Modify

| File | Action |
|---|---|
| `core/views_csv_mapper.py` | Create |
| `expense_month/urls.py` | Modify — add 3 routes |

---

## Implementation Plan

### 1. Shared helper `_apply_mapping`

Module-level private function in `core/views_csv_mapper.py`.

**Signature:**
```python
def _apply_mapping(
    file: IO[bytes],
    mapping: dict[str, str],
) -> list[dict[str, str | Decimal | None]]:
```

**Responsibilities:**
- Open and decode the uploaded file as UTF-8 (with BOM fallback).
- Parse CSV rows using `csv.DictReader`.
- For each row:
  - Extract date string from `mapping["date_col"]` → parse with `CSVParser._parse_date`.
  - Extract description string from `mapping["desc_col"]`.
  - Extract amount string from `mapping["amount_col"]` → parse with `CSVParser._parse_amount`, then apply `abs()`.
  - Optionally extract account string from `mapping.get("account_col")`.
- Return a list of dicts with normalized keys: `date`, `description`, `amount`, `account_from_col`.
- Rows where date or amount fail to parse should be included with a `parse_error: True` flag (not silently dropped — the caller tracks counts).

**Notes:**
- Reuse `CSVParser._parse_date` and `CSVParser._parse_amount` from `core/csv_parser.py`. Import them directly.
- Do not catch exceptions broadly; let the caller decide how to handle the flag.

---

### 2. `csv_mapper_view(request)` — GET + POST (HTMX import)

**GET:**
- Require login (`@login_required`).
- Render `csv_mapper/index.html`.
- Context: `accounts` — `Account.objects.filter(user=request.user).order_by("name")`.

**POST (HTMX import):**
- Required form fields: `csv_file` (file), `map_date`, `map_description`, `map_amount` (column name strings).
- Optional fields: `map_account_col` (source column name), `account_id` (global account PK).
- Build `mapping` dict and call `_apply_mapping`.
- Iterate normalized rows:
  - Skip rows with `parse_error=True` → increment `skipped_errors`.
  - Skip rows where `date > today` → increment `skipped_future`.
  - Group remaining rows by `(date.year, date.month)`.
- For each `(year, month)` group:
  - `ExpenseMonth.objects.get_or_create(user=request.user, month=date(year, month, 1), defaults={"label": date(year, month, 1).strftime("%b %y")})`.
  - Track whether the month was created (new) or already existed.
  - Bulk-create `Transaction` objects: `type="expense"`, `category=None`, `account` from `account_id` if provided.
- Return `render(request, "csv_mapper/result.html", context)`.

**Context for result template:**
```python
{
    "total_imported": int,
    "skipped_future": int,
    "skipped_errors": int,
    "months_summary": [
        {"month": ExpenseMonth, "count": int, "is_new": bool},
        ...
    ],
}
```

---

### 3. `csv_mapper_download_view(request)` — POST only

- Require login + POST method guard.
- Same parse + mapping flow as the import view (call `_apply_mapping`).
- Build an `HttpResponse` with `Content-Type: text/csv`.
- Set `Content-Disposition: attachment; filename="mapped_transactions.csv"`.
- Write rows with `csv.writer`:
  - Columns: `Date`, `Description`, `Amount` — always.
  - Add `Account` column only if `account_id` was provided in POST.
  - Date formatted as `YYYY-MM-DD`.
  - Amounts are always positive (already enforced by `_apply_mapping`).
- Skip rows with `parse_error=True` or future dates (same rules as import).

---

### 4. `csv_mapper_sample_view(request)` — GET only

- Require login.
- Return `HttpResponse` with hardcoded CSV content:
  ```
  Date,Description,Amount
  2026-03-01,Coffee Shop,4.50
  2026-03-02,Grocery Store,82.30
  2026-03-05,Phone Bill,45.00
  ```
- Headers: `Content-Type: text/csv`, `Content-Disposition: attachment; filename="sample.csv"`.

---

### 5. URL registration in `expense_month/urls.py`

Add three routes under the existing URL patterns:

```python
path("csv-mapper/", csv_mapper_view, name="csv_mapper"),
path("csv-mapper/download/", csv_mapper_download_view, name="csv_mapper_download"),
path("csv-mapper/sample.csv", csv_mapper_sample_view, name="csv_mapper_sample"),
```

---

## Acceptance Criteria

- [ ] `GET /csv-mapper/` returns 200 for a logged-in user with accounts context populated.
- [ ] `GET /csv-mapper/` redirects to login for an anonymous user.
- [ ] `POST /csv-mapper/` with a valid CSV and full mapping returns a 200 response containing the result partial (no redirect).
- [ ] `total_imported` count matches the number of non-skipped, non-future rows in the uploaded file.
- [ ] Rows with an unparseable date or amount are counted in `skipped_errors` and not persisted.
- [ ] Rows with a date after today (2026-03-10) are counted in `skipped_future` and not persisted.
- [ ] A transaction row dated 2026-02-15 saves with `type="expense"` and `category=None`.
- [ ] Importing into a month that does not yet exist creates a new `ExpenseMonth` with label `"Feb 26"`.
- [ ] Importing into a month that already exists reuses it — no duplicate `ExpenseMonth`.
- [ ] `months_summary` correctly marks each month entry as `is_new=True/False`.
- [ ] `POST /csv-mapper/download/` streams a valid CSV attachment — no DB writes occur.
- [ ] Download CSV includes `Account` column only when `account_id` is provided.
- [ ] `GET /csv-mapper/sample.csv` returns a downloadable CSV with the three hardcoded rows.
- [ ] All amounts in downloaded and imported rows are positive (`abs()` applied).
- [ ] `make check` passes with no new errors.
