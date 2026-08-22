---
name: solid-review
description: Analyze a Python project for SOLID principle violations, explain the evidence, propose appropriate refactoring strategies, and apply changes only after explicit user approval.
---

# SOLID Review Skill

## Purpose

Analyze the current Python codebase for violations of the five SOLID principles:

- Single Responsibility Principle (SRP)
- Open/Closed Principle (OCP)
- Liskov Substitution Principle (LSP)
- Interface Segregation Principle (ISP)
- Dependency Inversion Principle (DIP)

The goal is to provide evidence-based analysis and safe refactoring recommendations rather than blindly modifying the code.

## General Rules

1. Do not modify files during the analysis phase.
2. Inspect the actual source code before making conclusions.
3. Never claim that a SOLID principle is violated without identifying concrete evidence.
4. Distinguish between:
   - definite violation
   - possible violation
   - design smell that is not necessarily a SOLID violation
5. Prefer simple refactoring solutions over unnecessary abstractions.
6. Preserve existing application behavior.
7. Do not introduce changes unrelated to SOLID refactoring.
8. Before applying any modification, present the proposed changes and ask the user for explicit approval.
9. After applying changes, run the project's available tests or validation commands.
10. Report any failed tests or unexpected behavior.

## Analysis Process

When asked to analyze the project:

### Step 1: Inspect the project

Identify:

- main modules
- classes
- methods
- inheritance relationships
- dependencies
- external infrastructure
- major execution flows

Do not modify files.

### Step 2: Analyze SRP

For each important class:

- identify its responsibilities
- determine whether it has more than one reason to change
- identify unrelated responsibilities
- provide the exact class and methods involved

Example categories include:

- validation
- business logic
- persistence
- payment processing
- notification
- presentation/output

### Step 3: Analyze OCP

Look for code where adding a new behavior requires modifying existing conditional logic.

Pay particular attention to:

- if/elif chains
- switch-like logic
- type checks
- payment methods
- notification types
- business rules

For every finding explain:

- what new feature would require modification
- which existing code would have to change
- how polymorphism or another design technique could improve the design

### Step 4: Analyze LSP

Inspect inheritance relationships.

For every subclass determine whether it can safely replace its parent.

Look for:

- methods that raise NotImplementedError
- overridden methods with incompatible behavior
- strengthened preconditions
- weakened postconditions
- subclasses that cannot perform operations expected from the parent

Provide a concrete example showing why substitution would fail.

### Step 5: Analyze ISP

Inspect interfaces, base classes, and public APIs.

Look for clients or subclasses that depend on methods they do not actually need.

If the project does not explicitly use interfaces, identify class APIs that effectively act as interfaces.

Do not invent an ISP violation merely because a class has multiple methods.

### Step 6: Analyze DIP

Inspect dependencies between high-level business logic and low-level implementations.

Look for:

- direct instantiation of concrete dependencies
- imports of infrastructure classes into business logic
- business classes tightly coupled to databases
- business classes tightly coupled to external services

Explain how abstractions and dependency injection could improve the design.

## Output Format

For every identified issue use this format:

### [Principle] — [Class/File]

**Status:** Definite violation / Possible violation / No violation

**Evidence:**
- File:
- Class:
- Method:
- Relevant behavior:

**Why it violates the principle:**

Explain the reasoning based on the actual code.

**Impact:**

Explain how the design affects maintainability, extensibility, or testing.

**Recommended refactoring:**

Describe the proposed solution without modifying files.

**Why this solution:**

Explain why this approach is preferable to alternatives.

## Refactoring Process

When the user asks to refactor:

1. Re-check the relevant source code.
2. Create a detailed refactoring plan.
3. List every file that will be changed.
4. Explain the purpose of each change.
5. Identify possible risks.
6. Ask the user for explicit approval.
7. Do not modify anything before approval.

After approval:

1. Apply the approved changes only.
2. Avoid unrelated modifications.
3. Run available tests.
4. Run the application if practical.
5. Report changed files.
6. Report test results.
7. Report any remaining SOLID concerns.

## Important Constraint

Do not refactor merely to demonstrate SOLID.

A change should only be proposed when:

- there is concrete evidence of a design problem,
- the refactoring provides a meaningful benefit,
- and the resulting design remains understandable and maintainable.