# Changing behavior or interfaces

## Rule
If behavior, setup, configuration, or a public interface changes, the documentation changes in the same diff.

## This includes
- README setup steps, commands, or required environment variables.
- API routes, request/response shapes, or function signatures other modules use.
- Database schema (include the migration).
- User-visible behavior.

## Guidelines
- Search for every caller of a changed interface and update them.
- Call out breaking changes explicitly in your summary.
