# Writing tests

## Rule
Test behavior, not implementation. New logic gets tests.

## Guidelines
- Test what a unit does from the outside (inputs, outputs, effects), not its internal steps.
- Name tests as a statement of behavior (`rejects titles longer than 120 characters`).
- Cover the happy path, edge cases, and failure cases.
- Keep tests independent. No reliance on execution order or shared mutable state.
- Mock only at system boundaries (network, time, database), not internal functions.
- Match the existing test framework, file location, and naming convention.

## Don't
- Delete, skip, or loosen a failing test to make the suite pass. If a test seems wrong, say so.
- Assert on private internals that would break under a harmless refactor.
