# Handling errors

## Rule
Every failure path either recovers meaningfully or fails loudly with context. Never catch and ignore.

## Why
Swallowed errors turn bugs into silent data corruption that surfaces far from the cause.

## Do
```ts
try {
  await publishArtifact(id);
} catch (err) {
  throw new Error(`Failed to publish artifact ${id}`, { cause: err });
}
```

## Don't
```ts
try {
  await publishArtifact(id);
} catch (err) {
  console.log(err);
}
```

## Also
- Include the identifiers needed to debug (IDs, operation name), but never secrets or personal data.
- Show users a helpful message; log the technical detail separately.
- Only catch errors you can actually handle at that level. Let the rest propagate.

## Exceptions
Best-effort calls (e.g. analytics, telemetry) may swallow errors, with a comment saying so.
