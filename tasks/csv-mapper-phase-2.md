# CSV Mapper — Phase 2: Templates

## Goal
Build the two templates that power the CSV mapper UI: the full-page mapper (`index.html`) and the HTMX result partial (`result.html`).

---

## Prerequisites
Phase 1 must be complete — the three backend views and URLs must exist before templates can be wired up and verified end-to-end.

---

## Files to Create

| File | Action |
|---|---|
| `templates/csv_mapper/index.html` | Create |
| `templates/csv_mapper/result.html` | Create |

---

## Implementation Plan

### 1. `templates/csv_mapper/index.html`

Extends `base.html`. Full-page layout with Bootstrap 5 cards.

---

#### Section A — Page header

- Heading: `CSV Mapper`
- Right-aligned link: `<a href="{% url 'csv_mapper_sample' %}">Download Sample CSV</a>` with a Bootstrap icon (`bi-download`).

---

#### Section B — Upload zone card

- Visible on page load; hidden via JS once a file is selected and the mapping panel is rendered.
- Contains a single `<input type="file" accept=".csv">` (no `name` attribute needed here — the real file input is inside the main form below).
- Triggers the JS `renderMappingUI()` on `change`.

**Note:** There is only one `<form>` on this page. The file input inside the upload card and the file input submitted with the form must be the same element, or the mapping panel must include the actual file input that will be submitted.

---

#### Section C — Mapping panel card

- Hidden on load; revealed by JS after a file is selected.
- Renders a two-column table:
  - **Left**: source CSV header name (read-only label).
  - **Center**: arrow icon `→`.
  - **Right**: Bootstrap `<select>` with options:
    - `— skip —` (value `""`, default)
    - `Date` (value `"date"`)
    - `Description` (value `"description"`)
    - `Amount` (value `"amount"`)
    - `Account` (value `"account"`) — optional
  - **Badge**: `Required` badge next to Date, Description, Amount rows after user has interacted (shown only when validation fires, not upfront).

**Behavior:**
- Each `<select>` change triggers `renderPreview()`.
- At most one column may be mapped to each target (e.g., two columns cannot both be set to "Date").

---

#### Section D — Live Preview table

- Below the mapping panel card.
- Hidden until at least one column is mapped.
- Shows the first 5 data rows from the uploaded CSV.
- Columns shown are only those that have been mapped (skipped columns are excluded).
- Updates on every `<select>` change — no server round-trip.

---

#### Section E — Action bar

Inside the main `<form>`:
- **Global account dropdown**: `<select name="account_id">` populated from `{{ accounts }}` context. First option: `— No account —` (empty value). Optional.
- Hidden inputs dynamically injected by JS before submit: `map_date`, `map_description`, `map_amount`, `map_account_col`.
- **Import button**: `hx-post="{% url 'csv_mapper' %}"`, `hx-target="#result-container"`, `hx-swap="innerHTML"`, `hx-encoding="multipart/form-data"`. Always type `submit`.
- **Download button**: standard `<button type="submit" formaction="{% url 'csv_mapper_download' %}">`. Bypasses HTMX.

---

#### Section F — Result container

```html
<div id="result-container"></div>
```

Empty on load. HTMX swaps the result partial here after import.

---

#### JavaScript (inline `<script>` at bottom of template)

Keep it minimal and readable. No external JS libraries beyond what `base.html` already loads.

**Events and functions:**

1. **`fileInput.addEventListener("change", onFileSelected)`**
   - Uses `FileReader.readAsText()` to read the file.
   - Calls `parseCSVHeaders(text)` → returns array of header strings.
   - Calls `parseCSVRows(text)` → returns first 5 data rows as arrays.
   - Calls `renderMappingUI(headers)`.
   - Hides the upload card.

2. **`parseCSVHeaders(text)`**
   - Splits on `\n`, takes row 0, splits on `,` (handle basic quoted commas).
   - Returns `string[]`.

3. **`parseCSVRows(text)`**
   - Returns rows 1–5 (up to 5) as `string[][]`.

4. **`renderMappingUI(headers)`**
   - Injects mapping rows into a `<tbody id="mapping-rows">`.
   - Each row: label cell + arrow cell + `<select data-header="{header}">`.
   - Shows the mapping panel card.

5. **`renderPreview()`**
   - Reads current dropdown values.
   - Builds a filtered column list (only mapped columns).
   - Injects `<thead>` and `<tbody>` into `<table id="preview-table">`.
   - Shows preview card if any column is mapped; hides if none.

6. **`onImportClick(event)`** — called on Import button `click` before HTMX fires.
   - Check that Date, Description, Amount each have a mapping selected.
   - If not: prevent default + show inline validation error message. **No server round-trip.**
   - If valid: inject hidden inputs (`map_date`, `map_description`, `map_amount`, `map_account_col`) into the form before HTMX submission.

---

### 2. `templates/csv_mapper/result.html`

HTMX partial — no `{% extends %}`, no `{% block %}`. Rendered inline inside `#result-container`.

**Layout:**

```
Bootstrap card (border-success for full success, border-warning if any skipped)

Card body:
  ✓ Imported {total_imported} transaction(s)

  [If months_summary not empty]
  Table:
    Month | Transactions | Status
    Mar 26 | 15 | (badge: existing)
    Jan 26 | 8  | (badge: ✨ new)

  [If skipped_future > 0]
  <p class="text-warning">Skipped {skipped_future} future-dated row(s).</p>

  [If skipped_errors > 0]
  <p class="text-danger">Skipped {skipped_errors} row(s) with parse errors.</p>

  [Import Another CSV] — <a href="{% url 'csv_mapper' %}"> button styled as btn-outline-secondary
```

---

## Acceptance Criteria

- [ ] `GET /csv-mapper/` renders the upload card, the mapping panel is hidden, and `#result-container` is empty.
- [ ] After selecting a CSV file, the mapping panel appears populated with the file's headers.
- [ ] After selecting a CSV file, the upload card is hidden.
- [ ] Changing a dropdown immediately updates the preview table (no page reload).
- [ ] The preview shows at most 5 rows and only mapped columns.
- [ ] Clicking Import without mapping Date, Description, or Amount shows an inline validation error and does not submit.
- [ ] The global account dropdown lists all of the logged-in user's accounts plus a "No account" option.
- [ ] Clicking Import with valid mappings fires an HTMX POST and swaps the result partial into `#result-container`.
- [ ] The result partial shows the correct `total_imported` count, per-month breakdown table, and skip counts.
- [ ] New months are visually distinguished from existing months in the breakdown table.
- [ ] "Import Another CSV" link in the result partial navigates back to `GET /csv-mapper/` cleanly.
- [ ] Clicking Download submits to `/csv-mapper/download/` (standard form POST, no HTMX).
- [ ] The sample CSV link points to `{% url 'csv_mapper_sample' %}` and triggers a download.
- [ ] The page is responsive and consistent with the existing Bootstrap 5 look and feel (matches `base.html` conventions).
- [ ] `make check` passes with no new errors.
