class TickerNotFoundError(Exception):
    """Raised when Finviz has no data for the requested ticker."""

    def __init__(self, ticker: str):
        self.ticker = ticker
        super().__init__(f"No Finviz data found for ticker '{ticker}'")


class FinvizAuthError(Exception):
    """Raised when the Finviz Elite API rejects our auth token."""

    def __init__(self):
        super().__init__(
            "Finviz Elite API rejected the configured auth token. "
            "Check FINVIZ_API_TOKEN in .env."
        )
