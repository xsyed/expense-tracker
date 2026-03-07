# Phase 4 — CSV Upload & Parsing Engine

## Overview
Deliver the CSV ingestion pipeline that converts raw bank/credit card export files into `Transaction` records stored against an expense month. The parser must handle four distinct CSV formats produced by different financial institutions, gracefully normalise dates and amounts, and surface clear feedback to the user about what was imported. This phase populates the transaction table that Phase 5 will make editable.

---

## Goals
- Accept one or more CSV files uploaded against a specific expense month.
- Automatically detect the CSV format and map columns to a standard internal structure.
- Parse and normalise all date and amount variations found across supported institutions.
- Persist each valid row as a `Transaction` record with type defaulting to `unassigned`.
- Record an audit log entry (`CSVUpload`) for every successful upload.
- Show the user a clear summary of what was imported and surface any rows that could not be parsed.

---

## Scope

### Data Models
#### Transaction
- Belongs to an `ExpenseMonth` (FK).
- Fields: `date`, `description`, `amount` (positive decimal, 10,2), `account` (optional), `transaction_type` (choices: `income` / `expense` / `unassigned`, default `unassigned`), `category` (FK → Category, nullable), `source_file` (CSV filename for traceability), `created_at`, `updated_at`.

#### CSVUpload (audit log)
- Belongs to an `ExpenseMonth` (FK).
- Fields: `filename`, `row_count` (number of successfully imported rows), `uploaded_at`.

### CSV Upload UI (on Expense Month Detail screen)
- File picker accepting `.csv` files.
- Upload button (standard form POST or HTMX-enhanced).
- After upload, a list of previously uploaded CSVs for this month is shown beneath the upload area, displaying filename, row count, and upload timestamp.

### Supported CSV Formats
The parser detects format automatically in the following priority order:

1. **Standard** — columns `Date`, `Description`, `Amount`, `Account`.
2. **AMEX** — columns `Transaction Date`, `Description`, `Amount`; account inferred from the filename.
3. **TD Bank** — columns `Transaction Date`, `Merchant`, `Amount`, `Account Type`.
4. **Generic (fallback)** — fuzzy, case-insensitive column matching when no named format is detected.

### Fuzzy Column Matching (Generic fallback)
The parser maps ambiguous column headers to internal fields:
- **Date** — matched from: `date`, `transaction date`, `trans date`.
- **Description** — matched from: `description`, `merchant`, `detail`, `memo`.
- **Amount** — matched from: `amount`, `transaction amount` (single column), or a pair of debit + credit columns (auto-combined into a single signed value).
- **Account** — matched from: `account`, `account type`, `account name`.

### Amount Normalisation
- Strip currency symbols (`$`, `€`, `£`).
- Strip thousands separators (`,`).
- Convert accounting-style parentheses — e.g. `(50.00)` → `-50.00`.
- Store the **absolute value** in `Transaction.amount`; sign information is not retained (type classification happens in Phase 5).

### Date Normalisation
All of the following input formats are recognised and parsed into a standard `YYYY-MM-DD` date:

| Format | Example |
|--------|---------|
| YYYY-MM-DD | 2026-02-14 |
| MM/DD/YYYY | 02/14/2026 |
| DD/MM/YYYY | 14/02/2026 |
| MM-DD-YYYY | 02-14-2026 |
| YYYY/MM/DD | 2026/02/14 |
| DD-MM-YYYY | 14-02-2026 |
| Month DD, YYYY | February 14, 2026 |
| Mon DD, YYYY | Feb 14, 2026 |
| YYYY-MM-DD HH:MM:SS | 2026-02-14 13:45:00 |
| pandas fallback | any remaining parseable format |

### Parser Output Contract
Each successfully parsed row produces a dict with keys: `date`, `description`, `amount`, `account`, `source_file`. Rows that cannot be parsed (missing required fields, unrecognisable date/amount) are collected as errors and reported to the user — they are not silently dropped.

### Post-Upload Behaviour
- All successfully parsed rows are appended as new `Transaction` records for the expense month (no deduplication — user responsibility).
- A `CSVUpload` audit record is written with the filename and imported row count.
- The expense month detail screen refreshes to show the new transactions in the table and the updated upload history list.
- The summary cards (Total Income, Total Expense, Net) recalculate to reflect the newly imported rows.

### Error Handling
- If the uploaded file is not a valid CSV or has no recognisable columns, the upload is rejected with a descriptive error message; no partial data is saved.
- Individual unparseable rows are reported in a warning block (e.g. "3 rows could not be imported — see details"); the remaining valid rows are still saved.

---

## Acceptance Criteria

| # | Criterion |
|---|-----------|
| 1 | The user can upload a CSV file from the expense month detail screen. |
| 2 | A **Standard** format CSV is correctly detected and all rows imported with the right date, description, amount, and account values. |
| 3 | An **AMEX** format CSV is correctly detected; account value is inferred from the filename when not present in the data. |
| 4 | A **TD Bank** format CSV is correctly detected and all rows imported correctly. |
| 5 | An unrecognised CSV with loosely-matching headers is parsed via the generic fallback and rows are imported. |
| 6 | A CSV with a debit column and a credit column has those two columns combined into a single signed amount per row. |
| 7 | All nine supported date formats are parsed correctly into `YYYY-MM-DD` dates without error. |
| 8 | Amount values with currency symbols, thousands separators, or accounting parentheses are normalised to positive decimal numbers. |
| 9 | Every imported transaction has `transaction_type = unassigned` and `category = null` after upload. |
| 10 | A `CSVUpload` record is created for every successful upload, recording the filename and the number of imported rows. |
| 11 | The upload history list on the expense month detail screen shows all previously uploaded files for that month. |
| 12 | Uploading multiple CSV files to the same month appends new transactions without removing existing ones. |
| 13 | Uploading a file that is not a valid CSV shows a clear error message and saves no data. |
| 14 | Rows that cannot be parsed are reported with a count and reason; the remaining valid rows are still saved. |
| 15 | The summary cards on the expense month detail screen reflect the newly imported transactions immediately after upload. |



IMPORTANT: READ this project. /Users/sami/Documents/simple-monthly-budget 

I do not want the LLM/AI calls or categories. This is for you to just understanding the parsing of csv files which will be uploaded nothing. You should just understand and handle edge cases for parsing csv files. No API calls for LLM or Merchant categorisation.