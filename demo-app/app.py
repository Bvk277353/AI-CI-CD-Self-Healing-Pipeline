"""
Demo FastAPI Application
Used to test self-healing capabilities
"""

import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from prometheus_fastapi_instrumentator import Instrumentator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("demo-app")

app = FastAPI(
    title="Demo Application",
    description="Testing self-healing CI/CD pipeline",
    version="1.0.0"
)

# ---------------------------
# Models
# ---------------------------
class Item(BaseModel):
    name: str
    value: int

# ---------------------------
# Routes
# ---------------------------
@app.get("/")
def root():
    return {"status": "healthy", "message": "Demo app is running"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/items/")
def create_item(item: Item):
    logger.info(f"Creating item: {item.name}")
    return {"id": 1, "name": item.name, "value": item.value}

@app.get("/items/{item_id}")
def read_item(item_id: int):
    if item_id > 100:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"id": item_id, "name": f"Item {item_id}"}

# ---------------------------
# Prometheus Metrics (CORRECT)
# ---------------------------
Instrumentator(
    should_group_status_codes=False,
    excluded_handlers=["/health"]
).instrument(app).expose(app)

# ---------------------------
# Main
# ---------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
