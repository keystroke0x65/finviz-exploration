# Making a commit

## Rule
Each commit is one logical change with a message that explains why.

## Format
Follow the repo's existing convention. If none exists, use:

```
type(scope): short summary in imperative mood

Why this change was needed, and anything a reviewer should know.
```

Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`.

## Do
```
fix(auth): retry user lookup when webhook arrives early

Clerk can fire user.created before our row exists, which caused
intermittent 404s on first login.
```

## Don't
```
fixed stuff
```

## Also
- Don't commit generated files, build output, secrets, or local config unless the repo already does.
- Don't mix formatting changes with logic changes in one commit.
