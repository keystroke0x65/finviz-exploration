# Naming things

## Rule
Names describe intent in full words. A reader should understand what something is without reading its implementation.

## Guidelines
- Variables and constants: nouns describing the contents (`unpublishedDrafts`, not `arr2` or `data`).
- Functions: verbs describing the action (`fetchUserProfile`, not `userProfile` or `handle`).
- Booleans: read as a yes/no question (`isPublic`, `hasAccess`, `shouldRetry`).
- Avoid abbreviations unless universal in the domain (`id`, `url`, `api` are fine).
- Match the casing and naming conventions already used in the repo for files, components, and folders.

## Do
```ts
const expiredSessions = sessions.filter((s) => s.expiresAt < now);
```

## Don't
```ts
const tmp = sessions.filter((x) => x.e < n);
```
