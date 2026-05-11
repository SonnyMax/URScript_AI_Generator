import asyncio
from fastapi import APIRouter
from pydantic import BaseModel
from urscript_app.config import ROBOT_TARGETS, get_active_target, get_active_host, set_active_target
from urscript_app.robot.rtde_client import get_rtde_client

router = APIRouter()
_PROBE_TIMEOUT = 2.0


class SetTargetRequest(BaseModel):
    target: str


async def _probe_port(host: str, port: int) -> bool:
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=_PROBE_TIMEOUT
        )
        writer.close()
        await writer.wait_closed()
        return True
    except Exception:
        return False


@router.get("/robot-target")
async def get_robot_target() -> dict:
    active = get_active_target()
    targets = [
        {"name": name, "ip": ip, "active": name == active}
        for name, ip in ROBOT_TARGETS.items()
    ]
    return {"success": True, "data": {"active": active, "targets": targets}, "error": None}


@router.get("/robot-target/health")
async def robot_target_health() -> dict:
    host = get_active_host()
    script_ok, rtde_ok = await asyncio.gather(
        _probe_port(host, 30002),
        _probe_port(host, 30004),
    )
    reachable = script_ok and rtde_ok
    return {
        "success": True,
        "data": {
            "host": host,
            "reachable": reachable,
            "ports": {"script_30002": script_ok, "rtde_30004": rtde_ok},
        },
        "error": None,
    }


@router.post("/robot-target")
async def set_robot_target(req: SetTargetRequest) -> dict:
    try:
        set_active_target(req.target)
    except ValueError as e:
        return {"success": False, "data": None, "error": {"code": "INVALID_TARGET", "message": str(e)}}

    client = get_rtde_client()
    if client.is_connected():
        client.disconnect()

    return {"success": True, "data": {"active": req.target}, "error": None}
