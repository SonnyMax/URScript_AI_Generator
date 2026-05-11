from fastapi import APIRouter
from pydantic import BaseModel, Field
from urscript_app.llm.generator import generate_urscript

router = APIRouter()


class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000)


class GenerateResponse(BaseModel):
    success: bool
    data: dict | None
    error: dict | None = None


@router.post("/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest) -> GenerateResponse:
    result = generate_urscript(req.prompt)
    return GenerateResponse(success=True, data={"code": result.code})
