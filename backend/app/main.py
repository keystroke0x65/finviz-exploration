from fastapi import FastAPI

from app.routes.stocks import router as stocks_router

app = FastAPI(title="Finviz Dashboard API")
app.include_router(stocks_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
