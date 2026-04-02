# Task 3: Savings Planner Frontend Page

## Goal

Build the savings planner interactive page with summary cards, charts, client-side simulator, and category cut analysis.

## Description

Create `templates/savings_planner/index.html` extending `base.html`. Add a nav link to `base.html`. All data loaded via `fetch()` to the overview API endpoint (from Task 2). Simulation logic runs entirely in client-side JS.

### Navbar

Add "Savings Planner" to `templates/base.html` navbar as a top-level item between Insights and Goals. Icon: `bi-piggy-bank`. Active state: `{% if '/savings-planner/' in request.path %}`.

### Section 1: Summary Cards

4 cards in a `col-md-6 col-lg-3` grid row:
1. **Avg Monthly Income** — `avg_income` formatted as currency
2. **Avg Fixed Expenses** — `avg_fixed_expense` formatted as currency
3. **Avg Variable Expenses** — `avg_variable_expense` formatted as currency
4. **Savings Rate** — `savings_rate` as percentage, subtitle: "$X explicit transfers + $Y unallocated" from `savings_breakdown`

Time range selector: 3 Bootstrap button group buttons (3M / **6M** default / 12M). On click, re-fetch overview API with `?months=N` and re-render all sections.

### Section 2: Charts (two columns, `col-lg-6` each)

**Left: Category Expense Donut** (ApexCharts)
- Series: one slice per expense category from `category_stats`
- Labels: category names
- Values: `avg_spend`
- Type: `donut`

**Right: Monthly Stacked Area Chart** (ApexCharts)
- X-axis: `months` array
- 4 stacked area series: `fixed`, `variable`, `savings_transfer`, `savings` (unallocated) from `monthly`
- Colors: fixed=blue, variable=orange, savings_transfer=green, unallocated=emerald/teal
- Type: `area` with `stacked: true`

### Section 3: Savings Simulator (client-side only)

- Range slider (`<input type="range">`) + number input synced together
- Min: 0, Max: `avg_income` (from loaded data), Step: 50
- Default value: current savings amount (`avg_income - avg_fixed - avg_variable`)

**JS simulation logic** (runs on input change, no API call):
```
cut_needed = (avg_fixed + avg_variable) - (avg_income - target)
total_cut_potential = sum of all category cut_potentials
```

Feasibility tiers:
- `on_track` (green): `cut_needed <= 0`
- `achievable` (yellow): `cut_needed > 0 && cut_needed <= total_cut_potential`
- `aggressive` (orange): `cut_needed > total_cut_potential && cut_needed < avg_variable`
- `impossible` (red): `cut_needed >= avg_variable`

Per-category suggested cuts (variable categories only):
- If `total_cut_potential > 0`: `suggested_cut = (category.cut_potential / total_cut_potential) * cut_needed`
- Cap each `suggested_cut` at `category.cut_potential`
- `new_target = category.avg_spend - suggested_cut`

Result display: 2 cards showing "Cut Needed: $X" and feasibility badge (color-coded).

### Section 4: Category Cut Analysis

**Table** (Bootstrap table, no ag-grid):
- Rows: variable expense categories sorted by `cut_potential` descending
- Columns: Category | Avg Spend | Historical Min | Cut Potential | Suggested Cut
- Suggested Cut column updates dynamically from simulator
- Currency formatting via JS `Intl.NumberFormat`

**Horizontal bar chart** (ApexCharts):
- Categories on Y-axis, `cut_potential` on X-axis
- Variable categories only, sorted by cut_potential descending

### Section 5: Warnings & Empty States

- **Unassigned warning** (Bootstrap alert-warning): "X transactions are unclassified and excluded from this analysis." Shown when `unassigned_count > 0`.
- **No transactions** (centered card): "No transaction data found. Upload a CSV or create a month to get started." Links to `/months/create/`.
- **< 2 months** (Bootstrap alert-info): "Analysis works best with 2+ months of data. Results based on N month." Shown when `months.length < 2`.

### ApexCharts

Load via CDN (same as insights page). Use ApexCharts v5 consistent with existing templates.

## Acceptance Criteria

- [ ] `templates/savings_planner/index.html` exists and extends `base.html`
- [ ] "Savings Planner" nav link appears between Insights and Goals in navbar
- [ ] Nav link shows active state on `/savings-planner/` pages
- [ ] 4 summary cards render with correct data from API
- [ ] Time range buttons (3M/6M/12M) re-fetch and re-render all sections
- [ ] Category donut chart renders with one slice per expense category
- [ ] Stacked area chart renders 4 series (fixed, variable, savings_transfer, savings)
- [ ] Savings simulator slider updates results instantly (no network call)
- [ ] Feasibility badge shows correct color for each tier
- [ ] Category cut table updates suggested cuts on slider change
- [ ] Horizontal bar chart shows cut potential per variable category
- [ ] Unassigned transactions warning shows when count > 0
- [ ] Empty state shown when no transactions exist
- [ ] Low-data warning shown when < 2 months of data
- [ ] Savings rate card shows explicit transfers + unallocated subtitle
- [ ] Currency formatting uses `Intl.NumberFormat`
- [ ] `make check` passes

## Files

- `templates/savings_planner/index.html` (new)
- `templates/base.html` (edit — add nav link)

## Dependencies

- Task 2 (API endpoint must exist and return correct data)
