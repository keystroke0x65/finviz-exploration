# Writing comments

## Rule
Code says what. Comments say why.

## Write a comment when
- A decision is non-obvious or a simpler approach was rejected for a reason.
- There is a workaround for a bug in a library, browser, or external service (link to it).
- There is a constraint the code can't express (ordering, performance, security).

## Don't comment
- What a line obviously does (`// increment counter`).
- Out-of-date explanations. If you change code, update or remove its comments.
- Commented-out code. Delete it; version control remembers.

## Do
```ts
// Clerk's webhook can arrive before the user row exists, so retry once.
```

## Don't
```ts
// get the user
const user = await getUser(id);
```
