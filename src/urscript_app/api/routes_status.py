import asyncio
import json
from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse
from urscript_app.robot.rtde_client import get_rtde_client
from urscript_app.robot.safety import get_supervisor

router = APIRouter()


async def _state_generator():
    client = get_rtde_client()
    supervisor = get_supervisor()
    while True:
        state = client.get_state()
        payload = {
            "connected": state.connected,
            "robot_mode": state.robot_mode,
            "safety_mode": state.safety_mode,
            "runtime_state": state.runtime_state,
            "joint_positions": state.joint_positions,
            "tcp_pose": state.tcp_pose,
            "stop_requested": supervisor.is_stop_requested(),
        }
        yield {"data": json.dumps(payload)}
        await asyncio.sleep(0.1)


@router.get("/status")
async def status_stream() -> EventSourceResponse:
    return EventSourceResponse(_state_generator())
