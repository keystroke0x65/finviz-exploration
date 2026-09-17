# Adding a dependency

## Rule
Every new package needs a reason. Before installing, check whether the repo already has something that does the job, and whether a few lines of your own code would do.

## Checklist
- Is there an existing dependency or utility in the repo that covers this?
- Is the package actively maintained (recent releases, open issues handled)?
- What does it add to install size or bundle size?
- Is its license compatible with the project?
- Pin or lock the version according to the repo's existing convention.

## Why
Every dependency is code you don't control but must maintain, update, and secure.

## Do
Mention the new dependency and the reason for it in your task summary.

## Don't
Install a large library to use one small function (e.g. all of lodash for `debounce`).
