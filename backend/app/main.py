from fastapi import FastAPI

app = FastAPI(
    title="Académie des Créatifs SaaS API",
    version="0.1.0",
    description="API multi-écoles de l'Académie des Créatifs SaaS.",
)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "academie-des-creatifs-saas"}
