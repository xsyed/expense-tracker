# Phase 2: Insights Page Skeleton & Navbar Link

## Description

Create the main **Insights page** — a single page with a tabbed layout that will house all analytical widgets across future phases. This phase sets up the shell: the page structure, the tab navigation, and the navbar link so users can reach it.

The page uses Bootstrap tabs for client-side tab switching (no page reloads). Initially, only the Budget tab will have real content (added in Phase 3). All other tabs show a placeholder message indicating they are coming soon.

The Insights link is added to the main navigation bar so it's always accessible.

---

## Requirements

- A new page at `/insights/` accessible only to authenticated users.
- The page has 6 tabs: **Budgets**, **Goals**, **Recurring Expenses**, **Category Trends**, **Accounts Overview**, **Forecasting**.
- Tabs switch content client-side using Bootstrap's tab component (no server round-trips).
- The first tab (Budgets) is active by default on page load.
- Tabs other than Budgets display a simple "Coming soon" placeholder.
- A new "Insights" link appears in the main navbar, positioned logically among existing links.
- The page extends the base template and follows the same layout conventions as existing pages.

---

## Acceptance Criteria

- [ ] Navigating to `/insights/` loads the tabbed page.
- [ ] All 6 tabs are visible and clickable; switching tabs shows the correct content panel.
- [ ] The Budgets tab is selected by default.
- [ ] Non-Budget tabs show a placeholder message.
- [ ] The "Insights" link is visible in the navbar and navigates to `/insights/`.
- [ ] Unauthenticated users are redirected to login.
- [ ] `make check` passes.
