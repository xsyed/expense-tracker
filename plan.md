# Plan: django-expense-month PRD & Architecture

## Project Overview
Single-user personal expense tracker. The user creates "expense months", uploads one or more CSVs per month, manually classifies each transaction (income/expense/category), and views per-month summaries. Home/Dashboard will have chart widgets in a future phase.

**Stack:** Django 4.2 LTS · SQLite · Bootstrap 5 · django-crispy-forms (bootstrap5 pack) · HTMX (inline auto-save) · ApexCharts v5 (Phase 2) · Local deployment only

---

## Clarifications Captured
- **Single user** — personal app, one account
- **CSV formats** — 4 supported formats: standard, amex, td_bank, generic (fuzzy column matching). Debit/Credit split columns auto-combined into Amount. Multiple date and amount formats handled.
- **Income/Expense classification** — manual assignment per transaction after import (no auto-detection from CSV)
- **CSV duplicates** — no deduplication; user responsibility
- **All columns editable** — date, description, amount, account, type, category — all editable with auto-save
- **Default categories** — seeded with 12 categories (Housing & Utilities, Transportation, Grocery, Food/Uber Eats, Money Transfers, Savings & Investments, Amazon/Online Shopping, Clothing/Grooming, Movies/Entertainment, Donations, Miscellaneous, Debt Payment)
- **Dashboard charts (Phase 2)** — all 5: monthly income vs expense bar, category pie/donut, spending trend line, top categories, month-over-month comparison
- **Deployment** — local only

---

## Data Models

### User
- Django's built-in `auth.User`
- Login via email + password (set `USERNAME_FIELD = 'email'`)
- Custom `AbstractBaseUser` or just keep default + unique email constraint

### Category
- `id`, `name` (CharField, unique), `user` FK, `created_at`

### ExpenseMonth
- `id`, `label` (e.g., "February 2026"), `month` (DateField — day always 1, stores year/month), `user` FK, `created_at`
- Unique constraint: (user, month)

### Transaction
- `id`, `expense_month` FK, `date` (DateField), `description` (CharField), `amount` (DecimalField 10,2 — stored as positive value), `account` (CharField, nullable/blank), `transaction_type` (CharField choices: income/expense/unassigned, default unassigned), `category` (FK → Category, nullable/blank), `source_file` (CharField — CSV filename for traceability), `created_at`, `updated_at`

### CSVUpload (audit log)
- `id`, `expense_month` FK, `filename`, `row_count`, `uploaded_at`

---

## URL Structure
- `/` — Home/Dashboard (expense month list + future charts)
- `/months/` — Expense month list
- `/months/create/` — Create expense month
- `/months/<id>/` — Expense month detail (summary cards + editable table)
- `/months/<id>/edit/` — Edit month label
- `/months/<id>/delete/` — Delete month (+ all transactions)
- `/months/<id>/upload/` — CSV upload (POST, HTMX or form)
- `/months/<id>/transactions/<tx_id>/update/` — Inline update endpoint (HTMX POST, returns updated row)
- `/categories/` — Category list + create
- `/categories/<id>/edit/` — Edit category
- `/categories/<id>/delete/` — Delete category
- `/auth/login/`, `/auth/signup/`, `/auth/logout/`

---

## Screens

### 1. Home / Dashboard
- Header: app name + nav
- Grid of "Expense Month" cards — each shows: label, total income, total expense, net, date range of transactions
- "New Month" button
- **Phase 2 placeholder section** for ApexCharts widgets (5 charts planned)

### 2. Expense Month Detail
- **Summary cards row** (top): Total Income, Total Expense, Net Balance
- **Upload CSV area**: file picker, upload button, shows list of uploaded CSVs for this month
- **Transaction table** (Bootstrap table, editable):
  - Columns: Date | Description | Amount | Account | Type (dropdown: income/expense/unassigned) | Category (dropdown) | Actions (delete row)
  - Every cell editable inline — HTMX `hx-trigger="change"` or `hx-trigger="blur"` posts to update endpoint
  - Category dropdown populated from Category model

### 3. Categories
- List of categories (table or card grid)
- Inline add / edit / delete
- Pre-seeded 12 default categories on first run (via data migration or `post_migrate` signal)

### 4. Auth
- Signup: email + password + confirm password (crispy form)
- Login: email + password (crispy form)
- No email confirmation, no 2FA, no password reset (Phase 2 if needed)
- Redirect to Home after login

