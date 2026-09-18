from fastapi import FastAPI

app = FastAPI(title="Finviz Dashboard API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
