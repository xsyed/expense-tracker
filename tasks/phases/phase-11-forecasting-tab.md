# Phase 11: Forecasting Tab

## Description

Populate the **Forecasting tab** with predictive insights. Using a 3-month weighted moving average, the system predicts next month's spending per category and overall. This gives users a forward-looking view: *"Based on my recent habits, what should I expect to spend next month?"*

After a predicted month ends, the tab also shows how accurate the prediction was, building trust in the forecast over time.

---

## Requirements

### Prediction Logic

- Use a **3-month weighted moving average** per category (most recent month weighted highest).
- Compute a predicted amount per category and a total predicted amount.
- Assign a **confidence level** based on variance in the underlying data:
  - **High**: Low variance across the 3 months (consistent spending).
  - **Medium**: Moderate variance.
  - **Low**: High variance or fewer than 3 months of data.
- A JSON API endpoint returns the prediction results.

### Widget: Next Month Prediction Card

- A prominent card showing:
  - **Predicted total expenses** for next month.
  - **Confidence level** (High / Medium / Low) with a visual badge.
  - **Comparison to last month**: delta amount and percentage (e.g., "+$120 / +8% vs last month").

### Widget: Category Forecast Table

- Table with columns: Category, Predicted Amount, 3-Month Average, 6-Month Average, Trend (↑↓→).
- Sorted by predicted amount descending (biggest expected expenses first).
- Gives per-category visibility into the forecast.

### Widget: Forecast vs Actual (Historical Accuracy)

- For past months where a prediction could have been made (at least 3 prior months of data):
  - Show a chart or table comparing what was predicted vs. what was actually spent.
  - Display accuracy as a percentage (e.g., "92% accurate").
- This widget may have limited data initially (requires at least 4 months of history to show one comparison).
- If insufficient data exists, show a message indicating more history is needed.

### Edge Cases

- Categories with fewer than 3 months of history: use available data (1–2 months) with "Low" confidence.
- Categories with no recent spending: predicted as $0.
- A new user with no transaction history gets a friendly empty state.

---

## Acceptance Criteria

- [ ] The prediction card shows a predicted total for next month.
- [ ] Confidence level (High / Medium / Low) is displayed and reflects actual data variance.
- [ ] The delta vs. last month is shown with correct amount and percentage.
- [ ] The category forecast table lists every category with predicted, 3M avg, 6M avg, and trend.
- [ ] Predictions use a 3-month weighted moving average with correct weighting.
- [ ] Categories with fewer than 3 months of data show a "Low" confidence and still produce a prediction.
- [ ] The forecast vs. actual widget shows historical accuracy for past months (when enough data exists).
- [ ] When insufficient history exists for accuracy comparison, a helpful message is shown.
- [ ] A new user with no data sees a clean empty state.
- [ ] All data is scoped to the authenticated user.
- [ ] `make check` passes.
