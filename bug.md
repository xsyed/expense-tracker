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

**Diagnostic:** Added `[DIAG]` console logs at every decision point. Logs confirmed the spurious `change` event fires in a macrotask that runs *after* `fetchBurnRateData` has already been called for the correct month — well after `updatingSelect` is `false` and `selectedBudgetMonth` is set to `2026-02`. The event carries `this.value: 2026-01`, bypassing both guards.

**Root cause:** Browser (Safari) form-state restoration. The browser remembers the `<select>`'s previous value across page visits and restores it asynchronously in a later macrotask. `autocomplete="off"` is supposed to suppress this but Safari ignores it for `<select>` elements. Because restoration fires in a full macrotask, no synchronous flag (`updatingSelect`) can remain set by the time it arrives.

**Attempted fix 1 (failed):** Added `mousedown`/`keydown` listeners to set a `userInitiatedChange` flag; `change` handler returned early if `false`. Failure mode: user opens dropdown (`mousedown` → flag `true`) then closes without selecting — flag stays `true`, so the next browser form-restore `change` slips through.

**Attempted fix 2 (failed):** Set `blockChangeAfterPopulate = true` before `innerHTML = ''`, cleared it via `setTimeout(fn, 0)`. Reasoning: the form-restore `change` macrotask is queued at `innerHTML = ''` and should fire before the `setTimeout` callback, so the flag would still be `true` when the spurious event arrives. In practice this also did not work — to be investigated.