---

## CSV Parser Module (`core/csv_parser.py`)

### Supported Formats (detection order)
1. **standard** — Date, Description, Amount, Account
2. **amex** — Transaction Date, Description, Amount (account inferred from filename)
3. **td_bank** — Transaction Date, Merchant, Amount, Account Type
4. **generic** — fuzzy case-insensitive column matching (fallback)

### Fuzzy Column Mapping
- Date → `date`, `transaction date`, `trans date`
- Description → `description`, `merchant`, `detail`, `memo`
- Amount → `amount`, `transaction amount` (single col), OR debit + credit (auto-combined)
- Account → `account`, `account type`, `account name`

### Amount Normalization
- Strip currency symbols ($, €, £)
- Strip thousands separators (,)
- Accounting parentheses `(50.00)` → -50.00
- Store absolute value in `Transaction.amount`; type stays `unassigned`

### Date Parsing (multiple formats)
YYYY-MM-DD, MM/DD/YYYY, DD/MM/YYYY, MM-DD-YYYY, YYYY/MM/DD, DD-MM-YYYY, "Month DD, YYYY", "Mon DD, YYYY", YYYY-MM-DD HH:MM:SS, pandas fallback

### Parser Output
Returns list of dicts: `{date, description, amount, account, source_file}`

---

## High-Level Architecture

```
Browser
  Bootstrap 5 templates
  HTMX (inline cell editing auto-save, CSV upload feedback)
  ApexCharts v5 (Phase 2 dashboard widgets)
        │
        │ HTTP / HTMX partial responses
        ▼
Django 4.2 LTS
  Views: CBVs (list/create/delete) + function views (upload, inline update)
  django-crispy-forms + crispy-bootstrap5 pack
  core/csv_parser.py
  Django ORM
        │
        ▼
SQLite (dev + prod — local only)
```

### Django App Structure
```
expense_tracker/          ← project
├── manage.py
├── expense_tracker/      ← project settings package
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── core/                 ← single main app
│   ├── models.py         ← User, Category, ExpenseMonth, Transaction, CSVUpload
│   ├── views.py          ← all views
│   ├── urls.py
│   ├── forms.py          ← crispy forms
│   ├── csv_parser.py     ← multi-format parser
│   └── migrations/
├── templates/
│   ├── base.html         ← Bootstrap 5 navbar, blocks
│   ├── dashboard/
│   │   └── home.html
│   ├── months/
│   │   ├── list.html
│   │   ├── detail.html   ← main table view
│   │   ├── form.html     ← create/edit
│   │   └── partials/
│   │       └── transaction_row.html   ← HTMX swap target
│   ├── categories/
│   │   └── list.html
│   └── registration/
│       ├── login.html
│       └── signup.html
└── static/
    └── vendor/
        ├── htmx.min.js
        └── apexcharts.min.js
```

---

## Inline Editing Strategy (HTMX)
- Each `<tr>` has `hx-target="this"` and `hx-swap="outerHTML"` targeting the row
- Each editable cell uses `contenteditable` or `<input>`/`<select>` with `hx-post` + `hx-trigger="change"` (for dropdowns) or `hx-trigger="blur"` (for text/date/amount inputs)
- Server returns the refreshed `<tr>` partial (`transaction_row.html`)
- Summary cards (Income/Expense totals) can optionally update via a separate HTMX out-of-band swap (`hx-swap-oob`)

---

## Phase 2 — Dashboard Charts (ApexCharts v5)
Planned widgets (not in initial scope):
1. Monthly income vs expense — grouped bar chart
2. Category breakdown — donut/pie chart (per selected month)
3. Spending trend — line chart over rolling 6 months
4. Top spending categories — horizontal bar or treemap
5. Month-over-month comparison — stacked bar

---

## Scope Boundaries
**In scope (Phase 1):**
- Auth (login, signup, logout)
- ExpenseMonth CRUD
- CSV upload (multi-format parser, append behavior)
- Editable transaction table with auto-save (HTMX)
- Category CRUD + seeded defaults
- Per-month income/expense summary cards
- Home screen with expense month cards

**Out of scope / Phase 2:**
- Dashboard charts
- Password reset / email confirmation / 2FA
- Multi-currency
- CSV deduplication
- Export (PDF/CSV)
- Mobile-optimized table layout
