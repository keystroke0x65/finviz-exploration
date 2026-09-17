# Fixing a bug

## Rule
Find the root cause, then add a test that fails without the fix and passes with it.

## Steps
1. Reproduce the bug before changing anything.
2. Identify the root cause, not just the line where the symptom appears.
3. Write a test that reproduces it and fails.
4. Make the smallest change that fixes the cause.
5. Confirm the test passes and the rest of the suite still does.

## Don't
- Patch the symptom (e.g. add a null check) without understanding why the value was null.
- Bundle unrelated cleanups into the fix.

## Report
In your summary, state the root cause in one or two sentences.
