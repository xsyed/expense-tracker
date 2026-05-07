---
name: implement-feature
description: >-
  Implement a single feature from a task file end-to-end. Use when given a task
  file containing a goal, acceptance criteria, and constraints, or when asked to
  implement a feature following a structured plan-then-build workflow.
---

# Implement Feature

Read the task file. Follow these steps in order.

## Step 1 — Understand (no code yet)

- Restate the goal in one sentence
- List every acceptance criterion
- Identify constraints and dependencies
- If anything is ambiguous, ask before proceeding

Do NOT write code in this step.

## Step 2 — Plan

Break the work into a numbered list of atomic steps: files to change, functions to create, dependencies to add.

Each step must be independently executable. No large jumps.

## Step 3 — Implement

Execute one plan step at a time.

- Modify only relevant files
- Follow existing code patterns
- Do NOT refactor unrelated code
- Do NOT touch modules beyond what the task requires

## Step 4 — Validate

Check each acceptance criterion:

- PASS or FAIL with a one-line explanation
- If any FAIL: fix immediately, then re-validate

Run `make check`. Do not proceed until it passes.

## Step 5 — Test (if required)

Add or update tests only if acceptance criteria require them.

## Gotchas

- Never skip the planning step — even for small features
- Never assume missing requirements; ask instead
- Prefer the simplest solution that satisfies the criteria
- Do not add comments, docstrings, or type annotations to untouched code