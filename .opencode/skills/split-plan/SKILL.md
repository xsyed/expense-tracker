---
name: split-plan
description: "Split a large markdown plan into independent task files. Use when: breaking down a plan, splitting features into tasks, decomposing a roadmap, or creating task files from a plan document."
---

# Split Plan into Tasks

Take a large markdown plan file and split it into one file per feature/task in the `tasks/` directory.

## When to Use

- User has a markdown plan with multiple features or tasks
- User asks to break down, split, or decompose a plan into task files
- User wants independently executable task files from a larger document

## Procedure

1. Read the input plan file provided by the user
2. Identify each distinct feature or task in the plan
3. For each feature, create a separate file in `tasks/` named `<number>-<slug>.md`
4. Each task file must contain:
   - **Goal**: one-sentence description of the feature
   - **Description**: what needs to be built or changed
   - **Acceptance Criteria**: testable conditions (use a checklist)
   - **Dependencies**: which other task files must be completed first (or "None")
5. Verify no duplication across task files
6. Verify every item from the original plan is covered

## Rules

- Each task must be independently executable given its dependencies
- Max 200 lines per task file
- No duplication of requirements across files
- Every task file must have: clear goal, testable acceptance criteria, no ambiguity
- Use lowercase-kebab-case for file names