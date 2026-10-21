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


class FinvizRateLimitError(Exception):
    """Raised when Finviz answers HTTP 429 (too many requests)."""

    def __init__(self, operation: str):
        self.operation = operation
        super().__init__(f"Finviz is rate limiting requests ({operation}); try again in a minute.")


class FinvizUnavailableError(Exception):
    """Raised on timeouts, connection failures, or unexpected HTTP errors from Finviz."""

    def __init__(self, operation: str, reason: str):
        self.operation = operation
        self.reason = reason
        super().__init__(f"Finviz request failed ({operation}): {reason}")
