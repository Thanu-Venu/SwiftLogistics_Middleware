import os
import requests
from fastapi import APIRouter

router = APIRouter(prefix="/internal/ros", tags=["internal-ros"])

ROS_INTERNAL = os.getenv("ROS_INTERNAL", "http://ros-rest:9100")

@router.get("/last")
def ros_last():
    r = requests.get(f"{ROS_INTERNAL}/last", timeout=3)
    r.raise_for_status()
    return r.json()