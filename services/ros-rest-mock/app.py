import time
from fastapi import FastAPI

app = FastAPI(title="ROS REST Mock")

@app.post("/optimize-route")
def optimize(payload: dict):
    return {
        "route_id": f"ROUTE-{int(time.time())}",
        "eta_minutes": 45,
        "status": "OK"
    }