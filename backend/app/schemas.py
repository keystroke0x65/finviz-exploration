from pydantic import BaseModel, ConfigDict


class QuoteResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    Ticker: str
    Company: str | None = None
    Price: str | None = None
