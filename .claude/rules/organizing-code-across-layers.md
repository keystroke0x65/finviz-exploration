# Organizing code across layers

## Rule
Keep UI, business logic, and data access separate so each can change without rippling through the others.

## Guidelines
- UI components render and handle interaction. They don't contain database queries or core business rules.
- Business logic lives in plain functions or modules that can be tested without a UI or database.
- Data access (database, external APIs) is isolated behind a small set of functions.
- Place new files where similar files already live. Follow the existing folder structure.

## Why
Mixed layers make every change risky and every test expensive.

## Don't
Write a SQL query or third-party API call directly inside a React component.
