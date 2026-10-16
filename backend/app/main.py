
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.workflows import router as workflow_router


app = FastAPI(
    title="Nexora API",
    description="AI-native workflow orchestration platform",
    version="0.1.0",
)

# Allow the local Nexora frontend to call the backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(workflow_router)


@app.get("/")
def root():
    return {
        "message": "Welcome to Nexora",
        "status": "running",
        "version": "0.1.0",
    }
