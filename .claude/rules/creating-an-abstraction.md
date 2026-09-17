# Creating an abstraction

## Rule
Don't build generic layers for hypothetical future needs. Wait until a pattern has actually repeated.

## Guidelines
- Duplicate once is fine. On the third occurrence, consider extracting.
- An abstraction must make calling code simpler to read, not just shorter.
- Prefer a plain function over a class, factory, or config-driven system unless complexity demands it.
- Before creating a new helper, search the repo for an existing one.

## Why
Premature abstractions guess wrong about how code will change, and the wrong abstraction costs more than duplication.

## Don't
Create `BaseService`, `GenericRepository<T>`, or a plugin system for a feature with one current use.
