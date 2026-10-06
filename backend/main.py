from fastapi import FastAPI

app = FastAPI(title="Nexora API")


@app.get("/")
def root():
    return {
        "message": "Welcome to Nexora",
        "status": "running"
    }