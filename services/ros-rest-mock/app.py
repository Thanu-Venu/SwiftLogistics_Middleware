import time
from fastapi import FastAPI
from datetime import datetime, timezone

LAST = {
    "seen_at": None,
    "order_id": None,
    "request_json": None,
    "response_json": None,
}
app = FastAPI(title="ROS REST Mock")

@app.post("/optimize-route")
async def optimize(payload: dict):
    order_id = payload.get("order_id")

    resp = {
        "status": "OK",
        "route_id": f"ROUTE-{order_id[-4:]}",
        "eta_minutes": 35
    }

    LAST.update({
        "seen_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "order_id": order_id,
        "request_json": payload,
        "response_json": resp,
    })

    return resp

@app.get("/last")
def last():
    return LAST