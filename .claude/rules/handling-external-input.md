# Handling external input

## Rule
Treat all external input as untrusted and validate it where it enters the system.

## External input includes
Request bodies, query params, headers, form data, webhooks, file uploads, third-party API responses, URL contents, and anything read from storage that users can influence.

## Guidelines
- Validate shape and types with a schema (e.g. zod) at the boundary, then pass typed data inward.
- Check authorization, not just authentication: can *this* user act on *this* resource?
- Sanitize anything rendered as HTML.
- Set limits on sizes, lengths, and counts.
- Use parameterized queries. Never build SQL or shell commands with string concatenation.

## Do
```ts
const body = CreateArtifactSchema.parse(await req.json());
```

## Don't
```ts
const body = (await req.json()) as CreateArtifactInput;
```
