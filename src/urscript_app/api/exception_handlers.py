from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from urscript_app.llm.client import LLMUnavailableError, LLMTimeoutError, LLMError
from urscript_app.llm.generator import EmptyGenerationError
from urscript_app.robot.rtde_client import RTDEConnectionError
from urscript_app.robot.script_sender import ScriptSendError
from urscript_app.robot.session import ExecutionError


def _err(code: str, message: str, status: int) -> JSONResponse:
    return JSONResponse({"success": False, "data": None, "error": {"code": code, "message": message}}, status_code=status)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(LLMUnavailableError)
    async def llm_unavailable(req: Request, exc: LLMUnavailableError) -> JSONResponse:
        return _err("LLM_UNAVAILABLE", str(exc), 503)

    @app.exception_handler(LLMTimeoutError)
    async def llm_timeout(req: Request, exc: LLMTimeoutError) -> JSONResponse:
        return _err("LLM_TIMEOUT", str(exc), 504)

    @app.exception_handler(LLMError)
    async def llm_error(req: Request, exc: LLMError) -> JSONResponse:
        return _err("LLM_ERROR", str(exc), 502)

    @app.exception_handler(EmptyGenerationError)
    async def empty_gen(req: Request, exc: EmptyGenerationError) -> JSONResponse:
        return _err("EMPTY_GENERATION", str(exc), 422)

    @app.exception_handler(RTDEConnectionError)
    async def rtde_conn(req: Request, exc: RTDEConnectionError) -> JSONResponse:
        return _err("RTDE_CONNECTION_ERROR", str(exc), 503)

    @app.exception_handler(ScriptSendError)
    async def script_send(req: Request, exc: ScriptSendError) -> JSONResponse:
        return _err("SCRIPT_SEND_ERROR", str(exc), 502)

    @app.exception_handler(ExecutionError)
    async def exec_err(req: Request, exc: ExecutionError) -> JSONResponse:
        return _err("EXECUTION_ERROR", str(exc), 500)

    @app.exception_handler(Exception)
    async def generic(req: Request, exc: Exception) -> JSONResponse:
        return _err("INTERNAL_ERROR", "An unexpected error occurred", 500)
