# Scripts

## finviz_sanity_check.py

Manual, live check that the Finviz Elite export API integration still works.
Not run in CI. Run this after Finviz changes something on their end, or when
debugging an unexpected error from the /api/stocks endpoint.

Requires `FINVIZ_API_TOKEN` set in the environment (e.g. via `.env` loaded by
Docker Compose, or exported manually).

    cd backend && python -m scripts.finviz_sanity_check AAPL
