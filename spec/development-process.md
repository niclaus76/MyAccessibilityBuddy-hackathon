# Structured Development Process (VS Code + GitHub)

## Purpose
Define a lightweight, disciplined development process that:
- Works with VS Code and GitHub only
- Integrates naturally with GitHub Issues and Pull Requests
- Keeps work visible and traceable
- Embeds quality and accessibility by design
- Scales from solo work to small teams

Clarity over ceremony. Discipline over tools.

---

## Core Principles
1. No work without an issue
2. One issue equals one outcome
3. Every change goes through a Pull Request
4. Accessibility and testing are part of “done”, not optional
5. Decisions are documented, not remembered

---

## Development Control Folder

Add a top-level folder used as the project control layer:

/development
├── 01-backlog
├── 02-in-progress
├── 03-bugs
├── 04-testing
├── 05-decisions
├── 06-release

yaml
Copy code

This folder does not contain code.  
It contains thinking, rules, and traceability.

---

## Mental Model (Simple and Explicit)

All work must fit into one of four states:

| State | Meaning |
|-----|--------|
| Backlog | Ideas, features, technical debt |
| In progress | Currently being worked on |
| Broken | Known bugs or regressions |
| Done | Released and documented |

If a task cannot be placed in one state, it is not clearly defined.

---

## Backlog Rules

The backlog contains:
- Feature ideas
- Technical debt
- Known improvements

Backlog items are refined into GitHub Issues before development starts.

---

## GitHub Issues

GitHub Issues are the unit of execution.

Rules:
- No issue, no code
- One issue per problem or feature
- Issues must be small enough to be completed in one Pull Request

### Required issue structure
Why
Expected behavior
Acceptance criteria
yaml
Copy code

### Standard labels
- feature
- bug
- tech-debt
- accessibility
- decision
- test-missing

---

## Branching Strategy

Simple and strict.

Branch naming:
feature/short-description
bug/short-description
chore/short-description

yaml
Copy code

Rules:
- One branch per issue
- Branches are deleted after merge
- `main` is always deployable

---

## Pull Requests as Quality Gates

All changes are merged via Pull Request.

Each Pull Request must:
- Reference the related issue
- Explain what changed and why
- Describe how to test the change
- Explicitly state accessibility impact

Pull Requests are not optional.  
They are the main quality control mechanism.

---

## Testing and Accessibility

Testing is documented, even when minimal.

Expectations:
- Functional behavior is described
- Regressions are tracked
- Accessibility rules are explicitly checked

Accessibility considerations include:
- Decorative vs informative vs functional images
- WCAG rule awareness
- Avoidance of hallucinated or inferred content

---

## Architecture Decision Records (ADR)

Any non-trivial technical or product decision must be recorded.

ADR purpose:
- Capture reasoning
- Make trade-offs explicit
- Avoid re-discussing the same decisions

ADR structure:
Context
Decision
Alternatives considered
Consequences

yaml
Copy code

---

## Release Discipline

Every merge to `main` updates the changelog.

The changelog answers:
- What changed
- Why it matters
- What version this belongs to

This supports demos, reviews, and external evaluation.

---

## Definition of Done

A task is considered done only if:
- The issue is closed
- Code is merged via Pull Request
- Tests and accessibility checks are updated
- Changelog is updated
- An ADR exists if a decision was made

---

## Explicit Non-Goals

This process intentionally avoids:
- External project management tools
- Scrum ceremonies
- Status meetings
- Process for its own sake

The goal is clarity, traceability, and quality. Nothing else.
