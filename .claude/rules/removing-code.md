# Removing code

## Rule
Delete dead code instead of commenting it out, but confirm it's actually dead first.

## Before deleting
- Search the whole repo for references, including dynamic ones (string-based imports, route names, config keys).
- Check whether it's part of a public interface other code or services depend on.

## Guidelines
- Remove related leftovers in the same change: unused imports, types, tests, styles, and env vars.
- Only remove code within the scope of your task. Report other dead code you notice instead of deleting it.
