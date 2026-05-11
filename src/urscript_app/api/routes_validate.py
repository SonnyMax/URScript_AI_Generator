from fastapi import APIRouter
from pydantic import BaseModel, Field
from urscript_app.validator.validate import validate

router = APIRouter()


class ValidateRequest(BaseModel):
    code: str = Field(..., min_length=1)


@router.post("/validate")
async def validate_code(req: ValidateRequest) -> dict:
    result = validate(req.code)
    return {"success": True, "data": result.to_dict(), "error": None}
