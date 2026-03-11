# CSV Mapper — Phase 3: Entry Point & End-to-End Verification

## Goal
Wire the CSV Mapper into the existing app with an entry-point link on the month detail page, then verify the complete user flow end-to-end.

---

## Prerequisites
Phase 1 and Phase 2 must be complete — all views, URLs, and templates must exist.

---

## Files to Modify

| File | Action |
|---|---|
| `templates/months/detail.html` | Add entry-point link below upload card |
| `vulture_whitelist.py` | Add new view names if vulture flags them as unused |

---

## Implementation Plan

### 1. Entry-point link in `templates/months/detail.html`

Locate the closing `</form>` tag of the existing CSV upload form (around line 104).

Immediately after it, add:

```html
<div class="mt-2 text-center">
  <a href="{% url 'csv_mapper' %}" class="small text-muted">
    <i class="bi bi-arrow-left-right me-1"></i>Map &amp; import any CSV format
  </a>
</div>
```

**Rules:**
- Do not modify the upload form itself.
- Do not change any surrounding layout.
- This is the only change to `months/detail.html`.

---

### 2. `vulture_whitelist.py` update (if needed)

After running `make check`, if vulture reports any of the three new view functions as unused code, add them to `vulture_whitelist.py` using the existing whitelist pattern in that file.

Only make this change if vulture actually flags something — do not pre-emptively add entries.

---

### 3. End-to-end verification checklist

Work through the full user flow manually (or via Django test runner) before marking phase complete:

**Navigation:**
- [ ] Month detail page shows the "Map & import any CSV format" link.
- [ ] Clicking the link navigates to `GET /csv-mapper/` without errors.

**Happy path — import:**
- [ ] Upload a CSV with columns in a non-standard order (e.g., Amount, Date, Description).
- [ ] Mapping panel renders with correct headers.
- [ ] Map all three required fields; preview updates correctly.
- [ ] Assign an account from the global dropdown.
- [ ] Click Import — result partial appears with correct counts and month breakdown.
- [ ] Navigate to the affected month's detail page — transactions are present with correct data.
- [ ] Imported transactions have `type="expense"` and `category=None`.

**Edge cases — import:**
- [ ] CSV with a future-dated row (after 2026-03-10): row skipped, count shown in result.
- [ ] CSV with an unparseable amount (e.g., `"N/A"`): row skipped, error count shown.
- [ ] CSV targeting a month that already exists: no duplicate `ExpenseMonth` created.
- [ ] CSV targeting a new month: `ExpenseMonth` created with label formatted as `"MMM YY"` (e.g., `"Jan 26"`).
- [ ] Importing without selecting an account: transactions saved with `account=None`.

**Validation:**
- [ ] Clicking Import without mapping Date → inline error, no POST sent.
- [ ] Clicking Import without mapping Description → inline error, no POST sent.
- [ ] Clicking Import without mapping Amount → inline error, no POST sent.

**Download:**
- [ ] POST to `/csv-mapper/download/` returns a `.csv` file attachment.
- [ ] All amounts in the downloaded file are positive.
- [ ] Account column is present in download only when `account_id` was provided.

**Sample CSV:**
- [ ] `GET /csv-mapper/sample.csv` downloads a file with three rows and headers `Date,Description,Amount`.

**Quality gate:**
- [ ] `make check` passes with zero errors or warnings introduced by this feature.

---

## Acceptance Criteria

- [ ] The entry-point link appears on `months/detail.html` and navigates to the CSV mapper.
- [ ] The full import flow works end-to-end: upload → map → import → transactions visible in the month detail grid.
- [ ] The download flow works end-to-end: upload → map → download → valid CSV file.
- [ ] All edge cases (future dates, parse errors, existing vs. new months, missing account) behave correctly.
- [ ] Client-side validation blocks import submission when required mappings are missing.
- [ ] `vulture_whitelist.py` is updated only if and only if vulture flags the new views.
- [ ] `make check` passes cleanly — no regressions to existing functionality.
