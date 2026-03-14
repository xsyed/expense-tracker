# Bug: Insights widgets show stale/wrong month data

**Symptom:** Switching months fetches correct data but displays previous month's values. Widgets appear "cached."

**Root cause:** `populateMonthSelect()` rebuilt the `<select>` on every fetch response. Clearing `innerHTML` caused browsers to fire spurious `change` events mid-rebuild, triggering cascading fetches that corrupted the version counter and skipped/overwrote rendering.

**Fix (3 changes in `templates/insights/index.html`):**
1. Added `updatingSelect` flag — change listener returns early when `true`, preventing programmatic DOM mutations from triggering fetches.
2. Populate select only once (initial load, `options.length === 0`) — subsequent fetches skip rebuild.
3. Guard in change listener: `if (updatingSelect) return;` as safety net.

**What was actually implemented:**
4. Added `selectedBudgetMonth` to track the month currently represented by the rendered widgets.
5. Added `syncMonthSelect(selectedMonth)` to align the `<select>` value with the month returned by the latest accepted response without triggering another fetch.
6. Ignored duplicate `change` events with `if (this.value === selectedBudgetMonth) return;`, which stops delayed browser events from re-requesting the current month and overwriting the previous-month render.

---

## Second occurrence (March 2026)

**Symptom:** Page loads correctly for the default month (`2026-02`), then immediately re-fetches and renders `2026-01` (the previously visited month) without any user action.

**Diagnostic:** Added `[DIAG]` console logs at every decision point. Logs confirmed the spurious `change` event fires in a macrotask that runs *after* `fetchBurnRateData` has already been called for the correct month — well after `updatingSelect` is `false` and `selectedBudgetMonth` is set to `2026-02`. The event carries `this.value: 2026-01`, bypassing both guards. Reproduced on Chrome.

**Root cause:** Browser (Chrome) form-state restoration. The browser remembers the `<select>`'s previous value across page visits and restores it asynchronously in a later macrotask. `autocomplete="off"` is supposed to suppress this but Chrome ignores it for `<select>` elements. Because restoration fires in a full macrotask, no synchronous flag (`updatingSelect`) can remain set by the time it arrives.

**Attempted fix 1 (failed):** Added `mousedown`/`keydown` listeners to set a `userInitiatedChange` flag; `change` handler returned early if `false`. Failure mode: user opens dropdown (`mousedown` → flag `true`) then closes without selecting — flag stays `true`, so the next browser form-restore `change` slips through.

**Attempted fix 2 (failed):** Set `blockChangeAfterPopulate = true` before `innerHTML = ''`, cleared it via `setTimeout(fn, 0)`. Reasoning: the form-restore `change` macrotask is queued at `innerHTML = ''` and should fire before the `setTimeout` callback, so the flag would still be `true` when the spurious event arrives. In practice this also did not work — to be investigated.

**Fix (working):** Root cause was Chrome's asynchronous form-state restoration firing a `change` event with the previously visited month value in a macrotask that arrives after all synchronous guards have cleared. The fix combined two changes:

1. **Select population guard** — `populateMonthSelect()` only builds options once (when `options.length === 0`). Subsequent responses skip the rebuild entirely, eliminating the DOM mutation that triggers Chrome's form-state restoration.
2. **`selectedBudgetMonth` duplicate guard** — The `change` listener checks `if (this.value === selectedBudgetMonth) return;`, dropping any stale restoration event that matches the already-rendered month.
3. **Charts use `updateOptions()` instead of destroy+recreate** — All 6 ApexCharts instances (budget bar, health donut, burn rate, goals timeline, projection, spending trend) now call `chart.updateOptions(options)` when the chart already exists, only calling `new ApexCharts().render()` on first render. This is ApexCharts' recommended approach for dynamic data updates, avoids DOM thrashing, and eliminates any chart-related timing side effects.
