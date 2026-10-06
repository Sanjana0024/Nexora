from fastapi import FastAPI

from app.api.routes.workflows import router as workflow_router


app = FastAPI(
    title="Nexora API",
    description="AI-native workflow orchestration platform",
    version="0.1.0",
)


app.include_router(workflow_router)


@app.get("/")
def root():
    return {
        "message": "Welcome to Nexora",
        "status": "running",
        "version": "0.1.0",
    }