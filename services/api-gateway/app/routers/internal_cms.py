import os
import requests
from fastapi import APIRouter

router = APIRouter(prefix="/internal/cms", tags=["internal-cms"])

CMS_INTERNAL = os.getenv("CMS_INTERNAL", "http://cms-soap:9000")

@router.get("/last")
def cms_last():
    r = requests.get(f"{CMS_INTERNAL}/last", timeout=3)
    r.raise_for_status()
    return r.json()