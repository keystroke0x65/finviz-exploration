# Defining types

## Rule
Types are documentation. Use strong types at module boundaries and model data so invalid states are hard to represent.

## Guidelines
- No `any`. Use `unknown` and narrow it when the type is genuinely unknown.
- Type function parameters and return values at public boundaries.
- Prefer discriminated unions over bags of optional fields.
- Don't use type assertions (`as Foo`) to silence the compiler without validating.

## Do
```ts
type LoadState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "success"; data: Artifact[] };
```

## Don't
```ts
type LoadState = {
  loading?: boolean;
  error?: string;
  data?: Artifact[];
};
```
