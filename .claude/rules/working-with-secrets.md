# Working with secrets

## Rule
Credentials never appear in code, commits, logs, error messages, or client bundles.

## Guidelines
- Read secrets from environment variables or the project's config system.
- When adding a new variable, add it to `.env.example` with a placeholder, not a real value.
- Never expose server secrets to the client (e.g. no secrets in `NEXT_PUBLIC_*` variables).
- Don't log full request headers, tokens, or connection strings.
- If you find a secret committed in the repo, stop and report it. Don't just move it.
