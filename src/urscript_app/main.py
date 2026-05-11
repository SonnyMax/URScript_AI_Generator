from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
from starlette.responses import HTMLResponse

from urscript_app.api.routes_generate import router as generate_router
from urscript_app.api.routes_validate import router as validate_router
from urscript_app.api.routes_execute import router as execute_router
from urscript_app.api.routes_status import router as status_router
from urscript_app.api.routes_robot_target import router as robot_target_router
from urscript_app.api.exception_handlers import register_exception_handlers

BASE_DIR = Path(__file__).parent

templates = Jinja2Templates(directory=str(BASE_DIR / "web" / "templates"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="URScript AI Generator", version="0.1.0", lifespan=lifespan)

    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "web" / "static")), name="static")

    register_exception_handlers(app)

    app.include_router(generate_router, prefix="/api")
    app.include_router(validate_router, prefix="/api")
    app.include_router(execute_router, prefix="/api")
    app.include_router(status_router, prefix="/api")
    app.include_router(robot_target_router, prefix="/api")

    @app.get("/healthz")
    async def healthz() -> dict:
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        # New Starlette API: pass request as keyword arg, not inside context dict
        return templates.TemplateResponse(request=request, name="index.html")

    return app


app = create_app()
