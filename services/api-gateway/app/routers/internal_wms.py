import os, requests
from fastapi import APIRouter

router = APIRouter(prefix="/internal/wms", tags=["internal-wms"])
WMS_INTERNAL = os.getenv("WMS_INTERNAL", "http://wms-tcp:9201")

@router.get("/last")
def wms_last():
    r = requests.get(f"{WMS_INTERNAL}/last", timeout=3)
    r.raise_for_status()
    return r.json()