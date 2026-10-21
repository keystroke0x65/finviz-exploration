from app.finviz_client import ScreenRow


def snapshot(ticker: str, relative_volume: float | None = 1.0, change: float | None = 1.0,
             after_hours_change: float | None = 0.0, price: float = 2.5) -> ScreenRow:
    return ScreenRow(
        ticker=ticker, company=f"{ticker} Inc", country="USA", market_cap_millions=50.0, float_millions=5.0,
        average_volume_thousands=100.0, relative_volume=relative_volume, price=price, change_percent=change,
        volume=1_000_000, after_hours_close=None, after_hours_change_percent=after_hours_change,
        news_time=None, news_url=None, news_title=None,
    )
