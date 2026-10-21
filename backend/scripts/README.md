# Scripts

## finviz_sanity_check.py

Manual, live check that the Finviz Elite export API integration still works.
Not run in CI. Run this after Finviz changes something on their end, or when
debugging an unexpected error from the app.

Requires `FINVIZ_API_TOKEN` set in the environment (e.g. via `.env` loaded by
Docker Compose, or exported manually).

    cd backend && python -m scripts.finviz_sanity_check AAPL

    cd backend && python -m scripts.finviz_sanity_check --screens

`--screens` runs the default screens and checks that Finviz recognises every filter code
the screen form can produce and every signal (Finviz silently ignores unknown codes). It
makes about 45 requests, paced one per second.

    cd backend && python -m scripts.finviz_sanity_check --bars HOST

`--bars` fetches 1m, 5m and daily bars for the ticker, checks the intraday bars are
recent, then runs a full pattern scan of it against a temporary database and prints the
setups. Stop the Docker backend first (`docker compose stop backend`): two processes
calling Finviz at once can trigger its rate limiting.
