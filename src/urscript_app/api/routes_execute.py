from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel, Field
from urscript_app.validator.validate import validate
from urscript_app.robot.session import execute_program
from urscript_app.robot.safety import get_supervisor

router = APIRouter()

_last_result: dict = {"running": False, "message": "idle"}


class ExecuteRequest(BaseModel):
    code: str = Field(..., min_length=1)


def _run(code: str) -> None:
    global _last_result
    _last_result = {"running": True, "message": "executing"}
    try:
        result = execute_program(code)
        _last_result = {"running": False, "message": result.message, "success": result.success}
    except Exception as e:
        _last_result = {"running": False, "message": str(e), "success": False}


@router.post("/execute")
async def execute(req: ExecuteRequest, background_tasks: BackgroundTasks) -> dict:
    # Always re-validate server-side
    vr = validate(req.code)
    if not vr.valid:
        return {
            "success": False,
            "data": None,
            "error": {"code": "VALIDATION_FAILED", "message": "Code failed validation", "details": vr.to_dict()},
        }
    background_tasks.add_task(_run, req.code)
    return {"success": True, "data": {"message": "Execution started"}, "error": None}


@router.post("/stop")
async def stop() -> dict:
    supervisor = get_supervisor()
    supervisor.request_stop()
    return {"success": True, "data": {"message": "Stop requested", "stop_requested": True}, "error": None}


@router.post("/clear-stop")
async def clear_stop() -> dict:
    supervisor = get_supervisor()
    supervisor.clear()
    return {"success": True, "data": {"message": "Safety stop cleared"}, "error": None}


@router.get("/execution-status")
async def execution_status() -> dict:
    return {"success": True, "data": _last_result, "error": None}
