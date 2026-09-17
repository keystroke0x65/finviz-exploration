# Writing a function

## Rule
Each function does one job, reads top to bottom, and takes what it needs as explicit inputs.

## Guidelines
- If you need "and" to describe what it does, split it.
- About 40 lines is a soft ceiling. Going past it needs a reason.
- Use early returns and guard clauses. More than 3 levels of nesting should be rare.
- Replace meaningful numbers and strings with named constants.
- Pass dependencies in as arguments instead of reaching into globals or hidden state.

## Do
```ts
const MAX_TITLE_LENGTH = 120;

function validateTitle(title: string): string | null {
  if (!title.trim()) return "Title is required";
  if (title.length > MAX_TITLE_LENGTH) return "Title is too long";
  return null;
}
```

## Don't
```ts
function validate(t: string) {
  if (t.trim()) {
    if (t.length <= 120) {
      return null;
    } else {
      return "Title is too long";
    }
  } else {
    return "Title is required";
  }
}
```
