# Personal Finance Copilot

This context describes the AI-assisted finance feature for the expense tracker. It exists to keep advice boundaries, memory, and financial data language precise.

## Language

**Personal Finance Copilot**:
An AI assistant that analyzes the user's expense-tracker data and answers personal budgeting and cash-flow questions.
_Avoid_: Financial Advisor, Financial Expert

**Cash-Flow Recommendation**:
A direct yes/no budgeting recommendation backed by visible math, confidence, assumptions, and missing-data warnings.
_Avoid_: Financial advice, investment advice

**High-Impact Finance Question**:
A question where a wrong answer could materially affect cash reserves, debt, housing, family planning, lending, or job-loss runway.
_Avoid_: Casual question

**Financial Records**:
The user's stored transactions, categories, budgets, goals, accounts, and goal contributions.
_Avoid_: Memory, profile

**Advisor Memory**:
Stable personal context that helps interpret financial questions but is not itself a financial record.
_Avoid_: Financial data, transaction memory

**Memory Suggestion**:
A proposed change to advisor memory that is inactive until the user accepts or edits it.
_Avoid_: Automatic memory update

**Current Available Cash**:
A point-in-time amount the user provides when stored records are insufficient to answer an affordability question.
_Avoid_: Account balance, stored balance

**Financial Summary**:
A compact computed view of financial records prepared for one advisor question.
_Avoid_: Raw transaction dump, full context load

**Advisor Calculation**:
A tested deterministic calculation available to the copilot through an internal tool.
_Avoid_: Model-written code, arbitrary code execution

**Follow-Up Gate**:
A required pause where the copilot asks for missing facts before answering a high-impact finance question.
_Avoid_: Guess, provisional advice

**External Reference**:
Third-party webpage, article, or PDF content supplied to inform an advisor answer.
_Avoid_: Personal financial record

**Advisor Conversation**:
A user-visible thread of messages with the Personal Finance Copilot.
_Avoid_: Chat log

**Advisor Pill**:
The floating chat entry point available across authenticated pages.
_Avoid_: Dedicated advisor page

**Conversation Summary**:
A compact representation of prior advisor conversation used for model context.
_Avoid_: Full history prompt

**Provider Context**:
The approved memory, conversation text, and financial summaries sent to an external model provider.
_Avoid_: Full financial record export

**Advisor Run**:
A single background attempt to answer one user message inside an advisor conversation.
_Avoid_: Page request, browser stream

## Relationships

- A **Personal Finance Copilot** may use **Financial Records** to produce a **Cash-Flow Recommendation**
- A **High-Impact Finance Question** requires a **Follow-Up Gate** when missing facts could change the recommendation
- A **Cash-Flow Recommendation** must disclose when **Current Available Cash** is required but unknown
- **Advisor Memory** may inform a recommendation, but must not duplicate **Financial Records**
- A **Memory Suggestion** may become **Advisor Memory** only after user confirmation
- **Current Available Cash** may be requested from the user because accounts do not currently store true balances
- A **Personal Finance Copilot** should prefer **Financial Summary** data over broad raw **Financial Records**
- A **Personal Finance Copilot** may use **Advisor Calculation** tools but must not execute model-written code in phase 1
- A **Personal Finance Copilot** may use current currency rates before it supports broader **External References**
- An **Advisor Pill** is the primary phase-1 interface for **Advisor Conversations**
- An **Advisor Conversation** contains one or more **Advisor Runs**
- An **Advisor Conversation** stores full user-visible history, while **Conversation Summary** limits what is sent to the model
- **Provider Context** must be minimized to the current question, approved memory, compact conversation context, and needed financial summaries
- An **Advisor Run** continues independently of the browser page that created it

## Example Dialogue

> **Dev:** "Can the copilot say 'no, do not buy this car'?"
> **Domain expert:** "Yes, for a cash-flow decision, but it must show the math and say when current available cash is missing."
> **Dev:** "What if current available cash is missing?"
> **Domain expert:** "For a high-impact question, ask first unless the missing fact cannot materially change the answer."

## Flagged Ambiguities

- "Financial Advisor" sounds regulated and overly broad. Resolved: use **Personal Finance Copilot** for this feature.
- "Memory" could mean stored financial facts or personal preferences. Resolved: **Advisor Memory** stores stable personal context, not **Financial Records**.
- "Update memory" could mean silent AI writes. Resolved: the copilot creates **Memory Suggestions**; the user confirms, edits, or rejects them.
- "API/MCP tools" could mean exposing every financial query as an external interface. Resolved: start with compact **Financial Summary** tools inside the app; add external MCP only if another client needs it.
- "Write its own code" is too broad for a critical finance feature. Resolved: phase 1 uses tested **Advisor Calculation** tools only.
- "Streaming response" could mean the page owns the model request. Resolved: an **Advisor Run** owns answer generation; pages display saved run state.
- "Web/PDF reading" is not the same as current exchange rates. Resolved: broad **External References** are later-phase; currency rates are allowed early.
